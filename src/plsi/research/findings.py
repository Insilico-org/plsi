"""A project's findings doc, research/projects/<project>/findings.md: rebuilt from the graph at the end of every
research run, for the project's room to read. Generated and overwritten, never edited: it is not a research note
(those are in notes/, written by a bot), and the loop still writes no notes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files
from plsi.research import status as views
from plsi.research import store
from plsi.research.store import clip
from plsi.research.verdict import question_verdict
from plsi.vocab.research import ResearchNodeKind

FINDINGS_FILE = "findings.md"
REASON_CHARS = 300  # of a closed direction's reason or answer


def rebuild(directory: Path) -> Path:
    """Write the project's findings.md: its aim, then each topic (the active one first) with its question, the
    answer so far, every direction with its verdict and sources, what is open and what comes next."""
    meta = store.read_md(directory / store.PROJECT_FILE)[0]
    active = store.active_name(directory, required=False)
    names = sorted(store.list_topics(directory), key=lambda n: n != active)
    out = [f"# {meta.get('title')}", "", *([str(meta["aim"]), ""] if meta.get("aim") else []),
           "Rebuilt by PLSI at the end of each research run; edits here are overwritten.", ""]
    for name in names:
        out += _topic(name, name == active)
    if not names:
        out.append("No topic yet.")
    path = directory / FINDINGS_FILE
    with store.locked(directory):
        files.atomic_write_text(path, "\n".join(out).rstrip() + "\n")
    return path


def _topic(name: str, active: bool) -> list[str]:
    view, graph = views.status(topic=name), store.load(name)
    answer = view.get("answer")
    out = [f"## {name}" + (" (active)" if active else f" ({view['status']})"), "",
           f"Question: {view['question_in_chief']}",
           f"Depth: {view['depth']}; an answer must reach {view['answer_must_reach']}.", "",
           f"Answer so far ({view['verdict']}): {answer['answer']}" if answer else "Answer so far: none yet.", "",
           "### Directions", ""]
    questions = sorted(graph.of_kind(ResearchNodeKind.QUESTION),
                       key=lambda q: list(reversed(graph.ancestry(q["name"]))))  # each under its parent
    for q in questions:
        out += _direction(graph, q)
    if not questions:
        out.append("None opened yet.")
    out += ["", "### Open", ""]
    out += [f"- {e['question']}: {e['why']}" for e in view["frontier"]] or ["Nothing is open."]
    cursor = view.get("cursor") or {}
    out += ["", "### Next", ""]
    if active and view["frontier"]:
        out.append(f"{cursor.get('move') or 'ask'} on {cursor.get('question') or 'a new direction'}.")
    elif view["continue_with"]:
        out += [f"- {c['ask']} ({c['why']})" for c in view["continue_with"]]
    else:
        out.append("Nothing is planned: the user decides whether this topic continues.")
    return out + [""]


def _direction(graph: store.Graph, q: dict[str, Any]) -> list[str]:
    indent = "  " * (len(graph.ancestry(q["name"])) - 1)
    reason = q.get("closed_reason") or q.get("answer")
    out = [f"{indent}- {q.get('title') or q['name']}: {q.get('status')}, {question_verdict(graph, q['name'])}"
           + (f". {clip(str(reason), REASON_CHARS)}" if reason else "")]
    for f in graph.findings_of(q["name"]):
        ids = ", ".join(str(s.get("id")) for s in f.get("sources") or [] if s.get("id")) or "no source id"
        out.append(f"{indent}  - {f.get('title') or f['name']} ({f.get('design')}, {f.get('species')}): {ids}")
    return out
