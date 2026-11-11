"""`research status`: where a topic stands, with what counts for nothing and the metrics; and `research project`,
whose `--show` is the project map other bots navigate a project by."""

from __future__ import annotations

from collections import Counter
from typing import Any

from plsi.errors import UsageError
from plsi.research import adopt as adoption
from plsi.research import frontier, ledger, notes, projects, store
from plsi.research.store import Graph
from plsi.research.tuning import ADOPT_AFTER, DEPTH_WORDS
from plsi.research.verdict import (answered, evidence, floor_words, implicit_origin, independent, live_hypotheses,
                                   question_verdict, tested_against, verdicts, weakest)
from plsi.vocab.research import (LIVE, OFF_TARGET_SPECIES, ProjectStatus, ResearchDesign, ResearchGap,
                                 ResearchNodeKind, ResearchNoteStatus, ResearchVerdict)


def counting_for_nothing(graph: Graph) -> list[dict[str, Any]]:
    """Every finding that contributes to no claim, and why. Findings merely waiting for the Test move to link
    them are marked `waiting` and listed after the real losses."""
    out = []
    live_h = {h["name"] for h in graph.of_kind(ResearchNodeKind.HYPOTHESIS) if h.get("status") in LIVE}
    unattributed = {f["name"] for f in graph.of_kind(ResearchNodeKind.FINDING)
                    if not f.get("origin") and not implicit_origin(f)}
    for f in graph.of_kind(ResearchNodeKind.FINDING):
        linked = tested_against(f)
        why, waiting = None, False
        if f.get("status") not in LIVE:
            why = "superseded by a later finding; it keeps its place and its sources"
        elif not linked:
            why, waiting = "bears on its question but meets no candidate yet - the Test move links it", True
        elif not (linked & live_h):
            why = "every candidate it met has been closed"
        elif str(f.get("species") or "") in OFF_TARGET_SPECIES:
            why = (f"{f.get('species')}: a result about something else. It is kept and shown, and sits "
                   "outside the count for a claim about people")
        elif f.get("design") == ResearchDesign.PERSONAL_RECORD and (f.get("supports") or []):
            why = "the user's own record is n = 1: it may refute a prediction about them, never support a claim"
        elif f["name"] in unattributed and len(unattributed) > 1:
            why = (f"no origin recorded, so it shares one line with {len(unattributed) - 1} other "
                   "unattributed finding(s) - independence that cannot be shown has not been earned")
        if why:
            out.append({"finding": f["name"], "why": why, "waiting": waiting})
    return sorted(out, key=lambda item: item["waiting"])


def metrics(graph: Graph, log: list[dict[str, Any]]) -> dict[str, Any]:
    qs, fs = graph.of_kind(ResearchNodeKind.QUESTION), graph.of_kind(ResearchNodeKind.FINDING)
    sources = [s for f in fs for s in (f.get("sources") or [])]
    moves = [line for line in log if line.get("move")]
    novel = Counter(ResearchGap.canonical(q["gap"]) for q in qs
                    if q.get("gap") and ResearchGap.canonical(q["gap"]) not in tuple(ResearchGap))
    return {
        "verdicts": dict(Counter(verdicts(graph).values())),
        "findings": len(fs),
        "candidates_max": max((len(live_hypotheses(graph, q["name"])) for q in qs), default=0),
        "independent_lines_max": max((independent(evidence(graph, h["name"])["for"])
                                      for h in graph.of_kind(ResearchNodeKind.HYPOTHESIS)), default=0),
        "sources_per_finding": round(len(sources) / len(fs), 2) if fs else 0,
        "quote_verified": round(sum(bool(s.get("quote_verified")) for s in sources) / len(sources), 2) if sources else 0,
        "origin_filled": round(sum(bool(f.get("origin")) for f in fs) / len(fs), 2) if fs else 0,
        "cycles": graph.topic.get("cycles", 0),
        "moves": len(moves),
        "moves_productive": sum(bool(line.get("productive")) for line in moves),
        "chose_another_move": sum(bool(line.get("recommended")) for line in moves),
        "chose_another_question": sum(bool(line.get("suggested_question")) for line in moves),
        "novel_gap_labels": dict(novel),
        "gap_labels_to_adopt": sorted(k for k, v in novel.items() if v >= ADOPT_AFTER),
    }


def _map_note(note: dict[str, Any], superseded_by: dict[str, str]) -> dict[str, Any]:
    keep = ("name", "title", "topic", "status", "grade", "evidence_class", "updated", "builds_on", "supersedes",
            "contradicts", "decision_reason", "retire_reason", "error")
    shown = {k: note[k] for k in keep if note.get(k) not in (None, [], "")}
    if shown.get("supersedes"):
        shown["supersedes"] = shown["supersedes"][0]  # one note; `research check` refuses a list
    return {**shown, "sent": note.get("status") in notes.SENT, "superseded_by": superseded_by.get(note["name"])}


def project_map(ref: str) -> dict[str, Any]:
    """`research project --show`: one project as a map: its topics, every note with its status and links, which
    were sent to the Mothership and what came back, and the next steps its live notes name."""
    meta = projects.resolve(ref)
    found = notes.list_notes(project=meta["id"])
    superseded_by = {old: n["name"] for n in found for old in n.get("supersedes") or []}
    live = [n for n in found if n["name"] not in superseded_by
            and n.get("status") not in (ResearchNoteStatus.RETIRE, notes.UNREADABLE)]
    directory = projects.folder(meta["id"])
    return {"project": meta, "folder": str(directory), "topics": store.summaries(directory),
            "notes": [_map_note(n, superseded_by) for n in found],
            "counts": dict(Counter(str(n.get("status")) for n in found)),
            "next_steps": [{"note": n["name"], "next_step": s} for n in live for s in n.get("next_steps") or []]}


def project(new: str | None = None, aim: str | None = None, close: str | None = None, reopen: str | None = None,
            show: str | None = None, adopt: bool = False) -> dict[str, Any]:
    """`research project`: list projects, or create, close, reopen, show or adopt. Nothing here changes a project
    the command does not name."""
    if aim and not new:
        raise UsageError("--aim goes with --new", hint="plsi research project --new '<title>' --aim '<one line>'")
    if new:
        meta = projects.create(new, aim)
        return {"created": projects.card(meta), "aim": meta["aim"], "folder": str(projects.folder(meta["id"])),
                "active": projects.active_cards()}
    if close or reopen:
        key, to = ("closed", ProjectStatus.CLOSED) if close else ("reopened", ProjectStatus.ACTIVE)
        return {key: projects.card(projects.set_status(close or reopen, to)), "active": projects.active_cards()}
    if show:
        return project_map(show)
    if adopt:
        return adoption.adopt()
    return {"root": str(store.root() / store.PROJECTS_FOLDER), "active": projects.active_cards(),
            "projects": projects.every()}


def status(topic: str | None = None, full: bool = False, project: str | None = None) -> dict[str, Any]:
    """`research status [--full]`: where the topic named stands, else the active topic of the project named (or of
    the only active project). `--full` adds every log row, each hypothesis's evidence lines for and against and
    each finding's source ids: what a dashboard of the topic is drawn from."""
    name = topic
    if not name:
        if not projects.every():
            return {"root": str(store.root()), "topics": [], "note": "no research project yet"}
        meta = projects.pick(project)
        directory = projects.folder(meta["id"])
        name = store.active_name(directory, required=False)
        if not name:
            return {"project": projects.card(meta), "topics": store.summaries(directory),
                    "note": "this project has no active topic"}
    graph = store.load(name)
    log = store.read_log(graph)
    root = graph.root()
    answers = [a for a in (answered(graph, n) for n in graph.nodes) if a]
    tops = {n["name"] for n in graph.tops()}
    # the question in chief's own answer if it is a node, else every top-level answer
    headline = [a for a in answers if root and a["question"] == root["name"]] \
        or [a for a in answers if a["question"] in tops]
    depth = store.depth_of(graph)
    entries = frontier.rank(graph)
    return {
        "topic": graph.name, "status": str(graph.topic.get("status")),
        "question_in_chief": graph.topic.get("question_in_chief"),
        "source": graph.topic.get("source") or {},
        "depth": str(depth), "depth_means": DEPTH_WORDS[depth], "answer_must_reach": floor_words(depth),
        "answer": headline[0] if headline else None,
        "answers": headline,
        "verdict": weakest([question_verdict(graph, a["question"]) for a in headline])
                   if headline else str(ResearchVerdict.UNTESTED),
        "cursor": graph.topic.get("cursor"),
        "metrics": metrics(graph, log),
        "counting_for_nothing": counting_for_nothing(graph),
        "coverage": frontier.coverage(graph),
        "progress": ledger.bar(log),
        "budget": ledger.affordable(graph, log),
        "frontier": entries,
        "continue_with": frontier.continuations(graph) if not entries else [],
        "closed": frontier.closed(graph),
        "verdicts": verdicts(graph),
        **({"log": log,
            "evidence": {h["name"]: evidence(graph, h["name"]) for h in graph.of_kind(ResearchNodeKind.HYPOTHESIS)},
            "sources": {f["name"]: [s.get("id") for s in f.get("sources") or []]
                        for f in graph.of_kind(ResearchNodeKind.FINDING)}} if full else {}),
    }
