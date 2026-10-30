"""The user's enrollment in the Longevity Mothership: the consent version and the shared kinds; the install
id and token the relay mints for a one-time code from its /join page; and the contributor secret whose sha256 is the
pseudonym (contributor_id) every package carries. The install token and the secret never leave
<instance>/mothership/install.json except in the Authorization header to the relay (the token) and in a delete_all
withdrawal (the secret, as its proof), and are never returned."""

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
from plsi.mothership.relay import SCHEMA_VERSION, address, post, rate_limited, relay_error
from plsi.vocab import (ContributionKind, EnrollmentStatus, MothershipMessage, ReceiptState, Relation,
                        WithdrawalRequest)

CONSENT_PATH = paths.REPO_ROOT / "mothership" / "consent.md"


def current_consent() -> str:
    """The version marker of mothership/consent.md, the text the user agrees to."""
    match = re.search(r"<!-- plsi-mothership-consent: ([0-9.]+) -->", CONSENT_PATH.read_text(encoding="utf-8"))
    if not match:
        raise ValidationError("mothership/consent.md has no plsi-mothership-consent marker")
    return match.group(1)


def folder(instance: str) -> Path:
    return paths.instance_dir(instance) / "mothership"


def consented(enrollment: dict[str, Any] | None) -> bool:
    """The user's enrollment is active (not withdrawn)."""
    return bool(enrollment) and enrollment.get("status") == EnrollmentStatus.ACTIVE


def _install_path(instance: str) -> Path:
    return folder(instance) / "install.json"


def _save_install(instance: str, data: dict[str, str]) -> None:
    files.atomic_write_json(_install_path(instance), data, private=True)


def install(instance: str) -> dict[str, str] | None:
    path = _install_path(instance)
    if not path.is_file():
        return None
    found = files.load_json(path)
    for secret in ("token", "contributor_secret", "deletion_secret"):
        if secret in found:
            keys.hide(found[secret])
    return found


def pseudonym(secret: str) -> str:
    """The contributor id: sha256 of the contributor secret, 64 lowercase hex."""
    return files.sha256_hex(secret)


def _enroll(instance: str, code: str) -> dict[str, str]:
    """Trade the one-time /join code for the install id and token the relay mints; stored, never returned."""
    try:
        reply = post("/enroll", {"code": code.strip()})
    except NetworkError as exc:
        if exc.status == 429:
            raise rate_limited(exc) from None
        if relay_error(exc) == "enrollment_closed":
            raise ValidationError("the Longevity Mothership is not open for new contributors yet", code="ENROLLMENT_CLOSED",
                                  hint="nothing was recorded; try joining again later") from None
        raise ValidationError(f"the relay refused the enrollment code: {relay_error(exc)}", code="ENROLL_FAILED",
                              hint=f"get a new code at {address()}/join (codes are one-time and expire in ~15 minutes)") from None
    if not (reply.get("ok") and reply.get("install_id") and reply.get("token")):
        raise ValidationError("the relay did not return an install id and token", code="ENROLL_FAILED")
    minted = {"install_id": str(reply["install_id"]), "token": str(reply["token"]), "enrolled_at": now().isoformat()}
    keys.hide(minted["token"])
    kept = {k: v for k, v in (install(instance) or {}).items() if k == "contributor_secret"}  # a new code keeps the secret
    _save_install(instance, minted | kept)
    return minted | kept


def _secret(instance: str, found: dict[str, str]) -> str:
    """The contributor secret: 32 random bytes as hex, made at the first join (and after leave --delete)."""
    if "contributor_secret" not in found:
        found["contributor_secret"] = secrets.token_hex(32)
        keys.hide(found["contributor_secret"])
        _save_install(instance, found)
    return found["contributor_secret"]


def enrollment(instance: str) -> dict[str, Any] | None:
    path = folder(instance) / "enrollment.json"
    return files.load_json(path) if path.is_file() else None


def active(instance: str) -> dict[str, Any]:
    """The enrollment, when active and given for the current consent text; raises otherwise."""
    found = enrollment(instance)
    secret = (install(instance) or {}).get("contributor_secret")
    if not consented(found) or secret is None or pseudonym(secret) != found.get("contributor_id"):
        raise NotFound(f"{instance!r} has not joined the Longevity Mothership", code="NOT_ENROLLED",
                       hint=f"plsi mothership join --instance {instance} --kind states --consent-version {current_consent()}")
    if found["consent_version"] != current_consent():
        raise ValidationError("the consent text changed since the user joined", code="CONSENT_OUTDATED",
                              hint=f"show mothership/consent.md {current_consent()} and ask again before sending")
    return found


def join(instance: str, kind: list[str], consent_version: str, code: str | None = None) -> dict[str, Any]:  # noqa: A002
    """`mothership join`: record the user's consent for the kinds they picked. The first join trades the one-time
    code from the relay's /join page for this install's id and token; later joins (other kinds) need no code."""
    store = EventStore(instance)
    if store.subject.relation != Relation.SELF:
        raise ValidationError("only the user's own instance (relation self) can join", code="NOT_SELF",
                              hint="family members and sample people are never shared")
    if consent_version != current_consent():
        raise ValidationError(f"consent version {consent_version} is not the current text", code="CONSENT_OUTDATED",
                              hint="show the current mothership/consent.md and pass its version")
    kinds = sorted({ContributionKind(k).value for k in kind})
    found = _enroll(instance, code) if code else install(instance)  # a code always re-enrolls (new install id)
    if found is None:
        raise ValidationError("the first join needs an enrollment code", code="CODE_REQUIRED",
                              hint=f"the user gets one at {address()}/join and pastes it in chat")
    record = {"contributor_id": pseudonym(_secret(instance, found)), "kinds": kinds, "consent_version": consent_version,
              "joined_at": now().isoformat(), "status": EnrollmentStatus.ACTIVE}
    files.atomic_write_json(folder(instance) / "enrollment.json", record)
    return status(instance)


def leave(instance: str, delete: bool = False, anyway: bool = False) -> dict[str, Any]:
    """`mothership leave`: stop sharing; writes the withdrawal file to send. With --delete it asks to delete
    everything and carries the contributor secret as proof. It waits until the Mother's receipt is in for every sent
    contribution (`plsi mothership receipt`), and the secret moves to `deletion_secret`: a later join is a new
    contributor, and the proof is kept until the withdrawal's receipt says deleted. `anyway` (only after the user
    agreed) sends the deletion while a receipt is still pending; a package that arrives after it is refused."""
    record = enrollment(instance)
    if not record:
        raise NotFound(f"{instance!r} never joined the Longevity Mothership", code="NOT_ENROLLED")
    found = install(instance) or {}
    secret = found.get("contributor_secret")
    if delete and (secret is None or pseudonym(secret) != record["contributor_id"]):
        raise ValidationError("this install no longer holds the secret of its contributor id", code="NO_PROOF",
                              hint="a deletion was already requested; otherwise ask the Mothership steward")
    if delete and not anyway and (waiting := pending(instance, MothershipMessage.CONTRIBUTION)):
        raise ValidationError(f"{len(waiting)} sent contribution(s) have no Mothership receipt yet",
                              code="RECEIPT_PENDING", hint=f"plsi mothership receipt --instance {instance}, then leave "
                                                           "--delete again; --anyway only after the user agreed")
    record |= {"status": EnrollmentStatus.WITHDRAWN, "withdrawn_at": now().isoformat(), "deletion_requested": delete}
    files.atomic_write_json(folder(instance) / "enrollment.json", record)
    message = {"kind": MothershipMessage.WITHDRAWAL, "schema_version": SCHEMA_VERSION,
               "contributor_id": record["contributor_id"],
               "request": WithdrawalRequest.DELETE_ALL if delete else WithdrawalRequest.STOP}
    if delete:
        message["proof"] = secret
    path = folder(instance) / "outbox" / f"withdrawal-{ts_filename()}.json"
    files.atomic_write_json(path, message, private=delete)  # a delete_all carries the contributor secret
    if delete:
        kept = {k: v for k, v in found.items() if k != "contributor_secret"} | {"deletion_secret": secret}
        _save_install(instance, kept)
    return {"file": str(path), "request": message["request"]}


def drop_deletion_secret(instance: str) -> None:
    """The deletion is confirmed: the install no longer keeps the contributor secret as proof."""
    found = install(instance) or {}
    if "deletion_secret" in found:
        _save_install(instance, {k: v for k, v in found.items() if k != "deletion_secret"})


RECEIPT_DAYS = 7  # the relay keeps an ACK this long; a ticket still open after it is never confirmed


def sends(instance: str) -> list[dict[str, Any]]:
    """Every sent message with its receipt state: `stored` or `deleted` (the receipt), `refused` (the code),
    `pending`, `never_confirmed` (no receipt within RECEIPT_DAYS) or `before_receipts` (sent without a ticket)."""
    acks = {a.get("ticket"): a.get("ack") or {} for a in files.read_jsonl(folder(instance) / "acks.jsonl")}
    cutoff = now() - timedelta(days=RECEIPT_DAYS)
    out = []
    for e in files.read_jsonl(folder(instance) / "sent.jsonl"):
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


def pending(instance: str, kind: str | None = None) -> list[dict[str, Any]]:
    """Sent messages with a relay ticket and no Mother receipt yet, sent within RECEIPT_DAYS."""
    return [e for e in sends(instance)
            if e["receipt_state"] == ReceiptState.PENDING and (kind is None or e.get("kind") == kind)]


def status(instance: str) -> dict[str, Any]:
    """`mothership status`: enrollment, whether its consent is current, the address and what was sent."""
    record, found, log = enrollment(instance), install(instance), sends(instance)
    return {"instance": instance, "enrolled": consented(record),
            "enrollment": record, "consent_version": current_consent(),
            "consent_current": bool(record and record["consent_version"] == current_consent()),
            "to": address(), "join_page": f"{address()}/join", "has_install_token": found is not None,
            "has_contributor_secret": "contributor_secret" in (found or {}),
            "deletion_proof_held": "deletion_secret" in (found or {}),
            "sent_count": len(log), "sent": [{k: v for k, v in e.items() if k != "reply"} for e in log[-12:]],
            "receipts_pending": sum(e["receipt_state"] == ReceiptState.PENDING for e in log)}
