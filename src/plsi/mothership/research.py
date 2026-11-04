"""Research notes and registry updates for the Longevity Mothership: the message built from PLSI Explorer's
contribution.json (skills/explorer/mothership), gate-checked into the instance's outbox. A registry update goes with
plsi mothership send; a research note only by email (WIRE §7), drafted here for the user's Grok email."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files, paths, references
from plsi.clock import ts_filename
from plsi.errors import UsageError, ValidationError
from plsi.mothership import attach, gate, note as note_rules, scan
from plsi.mothership.enroll import folder
from plsi.mothership.note import FINDINGS
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
           **{k: given[k] for k in sorted(gate.FIELDS[kind][0] | gate.FIELDS[kind][1])
              if k in given and k != "files"}}  # "to" and "consent" stay local
    mail: dict[str, bytes] = {}
    if "files" in given:
        if kind != MothershipMessage.RESEARCH_NOTE:
            raise ValidationError("only a research note carries files", code="BAD_CONTRIBUTION")
        doc["files"], mail = attach.prepare(given["files"], gate.instance_names(instance))
    doc, removed = scan.strip_pictures(doc)  # the author's own draft: a hidden picture goes, the text stays
    gate.require(doc, instance, what=given["kind"].replace("_", " "))
    path = folder(instance) / "outbox" / f"{given['kind'].replace('_', '-')}-{ts_filename()}.json"
    bundle = attach.zip_bytes(mail) if mail else None  # too large raises before anything is written
    if bundle is not None:
        files.atomic_write_bytes(path.with_suffix(".zip"), bundle)  # the zip first: a note never sits without it
    files.atomic_write_json(path, doc)
    out = {"file": str(path), "kind": kind.value, "items": len(doc.get("items") or []), "pictures_removed": removed,
           "files": len(doc.get("files") or []), "package_hash": files.hash_json(doc)}
    return out | ({"bundle": str(path.with_suffix(".zip"))} if mail else {})


def _item(item: dict[str, Any]) -> str:
    sources = ", ".join(f"{s.get('kind')} {s.get('id')}" for s in item.get("sources") or [])
    lines = [f"Question: {item['question']}"] if item.get("question") else []
    lines += [f"Claim: {item.get('claim')}", f"Grade: {item.get('grade')} ({item.get('evidence_class')})",
              f"Sources: {sources or 'none'}"]
    for key in FINDINGS:
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
    to = references.get(RESEARCH_ADDRESS).email
    if not to:
        raise ValidationError("the Mothership research address is not set", code="NO_RESEARCH_ADDRESS",
                              hint=f"email in mothership/references/contact.yaml:{RESEARCH_ADDRESS}")
    by_email = note_rules.by_email(doc)
    if by_email:
        attach.verify(Path(file).with_suffix(".zip"), by_email)
    on_drive = [e["name"] for e in doc.get("files") or [] if "drive_id" in e]
    claim = str(doc["items"][0].get("claim") or "research note")
    subject = "PLSI research note: " + (claim if len(claim) <= 80 else claim[:79].rstrip() + "…")
    body = "\n\n".join(["A research note from PLSI, sent by its author for review by the Longevity Mothership.",
                         *(_item(i) for i in doc["items"]), f"Method: {doc['method']}",
                         *([f"Data files attached as a zip: {', '.join(e['name'] for e in by_email)}."] if by_email else []),
                         *([f"Data files on Google Drive, shared with the Mothership: {', '.join(on_drive)}."]
                           if on_drive else []),
                         "The note itself is attached as JSON"
                         + (", the full report as markdown." if doc.get("report") else ".")])
    out = {"to": to, "subject": subject, "body": body, "attachment": str(Path(file).resolve()),
           "items": len(doc["items"]), "package_hash": files.hash_json(doc)}
    if by_email:
        out["bundle"] = str(Path(file).resolve().with_suffix(".zip"))
    if doc.get("report"):
        report = Path(file).resolve().with_suffix(".report.md")
        files.atomic_write_text(report, doc["report"])
        out["report"] = str(report)
    return out
