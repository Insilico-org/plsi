"""The research note: the unit PLSI Challenger evaluates and the Longevity Mothership receives.

Notes live in `<PLSI_HOME>/research/notes/`, beside the topics, so a session with no research topic can still
file one. A note names its `topic` in frontmatter when it has one. The loop never cites a note, so removing a
retired one cannot break a link, and a note's `grade` is its author's judgment, not a computed verdict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files, paths
from plsi.errors import NotFound, UsageError
from plsi.research import store
from plsi.vocab.research import ResearchNoteStatus

RETIRED = "retired.md"
KIND = "note"  # the frontmatter `kind` that marks a file in the folder as a note


def _folder() -> Path:
    return store.root() / store.NOTES_FOLDER


def _read(path: Path) -> dict[str, Any]:
    meta, body = store.parse(path.read_text(encoding="utf-8"))
    return {"topic": meta.get("topic"), "name": path.stem, "title": meta.get("title") or path.stem,
            "status": meta.get("status"), "grade": meta.get("grade"), "evidence_class": meta.get("evidence_class"),
            "sources": meta.get("sources") or [], "updated": meta.get("updated"),
            "retire_reason": meta.get("retire_reason"), "path": str(path), "lines": len(body.splitlines())}


def _paths() -> list[Path]:
    """The notes in the folder: Markdown files whose frontmatter says `kind: note`."""
    folder = _folder()
    found = sorted(p for p in folder.glob("*.md") if p.name != RETIRED) if folder.is_dir() else []
    return [p for p in found if store.parse(p.read_text(encoding="utf-8"))[0].get("kind") == KIND]


def list_notes(topic: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    """`research notes`: every research note, filtered by topic and status. Notes without a topic are listed
    unless a topic is named."""
    notes = [_read(p) for p in _paths()]
    return [n for n in notes if status in (None, n["status"]) and topic in (None, n["topic"])]


def retire(name: str, topic: str | None = None, reason: str = "") -> dict[str, Any]:
    """`research retire`: remove one note marked `retire` and log it in `retired.md`. Nothing else in research
    is ever deleted."""
    path = paths.safe_join(_folder(), f"{name}.md")
    note = _read(path) if path in {p.resolve() for p in _paths()} else None
    if note is None or topic not in (None, note["topic"]):
        raise NotFound(f"no research note {name!r}", hint="plsi research notes --status retire")
    if note["status"] != ResearchNoteStatus.RETIRE:
        raise UsageError(f"{name!r} has status {note['status']!r}; only a note marked retire is removed",
                         hint="the owner sets status: retire and retire_reason first")
    path.unlink()
    log = _folder() / RETIRED
    prior = log.read_text(encoding="utf-8") if log.is_file() else "# Retired research notes\n\n"
    files.atomic_write_text(log, prior + f"- {store.today()} {note['title']}: "
                                        f"{reason or note['retire_reason'] or 'no reason given'}\n")
    return {"retired": name, "topic": note["topic"], "logged_in": str(log)}
