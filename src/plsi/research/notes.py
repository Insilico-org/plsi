"""The research note: the unit PLSI Challenger evaluates and the Longevity Mothership receives.

Notes live in their project's notes/ (<PLSI_HOME>/research/projects/<project>/notes/), and every note names that
project in its frontmatter; a note may also name its `topic`, a topic of the same project. Notes link to other
notes of their project: `builds_on` (uses their findings), `supersedes` (replaces an older note, which keeps its
status) and `contradicts`. The loop never cites a note, and a note's `grade` is its author's judgment, not a
computed verdict.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import NotFound, UsageError, ValidationError
from plsi.research import projects, store
from plsi.vocab import EvidenceClass, MothershipMessage
from plsi.vocab.research import ResearchNoteStatus as Status

KIND = MothershipMessage.RESEARCH_NOTE.value  # the frontmatter `kind` of a note: the same word as on the wire
NEW = (Status.ACTIVE, Status.READY)  # the statuses a note is written with
# the status a note may move to, from which: back to active to revise it (after Challenger's "not yet" or a
# rejection); submitted again when a refused email is sent again; retire from any status, with a reason
MOVES = {Status.ACTIVE: {Status.READY, Status.REJECTED}, Status.READY: {Status.ACTIVE},
         Status.SUBMITTED: {Status.ACTIVE, Status.READY, Status.SUBMITTED},
         Status.ACCEPTED: {Status.SUBMITTED}, Status.REJECTED: {Status.SUBMITTED}, Status.RETIRE: set(Status)}
DECIDED = (Status.ACCEPTED, Status.REJECTED)
SENT = (Status.SUBMITTED, Status.ACCEPTED, Status.REJECTED)
LINKS = ("builds_on", "supersedes", "contradicts")  # supersedes names one note, the others a list
UNREADABLE = "unreadable"  # the status a note whose frontmatter does not parse is listed with
NEXT_STEP = re.compile(r"^\s*-\s*Next step:\s*(.+?)\s*$", re.MULTILINE)


def _folder(pid: str) -> Path:
    return projects.folder(pid) / store.NOTES_FOLDER


def _links(meta: dict[str, Any]) -> dict[str, list[str]]:
    """A note's links as lists of note names: `supersedes` names one, the others a list."""
    out = {}
    for key in LINKS:
        given = meta.get(key)
        out[key] = [] if given in (None, "", []) else [given] if isinstance(given, str) else given
    return out


def _read(path: Path, pid: str) -> dict[str, Any] | None:
    """One note, or None for a file whose frontmatter does not name the note kind. A note whose frontmatter does not
    parse is listed with status `unreadable` and the error, so one broken file never hides the others."""
    base = {"project": pid, "name": path.stem, "path": str(path)}
    try:
        meta, body = store.read_md(path)
    except ValidationError as exc:
        return {**base, "topic": None, "title": path.stem, "status": UNREADABLE, "error": exc.message,
                "hint": f"plsi research check --name {path.stem} --project {pid}"}
    if meta.get("kind") != KIND:
        return None
    return {**base, "topic": meta.get("topic"), "title": meta.get("title") or path.stem,
            "status": meta.get("status"), "grade": meta.get("grade"), "evidence_class": meta.get("evidence_class"),
            "sources": meta.get("sources") or [], "updated": meta.get("updated"), **_links(meta),
            "retire_reason": meta.get("retire_reason"), "decision_reason": meta.get("decision_reason"),
            "next_steps": NEXT_STEP.findall(body), "lines": len(body.splitlines())}


def _notes(pid: str) -> list[dict[str, Any]]:
    folder = _folder(pid)
    found = sorted(p for p in folder.glob("*.md") if p.name != store.RETIRED) if folder.is_dir() else []
    return [n for n in (_read(p, pid) for p in found) if n]


def list_notes(topic: str | None = None, status: str | None = None,
               project: str | None = None) -> list[dict[str, Any]]:
    """`research notes`: the notes of one project, or of every project when none is named, filtered by topic and
    status; each names its project."""
    pids = [projects.resolve(project)["id"]] if project else [m["id"] for m in projects.every()]
    return [n for pid in pids for n in _notes(pid) if status in (None, n["status"]) and topic in (None, n["topic"])]


def _named(name: str, project: str | None = None) -> dict[str, Any]:
    """The note called `name`, in the project named, else in whichever project holds it; a name two projects use
    needs --project."""
    hits = [n for n in list_notes(project=project) if n["name"] == name]
    if len(hits) > 1:
        raise UsageError(f"{len(hits)} projects have a note {name!r}: name one with --project", code="PROJECT_REQUIRED",
                         hint="plsi research notes")
    if not hits:
        raise NotFound(f"no research note {name!r}", hint="plsi research notes")
    return hits[0]


def _link_violations(meta: dict[str, Any], name: str, pid: str) -> list[str]:
    """Links that are not note names of the same project, or that point at the note itself."""
    out = []
    if isinstance(meta.get("supersedes"), list):
        out.append("supersedes: one note name")
    for key in ("builds_on", "contradicts"):
        if meta.get(key) not in (None, "", []) and not isinstance(meta.get(key), list):
            out.append(f"{key}: a list of note names")
    names = {n["name"] for n in _notes(pid)}
    for key, targets in _links(meta).items():
        for target in targets:
            if not isinstance(target, str) or target == name:
                out.append(f"{key}: {target!r} is not another note")
            elif target not in names:
                out.append(f"{key}: no note {target!r} in this project (plsi research notes --project {pid})")
    return out


def _violations(meta: dict[str, Any], body: str, name: str, pid: str) -> list[str]:
    """What a note's frontmatter and body break; empty when the commands can read it."""
    out = []
    if meta.get("kind") != KIND:
        out.append(f"kind: must be {KIND}")
    for key in ("title", "grade"):
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            out.append(f"{key}: a non-empty line of text")
    if meta.get("status") not in tuple(Status):
        out.append(f"status: one of {', '.join(Status)}")
    if meta.get("evidence_class") not in tuple(EvidenceClass):
        out.append(f"evidence_class: one of {', '.join(EvidenceClass)}")
    sources = meta.get("sources")
    if not isinstance(sources, list) or not sources or not all(
            isinstance(x, str) and ":" in x and all(part.strip() for part in x.split(":", 1)) for x in sources):
        out.append("sources: a list of <kind>:<id>, at least one")
    if not str(meta.get("updated") or "").strip():
        out.append("updated: the date, YYYY-MM-DD")
    if meta.get("project") != pid:
        out.append(f"project: must be {pid}, the project whose notes/ holds it")
    if meta.get("topic") and str(meta["topic"]) not in projects.topics_of(pid):
        out.append(f"topic: no research topic {meta['topic']!r} in this project (plsi research topic)")
    if not body.strip():
        out.append("body: the note itself, below the frontmatter")
    return out + _link_violations(meta, name, pid)


def check(name: str, project: str | None = None) -> dict[str, Any]:
    """`research check`: whether a note parses, has every field the commands read, belongs to its folder's project
    and links only to notes of that project. Run after writing or editing one; a note with violations goes nowhere
    until it passes."""
    note = _named(name, project)
    try:
        meta, body = store.read_md(Path(note["path"]))
    except ValidationError as exc:
        return {"name": name, "project": note["project"], "ok": False, "violations": [exc.message]}
    found = _violations(meta, body, name, note["project"])
    return {"name": name, "project": note["project"], "ok": not found, "violations": found,
            "status": meta.get("status")}


def mark(name: str, status: str, reason: str | None = None, project: str | None = None) -> dict[str, Any]:
    """`research mark`: set a note's status and `updated`, only along MOVES (accepted or rejected only after
    submitted); retire needs a reason, and the Mothership's reason for accepted or rejected is kept as
    `decision_reason`. The body and every other field stay as written."""
    note, to = _named(name, project), Status(status)
    if note["status"] not in MOVES[to]:
        raise UsageError(f"{name!r} is {note['status']!r}; it cannot become {to.value!r}",
                         hint=f"allowed from: {', '.join(sorted(MOVES[to]))}")
    if to == Status.RETIRE and not reason:
        raise UsageError("a note is retired with a reason",
                         hint=f"plsi research mark --name {name} --status retire --reason '<why>'")
    path = Path(note["path"])
    with store.locked(projects.folder(note["project"])):
        meta, body = store.read_md(path)
        kept = {"retire_reason": reason} if to == Status.RETIRE else {"decision_reason": reason} if to in DECIDED else {}
        meta.update(status=to.value, updated=store.today(), **{k: v for k, v in kept.items() if v})
        files.atomic_write_text(path, store.render(meta, body))
    return {"name": name, "project": note["project"], "from": note["status"], "status": to.value}


def retire(name: str, topic: str | None = None, reason: str = "", project: str | None = None) -> dict[str, Any]:
    """`research retire`: log one note marked `retire` in its project's `retired.md`, then remove it, so a note is
    never gone without its line; run again after a failure, it logs the note once. Nothing else in research is
    ever deleted."""
    note = _named(name, project)
    if topic not in (None, note["topic"]):
        raise NotFound(f"no research note {name!r} in topic {topic!r}", hint="plsi research notes")
    if note["status"] != Status.RETIRE:
        raise UsageError(f"{name!r} has status {note['status']!r}; only a note marked retire is removed",
                         hint=f"plsi research mark --name {name} --status retire --reason '<why>'")
    log, tag = _folder(note["project"]) / store.RETIRED, f"[{name}]"
    with store.locked(projects.folder(note["project"])):
        append_retired(log, {tag: f"- {store.today()} {tag} {note['title']}: "
                                  f"{reason or note['retire_reason'] or 'no reason given'}"})
        Path(note["path"]).unlink()
    return {"retired": name, "project": note["project"], "topic": note["topic"], "logged_in": str(log)}


def append_retired(log: Path, entries: dict[str, str]) -> None:
    """Append to a retirement log, made with its heading, each line whose key the log does not hold yet. The caller
    holds the project's lock."""
    prior = log.read_text(encoding="utf-8") if log.is_file() else "# Retired research notes\n\n"
    files.atomic_write_text(log, prior + "".join(f"{line}\n" for key, line in entries.items() if key not in prior))
