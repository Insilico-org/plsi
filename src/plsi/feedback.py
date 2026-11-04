"""`plsi feedback`: timed setup stages and the usage report for the PLSI team, sent by email (WIRE §8)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from plsi import files, paths, references, role
from plsi.clock import now, parse_time
from plsi.errors import UsageError, ValidationError
from plsi.mothership import gate
from plsi.mothership.relay import SCHEMA_VERSION
from plsi.vocab import FeedbackMark, FeedbackStage, MothershipMessage

ADDRESS = "longevity_mothership_feedback"
MARKS = (*FeedbackStage, *FeedbackMark)
SUBJECT = "PLSI feedback:"
LABELS = {"install": "Install and environment", "team": "Identity, persona and core team", "choices": "Setup choices",
          "interview": "Onboarding interview", "specialists": "Specialists", "connectors": "Evipedia connector",
          "instance": "Your record", "routines": "Check-in, digest and routines", "mothership": "Longevity Mothership",
          "welcome": "Welcome", "records": "Sending records", "plans": "Plans", "research": "Research",
          "other": "Other"}


def _folder() -> Path:
    return paths.plsi_home() / "feedback"


def _timeline() -> Path:
    return _folder() / "timeline.jsonl"


def mark(stage: str, at: datetime | None = None) -> dict[str, Any]:
    """`feedback mark`: the start of a setup stage (`done` ends the last one); `install` starts a new run."""
    if stage not in MARKS:
        raise UsageError(f"stage must be one of {', '.join(MARKS)}")
    entry = {"stage": stage, "at": (at or now()).isoformat(timespec="seconds")}
    files.append_jsonl(_timeline(), entry)
    return entry


def _run() -> list[dict[str, Any]]:
    marks = files.read_jsonl(_timeline()) if _timeline().is_file() else []
    starts = [n for n, m in enumerate(marks) if m["stage"] == FeedbackStage.INSTALL]
    return marks[starts[-1]:] if starts else marks


def timeline() -> dict[str, Any]:
    """`feedback timeline`: minutes per stage of the last setup run; the open stage is not counted."""
    marks, seconds = _run(), {}
    for a, b in zip(marks, marks[1:]):
        if a["stage"] != FeedbackMark.DONE:
            span = (parse_time(b["at"]) - parse_time(a["at"])).total_seconds()
            seconds[a["stage"]] = seconds.get(a["stage"], 0) + max(span, 0)
    stages = [{"stage": s, "minutes": min(round(seconds[s] / 60), gate.MAX_MINUTES), "measured": True}
              for s in FeedbackStage if s in seconds]
    return {"started_at": marks[0]["at"] if marks else None, "done": bool(marks) and marks[-1]["stage"] == FeedbackMark.DONE,
            "open": marks[-1]["stage"] if marks and marks[-1]["stage"] != FeedbackMark.DONE else None, "stages": stages}


def _markdown(doc: dict[str, Any], day: str | None = None) -> str:
    title = f"# PLSI usage report, {day}" if day else "# PLSI usage report"
    lines = [title, "", f"Role: {doc['role']}", "", "## Time per stage", ""]
    if doc["stages"]:
        lines += ["| Stage | Minutes | How |", "|---|---|---|"]
        lines += [f"| {LABELS[e['stage']]} | {e['minutes']} | {'timed' if e['measured'] else 'estimated'} |"
                  for e in doc["stages"]]
        lines.append(f"\nTotal: {sum(e['minutes'] for e in doc['stages'])} minutes")
    else:
        lines.append("Not timed.")
    lines += ["", "## Points of frustration", ""]
    lines += [f"- **{LABELS[e['stage']]}** ({e['severity']}): {e['what']}" for e in doc["frustrations"]] or ["None."]
    lines += ["", "## Suggested improvements", ""]
    lines += [f"- **{LABELS[e['stage']]}**: {e['what']}" for e in doc["suggestions"]] or ["None."]
    return "\n".join(lines) + "\n"


def _email(doc: dict[str, Any]) -> dict[str, str] | None:
    to = references.get(ADDRESS).email
    if not to:
        return None
    n, m = len(doc["frustrations"]), len(doc["suggestions"])
    subject = f"{SUBJECT} {n} frustration{'s' * (n != 1)}, {m} suggestion{'s' * (m != 1)}"
    body = "\n\n".join(["A usage report from PLSI, sent by its user to the PLSI team.", _markdown(doc).strip(),
                        "```plsi\n" + json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n```"])
    return {"to": to, "subject": subject, "body": body}


def check(file: str) -> dict[str, Any]:
    """`feedback check`: the gate on a written report, and its email draft."""
    doc = files.load_json(file)
    if not isinstance(doc, dict) or doc.get("kind") != MothershipMessage.FEEDBACK:
        raise UsageError("not a feedback report", hint="plsi feedback report --file <draft>")
    gate.require(doc, None, what="feedback report")
    return {"file": file, "email": _email(doc), "package_hash": files.hash_json(doc)}


def report(file: str) -> dict[str, Any]:
    """`feedback report`: the draft plus measured times -> .json and .md copies stamped to the second (a later report
    never overwrites an earlier one) and the email."""
    draft = files.load_json(file)
    if not isinstance(draft, dict) or not set(draft) <= {"frustrations", "suggestions", "stages"}:
        raise ValidationError("the draft holds frustrations, suggestions and optional estimated stages only",
                              code="BAD_DRAFT")
    measured = timeline()["stages"]
    timed = {e["stage"] for e in measured}
    estimated = [{**e, "measured": False} if isinstance(e, dict) else e for e in draft.get("stages") or []
                 if not (isinstance(e, dict) and e.get("stage") in timed)]
    doc = {"kind": MothershipMessage.FEEDBACK.value, "schema_version": SCHEMA_VERSION, "role": role.show()["role"],
           "stages": measured + estimated, "frustrations": draft.get("frustrations") or [],
           "suggestions": draft.get("suggestions") or []}
    gate.require(doc, None, what="feedback report")
    day = now()
    stem = _folder() / f"usage-report_{day.strftime('%Y%m%d-%H%M%S')}"
    text = _markdown(doc, day.date().isoformat())
    files.atomic_write_json(stem.with_suffix(".json"), doc)
    files.atomic_write_text(stem.with_suffix(".md"), text)
    out = {"file": str(stem.with_suffix(".json")), "report": str(stem.with_suffix(".md")), "email": _email(doc),
           "frustrations": len(doc["frustrations"]), "suggestions": len(doc["suggestions"]),
           "package_hash": files.hash_json(doc)}
    if out["email"] is None:
        out["hint"] = f"the feedback address is not set: email in mothership/references/contact.yaml:{ADDRESS}"
    return out
