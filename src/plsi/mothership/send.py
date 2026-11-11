"""Sending a gate-checked file to the Mothership relay, logged in sent.jsonl: contributor files with the instance's
install token (<instance>/mothership/), professional files with the professional token (<PLSI_HOME>/mothership/).
The relay's `ticket` later fetches the Mother's own receipt (`receipt`, into acks.jsonl). Research notes and feedback
go by email, never to the relay."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from plsi import files
from plsi.clock import now
from plsi.errors import NetworkError, UsageError
from plsi.mothership import gate, professional, scan
from plsi.mothership.enroll import bearer, folder, forget_install, pending, sends
from plsi.mothership.relay import MAX_REPLY, MAX_WAIT_S, POLL_S, address, post, refused
from plsi.vocab import MothershipMessage, ProfessionalScope, ReceiptState, WithdrawalRequest

EMAIL_ONLY = {  # kind -> (refusal, hint)
    MothershipMessage.RESEARCH_NOTE: ("research notes go to the Mothership by email, signed by the sender's address",
                                      "plsi mothership email --file <file>"),
    MothershipMessage.FEEDBACK: ("feedback goes to the Mothership by email", "plsi feedback report --file <draft>")}
# fields that change without the data changing: the month it was packed and the PLSI release that packed it
STAMPS = ("packed", "plsi_version")


def _channel(instance: str | None) -> tuple[str | None, Path]:
    """(token, folder of sent.jsonl and acks.jsonl): the instance's install, else the professional's."""
    return (bearer(instance), folder(instance)) if instance else (professional.token(), professional.folder())


def _sender(doc: Any, instance: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """(instance, professional token payload): exactly one of them names the sender of `doc`."""
    kind = doc.get("kind") if isinstance(doc, dict) else None
    if kind in EMAIL_ONLY:
        raise UsageError(EMAIL_ONLY[kind][0], code="EMAIL_ONLY", hint=EMAIL_ONLY[kind][1])
    if kind in gate.PROFESSIONAL and instance:
        raise UsageError(f"a {kind} is a professional message; send it without --instance")
    if instance or kind not in gate.PROFESSIONAL:
        return instance, None
    return None, professional.payload(ProfessionalScope.FINDINGS_SUBMIT)


def _gated(file: str, instance: str | None, expected: str | None = None) -> tuple[Any, str | None]:
    """The file and its sending instance (None for a professional's file), once the file passed the gate."""
    doc = scan.load(file)
    gate.approved(doc, expected)
    instance, token = _sender(doc, instance)
    gate.require(doc, instance, pid=token["pid"] if token else None)
    return doc, instance


def check(file: str, instance: str | None = None, expected: str | None = None) -> dict[str, Any]:
    """`mothership check`: run the gate on a file without sending or logging it; `nothing_new` when the same data
    (stamps aside: the month packed, the PLSI version) was stored or is pending."""
    doc, inst = _gated(file, instance, expected)
    return {"file": file, "ok": True, "to": address(), "package_hash": files.hash_json(doc),
            "nothing_new": bool(inst) and _repeat(inst, doc) is not None}


def send(file: str, expected: str, instance: str | None = None) -> dict[str, Any]:
    """`mothership send`: gate-check the approved file (`expected`, its package_hash), POST it to the relay with the
    sender's token and log it with the reply and ticket; not logged when refused, never retried."""
    doc, instance = _gated(file, instance, expected)
    token, base = _channel(instance)
    if instance:
        _not_again(instance, doc)
    try:
        reply = post("/relay", doc, token)
    except NetworkError as exc:
        raise refused(exc, "file") from None
    entry = {"sent_at": now().isoformat(), "file": file, "kind": doc["kind"], "to": address(),
             "package_hash": files.hash_json(doc), "data_hash": data_hash(doc), "kinds": doc.get("kinds", []), "request": doc.get("request"),
             "id": doc.get("preregistration_id") if doc["kind"] == MothershipMessage.PREREGISTRATION else doc.get("finding_id"),
             "ticket": reply.get("ticket") if isinstance(reply, dict) else None,
             "reply": reply if isinstance(reply, dict) else {"text": str(reply)[:MAX_REPLY]}}
    entry = {k: v for k, v in entry.items() if v not in (None, [])}
    files.append_jsonl(base / "sent.jsonl", entry)
    return entry


def data_hash(doc: dict[str, Any]) -> str:
    """The contribution's data, without its stamps: the same states and events packed next month or by a newer PLSI
    are the same data, so they are never sent, and stored, twice."""
    return files.hash_json({k: v for k, v in doc.items() if k not in STAMPS})


def _repeat(instance: str, doc: dict[str, Any]) -> dict[str, Any] | None:
    """The earlier send of the same contribution data that the Mother stored or still has pending, or None; one that
    was refused, never confirmed or sent before receipts does not count."""
    if doc.get("kind") != MothershipMessage.CONTRIBUTION:
        return None
    digest = data_hash(doc)
    return next((e for e in sends(folder(instance)) if e.get("data_hash") == digest
                 and e["receipt_state"] in (ReceiptState.STORED, ReceiptState.PENDING)), None)


def _not_again(instance: str, doc: dict[str, Any]) -> None:
    """The same contribution data twice: refused when the Mother already stored it or its receipt is pending."""
    if (e := _repeat(instance, doc)) is not None:
        if e["receipt_state"] == ReceiptState.STORED:
            raise UsageError("the Mothership already stored this data", code="ALREADY_STORED",
                             hint=f"receipt {e.get('receipt')}; nothing new to send")
        raise UsageError("this data was sent and its receipt is pending", code="ALREADY_SENT",
                         hint=f"plsi mothership receipt --instance {instance} --wait 120")


def receipt(instance: str | None = None, wait: int = 0) -> dict[str, Any]:
    """`mothership receipt`: ask the relay for the Mother's receipt of every sent message without one, keep each in
    acks.jsonl and list done, refused and pending; `wait` seconds (at most MAX_WAIT_S) keeps asking every POLL_S. A
    confirmed delete_all drops the proof from the withdrawal file and forgets the install."""
    deadline = time.monotonic() + max(0, min(wait, MAX_WAIT_S))
    out = _receipt_once(instance)
    while out["pending"] and time.monotonic() + POLL_S <= deadline:
        time.sleep(POLL_S)
        more = _receipt_once(instance)
        out = {"done": out["done"] + more["done"], "refused": out["refused"] + more["refused"], "pending": more["pending"]}
    return out


def _receipt_once(instance: str | None) -> dict[str, Any]:
    token, base = _channel(instance)
    out: dict[str, list[dict[str, Any]]] = {"done": [], "refused": [], "pending": []}
    for entry in pending(base):
        try:
            reply = post("/ack", {"ticket": entry["ticket"]}, token)
        except NetworkError as exc:
            raise refused(exc, "receipt request") from None
        line = {"kind": entry["kind"], "sent_at": entry["sent_at"], "ticket": entry["ticket"]}
        if not isinstance(reply, dict) or reply.get("status") != "done":
            out["pending"].append(line)
            continue
        ack = reply.get("ack") if isinstance(reply.get("ack"), dict) else {}
        files.append_jsonl(base / "acks.jsonl", line | {"at": now().isoformat(), "ack": ack})
        out["done" if ack.get("ok") else "refused"].append(line | {"ack": ack})
        deleted = ack.get("ok") and ack.get("status") == "deleted"
        if instance and deleted and entry.get("request") == WithdrawalRequest.DELETE_ALL:
            _drop_proof(instance, entry.get("file"))
            break  # the relay retires this install once it reads the deletion: nothing more to ask with its token
    return out


def _drop_proof(instance: str, file: str | None) -> None:
    """The deletion is confirmed: the contributor secret is no longer needed anywhere."""
    if file and file != "-" and Path(file).is_file():
        doc = files.load_json(file)
        files.atomic_write_json(Path(file), {k: v for k, v in doc.items() if k != "proof"})
    forget_install(instance)
