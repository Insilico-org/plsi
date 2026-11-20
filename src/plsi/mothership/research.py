"""Research notes and registry updates from PLSI Explorer's contribution.json, gate-checked into the instance's
outbox. A registry update goes with `mothership send`; a research note only by email (WIRE §7), drafted here."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from plsi import files, mesh, paths
from plsi.errors import GateFailed, UsageError, ValidationError
from plsi.mothership import attach, gate, hints, mine, note as note_rules, scan
from plsi.mothership.attach import REPORT_FILE
from plsi.mothership.enroll import outbox
from plsi.mothership.relay import RESEARCH_REFERENCE, header, mail_address
from plsi.vocab import MothershipMessage, ProjectAction

MAX_SUBJECT = 80
PROJECT_SUBJECT = "PLSI project invite:"  # the Mother routes BOTH invite and revoke by this subject prefix — keep it for both
NOTE_INLINE_MAX = 30_000  # bytes of the note's JSON: a longer note sends its report as a data file, and still longer is refused
# the kinds an Explorer contribution.json may have, named as on the wire
KINDS = (MothershipMessage.RESEARCH_NOTE, MothershipMessage.REGISTRY_UPDATE)


def _size(doc: dict[str, Any]) -> int:
    return len(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def _report_as_file(doc: dict[str, Any], mail: dict[str, bytes],
                    instances: set[str]) -> tuple[dict[str, Any], dict[str, bytes]]:
    """A note too long to attach keeps its items and method and sends its report as the data file report.md, checked
    as every data file is (the caller has gated it inline first: its lines and its length); the note itself stays a
    separate .json attachment, never inside the zip."""
    entries = doc.get("files") or []
    if len(entries) >= note_rules.MAX_FILES:
        raise ValidationError(f"a long note sends its report as a data file: at most {note_rules.MAX_FILES - 1} other files",
                              code="BAD_CONTRIBUTION")
    data = doc["report"].encode("utf-8")
    if found := [scan.flag("report", r) for r in sorted(attach.check(REPORT_FILE, data, instances))]:
        raise GateFailed(found, "the research note's report is not safe to send", hints.hint(found))
    rest = {k: v for k, v in doc.items() if k != "report"}
    rest["files"] = [*entries, {"name": REPORT_FILE, "sha256": files.sha256_hex(data)}]
    return rest, {**mail, REPORT_FILE: data}


def _within_inbox_limit(doc: dict[str, Any], mail: dict[str, bytes], instance: str, instances: set[str],
                        what: str) -> tuple[dict[str, Any], dict[str, bytes]]:
    """A research note too large to attach inline moves its report to report.md (re-gated as a data file); one still
    over the inbox limit without its report is refused — the inbox would cut it off (WIRE §7)."""
    if doc.get("report") and _size(doc) > NOTE_INLINE_MAX:
        doc, mail = _report_as_file(doc, mail, instances)
        gate.require(doc, instance, what=what)
    if _size(doc) > NOTE_INLINE_MAX:
        raise ValidationError(f"the research note is over {NOTE_INLINE_MAX // 1000} KB even without its report",
                              code="NOTE_TOO_LONG",
                              hint="fewer items or shorter support, against and risks lines, or split it into two notes")
    return doc, mail


def note(instance: str, file: str) -> dict[str, Any]:
    """`mothership note`: a plsi_research_note (items, method; report, files and project optional) or
    plsi_registry_update (items); nothing is sent."""
    paths.instance_dir(instance)
    given = files.load_json(file)
    if not isinstance(given, dict) or given.get("kind") not in KINDS:
        raise ValidationError(f"contribution.json kind must be one of {', '.join(KINDS)}", code="BAD_CONTRIBUTION")
    kind, instances = MothershipMessage(given["kind"]), gate.instance_names(instance)
    required, optional = gate.FIELDS[kind]
    doc = header(kind) | {k: given[k] for k in sorted(required | optional) if k in given and k != "files"}  # "to", "consent" stay
    if kind == MothershipMessage.RESEARCH_NOTE and isinstance(doc.get("items"), list):
        doc["items"] = [{**item, "tags": mesh.tags(item["tags"], f"items[{n}].tags")}
                        if isinstance(item, dict) and "tags" in item else item for n, item in enumerate(doc["items"])]
    mail: dict[str, bytes] = {}
    if "files" in given:
        if kind != MothershipMessage.RESEARCH_NOTE:
            raise ValidationError("only a research note carries files", code="BAD_CONTRIBUTION")
        doc["files"], mail = attach.prepare(given["files"], instances)
    doc, removed = scan.strip_pictures(doc)  # the author's own draft: a hidden picture goes, the text stays
    label = kind.value.removeprefix("plsi_")
    gate.require(doc, instance, what=label.replace("_", " "))  # a report still inline: a refusal names its line
    if kind == MothershipMessage.RESEARCH_NOTE:
        doc, mail = _within_inbox_limit(doc, mail, instance, instances, label.replace("_", " "))
    path = outbox(instance, label.replace("_", "-"))
    bundle = attach.zip_bytes(mail) if mail else None  # too large raises before anything is written
    if bundle is not None:
        files.atomic_write_bytes(path.with_suffix(".zip"), bundle)  # the zip first: a note never sits without it
    files.atomic_write_json(path, doc)
    package_hash = files.hash_json(doc)
    if kind == MothershipMessage.RESEARCH_NOTE and isinstance(doc.get("project"), dict):  # a draft for `mothership mine`
        mine.note_drafted(instance, doc["project"]["id"], doc["project"].get("title"), package_hash)
    out = {"file": str(path), "kind": kind.value, "items": len(doc.get("items") or []), "pictures_removed": removed,
           "files": len(doc.get("files") or []), "package_hash": package_hash}
    return out | ({"bundle": str(path.with_suffix(".zip"))} if mail else {})


def _project_access(project: str, emails: list[str], action: ProjectAction, instance: str | None) -> dict[str, Any]:
    """The email the project owner sends the Mother to grant (invite) or withdraw (revoke) collaborators' Drive
    writer on projects/<project>/. The body is the JSON the Mother's PROJECT_INVITE gate reads — the wire header plus
    {project_id, emails, action}; nothing is sent, and only the owner's own address (DMARC pass) can act, so the
    Mother verifies the sender."""
    if not (isinstance(project, str) and scan.UUID_LOWER.fullmatch(project)):  # as a note's project.id (bad_project)
        raise ValidationError(f"not a project id: {project!r}", code="BAD_PROJECT",
                              hint="the project's id from plsi research project")
    clean = mine.clean_emails(emails)
    message = header(MothershipMessage.PROJECT_INVITE) | {"project_id": project, "emails": clean, "action": action.value}
    out = {"to": mail_address(RESEARCH_REFERENCE, "research address", "NO_RESEARCH_ADDRESS"), "subject": PROJECT_SUBJECT, "body": json.dumps(message, ensure_ascii=False, indent=1),
           "project_id": project, "emails": len(clean)}
    if instance:  # remembered for `mothership mine`; it counts once `mothership sent --draft <draft>` records it went
        out["draft"] = mine.access_drafted(instance, project, clean, action.value)
    return out


def project_invite(project: str, emails: list[str], instance: str | None = None) -> dict[str, Any]:
    """`mothership project invite`: draft the owner's email that grants collaborators Drive writer on
    projects/<project>/ (action "invite"). With `--instance`, the draft is remembered locally for `mothership mine`."""
    return _project_access(project, emails, ProjectAction.INVITE, instance)


def project_revoke(project: str, emails: list[str], instance: str | None = None) -> dict[str, Any]:
    """`mothership project revoke`: draft the owner's email that removes collaborators' Drive writer on
    projects/<project>/ and drops them from the registry invitees[] (action "revoke"). The symmetric inverse of
    project_invite — same owner gate, same validation, same body shape. With `--instance`, remembered for `mine`."""
    return _project_access(project, emails, ProjectAction.REVOKE, instance)


def _item(item: dict[str, Any]) -> str:
    sources = ", ".join(f"{s.get('kind')} {s.get('id')}" for s in item.get("sources") or [])
    lines = [f"Question: {item['question']}"] if item.get("question") else []
    lines += [f"Claim: {item.get('claim')}", f"Grade: {item.get('grade')} ({item.get('evidence_class')})",
              f"Sources: {sources or 'none'}"]
    for key in note_rules.FINDINGS:
        lines += [f"{key.capitalize()}: {e['source']['kind']} {e['source']['id']} - {e['finding']}"
                  for e in item.get(key, [])]
    lines += [f"Limits: {t}" for t in item.get("limits", [])]
    lines += [f"Model output: {e['model']} - {e['finding']}" for e in item.get("model_output", [])]
    return "\n".join([*lines, f"Falsified by: {item.get('falsified_by')}", f"Next step: {item.get('next_step')}"])


def email(file: str, expected: str) -> dict[str, Any]:
    """`mothership email`: the email for a gate-checked research note (WIRE §7): the address, the subject, a body with
    the note in plain words, and the message file to attach. Nothing is sent; the user's Grok email sends it."""
    doc = scan.load(file)
    gate.approved(doc, expected)
    if not isinstance(doc, dict) or doc.get("kind") != MothershipMessage.RESEARCH_NOTE:
        raise UsageError("only a research note goes by email", hint="plsi mothership note --instance <i> --file contribution.json")
    gate.require(doc, None, what="research note")
    to = mail_address(RESEARCH_REFERENCE, "research address", "NO_RESEARCH_ADDRESS")
    path, by_email = Path(file).resolve(), note_rules.by_email(doc)
    if by_email:
        attach.verify(path.with_suffix(".zip"), by_email)
    on_drive = [e["name"] for e in doc.get("files") or [] if "drive_id" in e]
    claim = str(doc["items"][0].get("claim") or "research note")
    subject = "PLSI research note: " + (claim if len(claim) <= MAX_SUBJECT else claim[:MAX_SUBJECT - 1].rstrip() + "…")
    body = "\n\n".join(["A research note from PLSI, sent by its author for review by the Longevity Mothership.",
                         *([f"Project: {doc['project']['title']}"] if doc.get("project") else []),
                         *(_item(i) for i in doc["items"]), f"Method: {doc['method']}",
                         *([f"Data files in the zip: {', '.join(e['name'] for e in by_email)}."] if by_email else []),
                         *([f"Data files on Google Drive, shared with the Mothership: {', '.join(on_drive)}."]
                           if on_drive else []),
                         "The note itself is attached as JSON" + (
                             f", its full report in the zip as {REPORT_FILE}." if any(e["name"] == REPORT_FILE for e in by_email)
                             else ", the full report as markdown." if doc.get("report") else ".")])
    out = {"to": to, "subject": subject, "body": body, "items": len(doc["items"]), "package_hash": files.hash_json(doc),
           "attachment": str(path)}
    if by_email:
        out["bundle"] = str(path.with_suffix(".zip"))
    if doc.get("report"):  # a short report is inside the note, and also attached as markdown for a human reader
        report = path.with_suffix(".report.md")
        files.atomic_write_text(report, doc["report"])
        out["report"] = str(report)
    return out
