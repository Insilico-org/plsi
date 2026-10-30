"""Research notes and registry updates for the Longevity Mothership: the message built from PLSI Explorer's
contribution.json (skills/explorer/mothership), gate-checked into the instance's outbox. A registry update goes with
plsi mothership send; a research note only by email (WIRE §7), drafted here for the user's Grok email."""

from __future__ import annotations

from typing import Any

import json

from plsi import files, paths, references
from plsi.clock import ts_filename
from plsi.errors import UsageError, ValidationError
from plsi.mothership import gate, scan
from plsi.mothership.enroll import folder
from plsi.mothership.relay import SCHEMA_VERSION
from plsi.vocab import MothershipMessage, NoteKind

RESEARCH_ADDRESS = "longevity_mothership_research"
MESSAGES = {NoteKind.RESEARCH_NOTE: MothershipMessage.RESEARCH_NOTE, NoteKind.REGISTRY_UPDATE: MothershipMessage.REGISTRY_UPDATE}


def note(instance: str, file: str) -> dict[str, Any]:
    """`mothership note`: a plsi_research_note (items, method) or plsi_registry_update (items); nothing is sent."""
    paths.instance_dir(instance)
    given = files.load_json(file)
    if not isinstance(given, dict) or given.get("kind") not in tuple(NoteKind):
        raise ValidationError(f"contribution.json kind must be one of {', '.join(NoteKind)}", code="BAD_CONTRIBUTION")
    kind = MESSAGES[NoteKind(given["kind"])]
    doc = {"kind": kind.value, "schema_version": SCHEMA_VERSION,
           **{k: given[k] for k in sorted(gate.FIELDS[kind][0]) if k in given}}  # "to" and "consent" stay local
    gate.require(doc, instance, what=given["kind"].replace("_", " "))
    path = folder(instance) / "outbox" / f"{given['kind'].replace('_', '-')}-{ts_filename()}.json"
    files.atomic_write_json(path, doc)
    return {"file": str(path), "kind": kind.value, "items": len(doc.get("items") or []), "package_hash": files.hash_json(doc)}


def _item(item: dict[str, Any]) -> str:
    sources = ", ".join(f"{s.get('kind')} {s.get('id')}" for s in item.get("sources") or [])
    return "\n".join([f"Claim: {item.get('claim')}", f"Grade: {item.get('grade')} ({item.get('evidence_class')})",
                      f"Sources: {sources or 'none'}", f"Falsified by: {item.get('falsified_by')}",
                      f"Next step: {item.get('next_step')}"])


def email(file: str) -> dict[str, Any]:
    """`mothership email`: the email for a gate-checked research note (WIRE §7): the address, the subject and a body
    with the note in plain words and the message in one ```plsi block. Nothing is sent; the user's Grok email sends it."""
    doc = scan.load(file)
    if not isinstance(doc, dict) or doc.get("kind") != MothershipMessage.RESEARCH_NOTE:
        raise UsageError("only a research note goes by email", hint="plsi mothership note --instance <i> --file contribution.json")
    gate.require(doc, None, what="research note")
    to = references.get(RESEARCH_ADDRESS).email
    if not to:
        raise ValidationError("the Mothership research address is not set", code="NO_RESEARCH_ADDRESS",
                              hint=f"email in mothership/references/contact.yaml:{RESEARCH_ADDRESS}")
    claim = str(doc["items"][0].get("claim") or "research note")
    subject = "PLSI research note: " + (claim if len(claim) <= 80 else claim[:79].rstrip() + "…")
    body = "\n\n".join(["A research note from PLSI, sent by its author for review by the Longevity Mothership.",
                         *(_item(i) for i in doc["items"]), f"Method: {doc['method']}",
                         "```plsi\n" + json.dumps(doc, ensure_ascii=False, indent=2) + "\n```"])
    return {"to": to, "subject": subject, "body": body, "items": len(doc["items"]), "package_hash": files.hash_json(doc)}
