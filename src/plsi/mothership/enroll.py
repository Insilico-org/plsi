"""The user's enrollment: consent version and kinds, the install id and token the relay mints for a one-time /join
code, the contributor secret whose sha256 is the pseudonym (contributor_id), and the sent log with its receipts. The
token and the secret leave <instance>/mothership/install.json only in the relay's Authorization header (the token)
and a delete_all withdrawal (the secret, as its proof), and are never returned."""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from plsi import files, keys, paths
from plsi.clock import now, parse_time, ts_filename
from plsi.errors import NetworkError, NotFound, ValidationError
from plsi.life.store import EventStore
from plsi.mothership.relay import RECEIPT_DAYS, address, header, post, rate_limited, relay_error
from plsi.vocab import (ContributionKind, EnrollmentStatus, MothershipMessage, ReceiptState, Relation,
                        WithdrawalRequest)

CONSENT_PATH = paths.REPO_ROOT / "mothership" / "consent.md"
STALE_DELETION_H = 1  # a deletion with no receipt after this is told to the user, never left to sit


def _marker(name: str) -> str:
    match = re.search(rf"<!-- {name}: ([0-9.]+) -->", CONSENT_PATH.read_text(encoding="utf-8"))
    if not match:
        raise ValidationError(f"mothership/consent.md has no {name} marker")
    return match.group(1)


def current_consent() -> str:
    """The version marker of mothership/consent.md, the text the user agrees to."""
    return _marker("plsi-mothership-consent")


def _version(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def reworded(record: dict[str, Any] | None) -> bool:
    """The consent text changed since `record` only in wording: its version is older than the current one and not
    older than the `plsi-mothership-shared` marker, the version that last changed the kinds or what they share."""
    given = (record or {}).get("consent_version")
    return isinstance(given, str) and _version(_marker("plsi-mothership-shared")) <= _version(given) < _version(
        current_consent())


def folder(instance: str) -> Path:
    return paths.instance_dir(instance) / "mothership"


def outbox(instance: str, stem: str) -> Path:
    """A new file of the instance's outbox, `<stem>-<timestamp>-<4 hex>.json`: the random part keeps two messages
    made in one second apart."""
    return folder(instance) / "outbox" / f"{stem}-{ts_filename()}-{secrets.token_hex(2)}.json"


def consented(enrollment: dict[str, Any] | None) -> bool:
    """The user's enrollment is active (not withdrawn)."""
    return bool(enrollment) and enrollment.get("status") == EnrollmentStatus.ACTIVE


def _install_path(instance: str) -> Path:
    return folder(instance) / "install.json"


def _enrollment_path(instance: str) -> Path:
    return folder(instance) / "enrollment.json"


def _save_install(instance: str, data: dict[str, str]) -> None:
    files.atomic_write_json(_install_path(instance), data, private=True)


def install(instance: str) -> dict[str, str] | None:
    path = _install_path(instance)
    if not path.is_file():
        return None
    found = files.load_json(path)
    for secret in {"token", "contributor_secret"} & found.keys():
        keys.hide(found[secret])
    return found


def bearer(instance: str) -> str:
    """The install token the relay minted for this instance; raises when it has none."""
    found = install(instance)
    if found is None:
        raise NotFound(f"{instance!r} has no relay install token", code="NOT_ENROLLED",
                       hint=f"plsi mothership join --instance {instance} --code <code from {address()}/join> ...")
    return found["token"]


def pseudonym(secret: str) -> str:
    """The contributor id: sha256 of the contributor secret, 64 lowercase hex."""
    return files.sha256_hex(secret)


def _proof(instance: str, record: dict[str, Any] | None) -> str | None:
    """The contributor secret, when the install holds the one behind the enrollment's contributor id."""
    secret = (install(instance) or {}).get("contributor_secret")
    ok = isinstance(secret, str) and bool(record) and pseudonym(secret) == record.get("contributor_id")
    return secret if ok else None


def _enroll(instance: str, code: str) -> dict[str, str]:
    """Trade the one-time /join code for the install id and token the relay mints; stored, never returned."""
    try:
        reply = post("/enroll", {"code": code.strip()})
    except NetworkError as exc:
        if exc.status == 429:
            raise rate_limited(exc) from None
        reason = relay_error(exc)
        if reason == "enrollment_closed":
            raise ValidationError("the Longevity Mothership is not open for new contributors yet", code="ENROLLMENT_CLOSED",
                                  hint="nothing was recorded; try joining again later") from None
        raise ValidationError(f"the relay refused the enrollment code: {reason}", code="ENROLL_FAILED",
                              hint=f"get a new code at {address()}/join (codes are one-time and expire in ~15 minutes)") from None
    if not (reply.get("ok") and reply.get("install_id") and reply.get("token")):
        raise ValidationError("the relay did not return an install id and token", code="ENROLL_FAILED")
    minted = {"install_id": str(reply["install_id"]), "token": str(reply["token"]), "enrolled_at": now().isoformat()}
    keys.hide(minted["token"])
    # a new code keeps the secret, so the contributor stays the same
    kept = {k: v for k, v in (install(instance) or {}).items() if k == "contributor_secret"}
    _save_install(instance, minted | kept)
    return minted | kept


def _secret(instance: str, found: dict[str, str]) -> str:
    """The contributor secret: 32 random bytes as hex, made at the first join (and after a confirmed deletion)."""
    if "contributor_secret" not in found:
        found["contributor_secret"] = secrets.token_hex(32)
        keys.hide(found["contributor_secret"])
        _save_install(instance, found)
    return found["contributor_secret"]


def enrollment(instance: str) -> dict[str, Any] | None:
    path = _enrollment_path(instance)
    return files.load_json(path) if path.is_file() else None


def active(instance: str) -> dict[str, Any]:
    """The enrollment, when active and given for the current consent text; raises otherwise."""
    found, current = enrollment(instance), current_consent()
    if not consented(found) or _proof(instance, found) is None:
        raise NotFound(f"{instance!r} has not joined the Longevity Mothership", code="NOT_ENROLLED",
                       hint=f"plsi mothership join --instance {instance} --kind states --consent-version {current}")
    if reworded(found):
        raise ValidationError("the consent text changed in wording only; what is shared is unchanged",
                              code="CONSENT_REWORDED",
                              hint=f"ask the user to accept the new text, then plsi mothership join --instance {instance} "
                                   f"--consent-version {current} (no --kind: the kinds stay)")
    if found["consent_version"] != current:
        raise ValidationError("the consent text changed since the user joined", code="CONSENT_OUTDATED",
                              hint=f"show mothership/consent.md {current} and ask again before sending")
    return found


def deletion_waiting(instance: str) -> bool:
    """A delete_all was asked for and its receipt is not in: the install is forgotten only when it is."""
    return bool((enrollment(instance) or {}).get("deletion_requested")) and install(instance) is not None


def join(instance: str, consent_version: str, kind: list[str] | None = None, code: str | None = None) -> dict[str, Any]:
    """`mothership join`: record the user's consent for the kinds they picked. The first join trades the one-time
    code from the relay's /join page for this install's id and token; later joins (other kinds) need no code. With
    no kinds, the user accepted reworded consent text (`reworded`): the active enrollment keeps its kinds. Never
    while a deletion waits for its receipt: one install holds one contributor, and the deletion forgets it."""
    store = EventStore(instance)
    if store.subject.relation != Relation.SELF:
        raise ValidationError("only the user's own instance (relation self) can join", code="NOT_SELF",
                              hint="family members and sample people are never shared")
    if deletion_waiting(instance):
        raise ValidationError("a deletion of everything shared is waiting for the Mothership's receipt",
                              code="DELETION_PENDING",
                              hint=f"plsi mothership receipt --instance {instance}; once it is confirmed, join again "
                                   f"with a new code from {address()}/join")
    if consent_version != current_consent():
        raise ValidationError(f"consent version {consent_version} is not the current text", code="CONSENT_OUTDATED",
                              hint="show the current mothership/consent.md and pass its version")
    if not kind:
        record = enrollment(instance)
        if not (consented(record) and (reworded(record) or record["consent_version"] == consent_version)):
            raise ValidationError("pick the kinds to share: what is shared changed, or the user has not joined",
                                  code="KIND_REQUIRED", hint="show the kinds card and pass one --kind per picked item")
        kind = record["kinds"]
    kinds = sorted({ContributionKind(k).value for k in kind})
    found = _enroll(instance, code) if code else install(instance)  # a code always re-enrolls (new install id)
    if found is None:
        raise ValidationError("the first join needs an enrollment code", code="CODE_REQUIRED",
                              hint=f"the user gets one at {address()}/join and pastes it in chat")
    record = {"contributor_id": pseudonym(_secret(instance, found)), "kinds": kinds, "consent_version": consent_version,
              "joined_at": now().isoformat(), "status": EnrollmentStatus.ACTIVE}
    files.atomic_write_json(_enrollment_path(instance), record)
    return status(instance)


def leave(instance: str, delete: bool = False, anyway: bool = False) -> dict[str, Any]:
    """`mothership leave`: stop sharing; writes the withdrawal file to send. `delete` asks to delete everything with
    the contributor secret as proof, once every sent contribution has its receipt (`anyway`, only after the user
    agreed: before). The secret stays in the install until the deletion's receipt forgets the install, so an
    unconfirmed deletion can go again and a later join is a new contributor."""
    record = enrollment(instance)
    if not record:
        raise NotFound(f"{instance!r} never joined the Longevity Mothership", code="NOT_ENROLLED")
    secret = _proof(instance, record)
    if delete and secret is None:
        raise ValidationError("this install no longer holds the secret of its contributor id", code="NO_PROOF",
                              hint="the deletion is confirmed already, or this install never joined; "
                                   "otherwise ask the Mothership steward")
    if delete and not anyway and (waiting := pending(folder(instance), MothershipMessage.CONTRIBUTION)):
        raise ValidationError(f"{len(waiting)} sent contribution(s) have no Mothership receipt yet",
                              code="RECEIPT_PENDING", hint=f"plsi mothership receipt --instance {instance}, then leave "
                                                           "--delete again; --anyway only after the user agreed")
    record |= {"status": EnrollmentStatus.WITHDRAWN, "withdrawn_at": now().isoformat(), "deletion_requested": delete}
    files.atomic_write_json(_enrollment_path(instance), record)
    message = header(MothershipMessage.WITHDRAWAL) | {
        "contributor_id": record["contributor_id"], "request": WithdrawalRequest.DELETE_ALL if delete else WithdrawalRequest.STOP}
    if delete:
        message["proof"] = secret
    path = outbox(instance, "withdrawal")
    files.atomic_write_json(path, message, private=delete)  # a delete_all carries the contributor secret
    return {"file": str(path), "request": message["request"]}


def forget_install(instance: str) -> None:
    """The deletion is confirmed: forget the install whole (id, token, secret); a later join gets a new, unlinked one."""
    _install_path(instance).unlink(missing_ok=True)


def sends(base: Path) -> list[dict[str, Any]]:
    """Every message in base/sent.jsonl with its receipt state (acks.jsonl): `stored` or `deleted` (the receipt), `refused` (the code),
    `pending`, `never_confirmed` (no receipt within RECEIPT_DAYS) or `before_receipts` (sent without a ticket)."""
    acks = {a.get("ticket"): a.get("ack") or {} for a in files.read_jsonl(base / "acks.jsonl")}
    cutoff = now() - timedelta(days=RECEIPT_DAYS)
    out = []
    for e in files.read_jsonl(base / "sent.jsonl"):
        t = e.get("ticket")
        if not t:
            state: dict[str, Any] = {"receipt_state": ReceiptState.BEFORE_RECEIPTS}
        elif t in acks:
            a = acks[t]
            stored = ReceiptState.DELETED if a.get("status") == "deleted" else ReceiptState.STORED
            state = ({"receipt_state": stored, "receipt": a.get("receipt")}
                     if a.get("ok") else {"receipt_state": ReceiptState.REFUSED, "error": a.get("error")})
        else:
            fresh = parse_time(e["sent_at"]) > cutoff
            state = {"receipt_state": ReceiptState.PENDING if fresh else ReceiptState.NEVER_CONFIRMED}
        out.append(e | state)
    return out


def pending(base: Path, kind: str | None = None) -> list[dict[str, Any]]:
    """Sent messages with a relay ticket and no Mother receipt yet, sent within RECEIPT_DAYS."""
    return [e for e in sends(base)
            if e["receipt_state"] == ReceiptState.PENDING and (kind is None or e.get("kind") == kind)]


def unconfirmed_deletions(instance: str) -> list[dict[str, Any]]:
    """Deletions sent over STALE_DELETION_H ago with no receipt: the user is told and can ask again."""
    cutoff = now() - timedelta(hours=STALE_DELETION_H)
    return [{k: e[k] for k in ("sent_at", "ticket", "request") if k in e}
            for e in pending(folder(instance), MothershipMessage.WITHDRAWAL)
            if e.get("request") == WithdrawalRequest.DELETE_ALL and parse_time(e["sent_at"]) < cutoff]


def status(instance: str) -> dict[str, Any]:
    """`mothership status`: enrollment, whether its consent is current, the address and what was sent."""
    record, found, log, current = enrollment(instance), install(instance), sends(folder(instance)), current_consent()
    return {"instance": instance, "enrolled": consented(record), "enrollment": record, "consent_version": current,
            "consent_current": bool(record and record["consent_version"] == current), "consent_reworded": reworded(record),
            "to": address(), "join_page": f"{address()}/join", "has_install_token": found is not None,
            "has_contributor_secret": "contributor_secret" in (found or {}),
            "deletion_pending": deletion_waiting(instance),
            "sent_count": len(log), "sent": [{k: v for k, v in e.items() if k != "reply"} for e in log[-12:]],
            "receipts_pending": sum(e["receipt_state"] == ReceiptState.PENDING for e in log),
            "deletions_unconfirmed": unconfirmed_deletions(instance)}
