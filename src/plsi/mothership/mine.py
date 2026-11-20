"""The owner's own view of their Mothership research projects. Remembered locally in <instance>/mothership/projects.json
so `mothership mine` shows each project's status without the Mother ever exposing a per-owner query. A note, invite or
revoke drafted here stays a draft (its id: the note's package_hash, the invite's `draft`) until `mothership sent`
records that its email went; only what went counts. A send settles the drafts it makes moot, and recording one twice
changes nothing. Whether the Mother published it comes from the public table."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import NotFound, PlsiError, UsageError, ValidationError
from plsi.mothership import professional
from plsi.mothership.enroll import folder
from plsi.mothership.relay import get
from plsi.vocab import DraftKind, ProjectAction, PublicationStatus

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # an invitee needs only a Google account, unknown to the Mother
MAX_INVITE_EMAILS = 50  # the Mother's PROJECT_INVITE gate caps one invite at this many addresses


def clean_emails(emails: list[str]) -> list[str]:
    """The collaborators a project invite or revoke names: each stripped and validated, deduped by case keeping the
    first spelling, at most MAX_INVITE_EMAILS and at least one. Shared by the wire body and the local draft record."""
    clean: list[str] = []
    for raw in emails or []:
        address = raw.strip()
        if not (address.isascii() and EMAIL_RE.match(address)):  # the Mother's gate rejects non-ascii addresses
            raise ValidationError(f"not an email address: {address!r}", code="BAD_EMAIL",
                                  hint="--email you@example.com (a collaborator's Google account)")
        if address.lower() not in {c.lower() for c in clean}:  # one account, whatever its case: the first spelling
            clean.append(address)
    if not clean:
        raise UsageError("name at least one collaborator email", hint="--email you@example.com")
    if len(clean) > MAX_INVITE_EMAILS:  # the Mother caps one invite at MAX_INVITE_EMAILS addresses
        raise UsageError(f"one invite names at most {MAX_INVITE_EMAILS} collaborators", hint="send another invite")
    return clean


def _path(instance: str) -> Path:
    return folder(instance) / "projects.json"


def _load(instance: str) -> dict[str, Any]:
    path = _path(instance)
    return files.load_json(path) if path.is_file() else {}


def _entry(data: dict[str, Any], project_id: str) -> dict[str, Any]:
    """A project's record: `notes` and `access` hold the unsent drafts, `note_sent` and `collaborators` what went, and
    `settled` each draft already sent or made moot by a later send."""
    entry = data.setdefault(project_id, {"title": None, "collaborators": {}, "notes": [], "access": {}})
    entry.setdefault("access", {})
    entry.setdefault("settled", {})
    return entry


def note_drafted(instance: str, project_id: str, title: str | None, draft: str) -> None:
    """Remember a note drafted here for a project, by its package_hash; it counts once `sent` records it."""
    data = _load(instance)
    entry = _entry(data, project_id)
    if draft not in entry["notes"]:
        entry["notes"].append(draft)
    entry["title"] = title or entry.get("title")
    files.atomic_write_json(_path(instance), data)


def access_drafted(instance: str, project_id: str, emails: list[str], action: str) -> str:
    """Remember an invite or revoke drafted here and return its draft id: the same action for the same people is the
    same draft, whatever their order or case, and drafting it again makes it the newest. It changes the collaborators
    once `sent` records it."""
    given = {"action": action, "emails": sorted({e.lower() for e in clean_emails(emails)})}
    draft = files.hash_json({"project_id": project_id, **given})
    data = _load(instance)
    access = _entry(data, project_id)["access"]
    access.pop(draft, None)
    access[draft] = given | {"order": _order(access) + 1}  # the file sorts its keys, so drafting order is kept here
    files.atomic_write_json(_path(instance), data)
    return draft


def _order(access: dict[str, Any], draft: str | None = None) -> int:
    """The drafting order of `draft`, or the newest of `access` (0 for none)."""
    return access[draft]["order"] if draft else max((a["order"] for a in access.values()), default=0)


def _settle(entry: dict[str, Any], draft: str) -> dict[str, Any]:
    """Move the unsent `draft` to `settled` as sent, with the drafts it makes moot: a note's other drafts (earlier
    versions of it), or each invite or revoke drafted before it for none but the same people."""
    settled, notes, access = entry["settled"], entry["notes"], entry["access"]
    if draft in notes:
        settled |= {d: {"what": DraftKind.NOTE, "sent": d == draft} for d in notes}
        entry["notes"] = []
        return settled[draft]
    at = _order(access, draft)
    given = access.pop(draft)
    for older in [d for d in access if _order(access, d) < at and set(access[d]["emails"]) <= set(given["emails"])]:
        moot = access.pop(older)
        settled[older] = {"what": moot["action"], "emails": moot["emails"], "sent": False}
    settled[draft] = {"what": given["action"], "emails": given["emails"], "sent": True}
    return settled[draft]


def _went(entry: dict[str, Any], done: dict[str, Any]) -> None:
    if done["what"] == DraftKind.NOTE:
        entry["note_sent"] = True
    else:  # for an address the last invite or revoke sent wins
        entry.setdefault("collaborators", {}).update(dict.fromkeys(done["emails"], done["what"]))


def sent(instance: str, draft: str) -> dict[str, Any]:
    """`mothership sent`: record that the email of a drafted note, invite or revoke went. Recording it again changes
    nothing (`already`); a draft a later send made moot whose email went after all counts from now."""
    data = _load(instance)
    for project_id, entry in data.items():
        if draft in (entry.get("notes") or []) or draft in (entry.get("access") or {}):
            done, already = _settle(_entry(data, project_id), draft), False
        elif draft in (entry.get("settled") or {}):
            done = entry["settled"][draft]
            already, done["sent"] = done["sent"], True
        else:
            continue
        if not already:
            _went(entry, done)
            files.atomic_write_json(_path(instance), data)
        out = {"project_id": project_id, "sent": done["what"]}
        if "emails" in done:  # an invite or revoke carries its addresses; a note does not
            out["emails"] = done["emails"]
        return out | ({"already": True} if already else {})
    raise NotFound(f"no draft {draft!r} on this computer", code="NO_DRAFT",
                   hint=f"plsi mothership mine --instance {instance} lists the drafts not yet recorded as sent")


def _status(entry: dict[str, Any], published: bool, read: bool) -> PublicationStatus:
    if published:
        return PublicationStatus.PUBLISHED
    if entry.get("note_sent"):
        return PublicationStatus.AWAITING if read else PublicationStatus.SENT
    return PublicationStatus.DRAFTED


def _merge(local: dict[str, Any], table: dict[str, Any], read: bool) -> list[dict[str, Any]]:
    """The owner's local record enriched with the public table (`read`: it was fetched just now): title and link come
    from the table once published."""
    published = {p["project_id"]: p for p in (table.get("projects") or []) if isinstance(p, dict) and p.get("project_id")}
    out = []
    for project_id, entry in local.items():
        pub = published.get(project_id)
        access = entry.get("access") or {}
        out.append({"project_id": project_id,
                    "title": (pub or {}).get("title") or entry.get("title"),
                    "status": _status(entry, pub is not None, read).value,
                    "link": (pub or {}).get("link"),
                    "collaborators": sorted(e for e, a in (entry.get("collaborators") or {}).items()
                                            if a == ProjectAction.INVITE),
                    "drafts": {"notes": list(entry.get("notes") or []),
                               "access": [{"draft": d, "action": access[d]["action"], "emails": access[d]["emails"]}
                                          for d in sorted(access, key=lambda d: _order(access, d))]}})
    order = list(PublicationStatus)
    return sorted(out, key=lambda p: (order.index(PublicationStatus(p["status"])), (p["title"] or p["project_id"]).lower()))


def mine(instance: str) -> dict[str, Any]:
    """`mothership mine`: this owner's projects and their status — the local record, enriched with the public projects
    table when a token can read it (network, best-effort). `table_read` is False when the table could not be fetched:
    a sent note then reads `sent`, never `awaiting`."""
    table: dict[str, Any] = {}
    read = False
    try:
        fetched = get("/public/projects", professional.token())
        table, read = (fetched if isinstance(fetched, dict) else {}), True
    except PlsiError:  # offline, or a token without findings:read — the local view still stands
        pass
    return {"projects": _merge(_load(instance), table, read), "table_read": read}
