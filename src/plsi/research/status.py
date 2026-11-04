"""`research status`: where a topic stands, with its topic-wide counts (coverage, what counts for nothing, the
metrics) and the list of topics."""

from __future__ import annotations

from collections import Counter
from typing import Any

from plsi.research import frontier, ledger, store
from plsi.research.store import Graph
from plsi.research.verdict import (answered, evidence, floor_words, implicit_origin, independent, live_hypotheses,
                                   question_verdict, verdicts, weakest)
from plsi.vocab.research import (LIVE, OFF_TARGET_SPECIES, ResearchDepth, ResearchDesign, ResearchGap, ResearchMove,
                                 ResearchNodeKind, ResearchVerdict)

ADOPT_AFTER = 2  # a novel gap label used this many times is offered for adoption
DEPTH_WORDS = {
    ResearchDepth.FAST: "one pass. Whatever answer the evidence allows, including a thin one",
    ResearchDepth.STANDARD: "an answer has to rest on something before the topic is finished",
    ResearchDepth.DEEP: "replication before the topic is finished, and every direction goes through Explain",
    ResearchDepth.EXHAUSTIVE: "the same bar as deep, with more room to branch",
}


def counting_for_nothing(graph: Graph) -> list[dict[str, Any]]:
    """Every finding that contributes to no claim, and why. Findings merely waiting for the Test move to link
    them are marked `waiting` and listed after the real losses."""
    out = []
    live_h = {h["name"] for h in graph.of_kind(ResearchNodeKind.HYPOTHESIS) if h.get("status") in LIVE}
    unattributed = [f for f in graph.of_kind(ResearchNodeKind.FINDING)
                    if not f.get("origin") and not implicit_origin(f)]
    for f in graph.of_kind(ResearchNodeKind.FINDING):
        linked = set((f.get("supports") or []) + (f.get("contradicts") or []))
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
        elif not f.get("origin") and not implicit_origin(f) and len(unattributed) > 1:
            why = (f"no origin recorded, so it shares one line with {len(unattributed) - 1} other "
                   "unattributed finding(s) - independence that cannot be shown has not been earned")
        if why:
            out.append({"finding": f["name"], "why": why, "waiting": waiting})
    return sorted(out, key=lambda item: item["waiting"])


def coverage(graph: Graph, brief: bool = False) -> dict[str, Any]:
    """What the topic already covers: angles, question states, outstanding gaps, designs, species, origins and
    populations. `brief` (what `next` sends) gives counts for origins and populations instead of the lists."""
    qs, fs = graph.of_kind(ResearchNodeKind.QUESTION), graph.of_kind(ResearchNodeKind.FINDING)
    live_gaps = Counter(frontier.gap(graph, q["name"])[0] for q in qs if q.get("status") in LIVE)
    origins = {str(f.get("origin")) for f in fs if f.get("origin")}
    populations = {str(f.get("population")) for f in fs if f.get("population")}
    return {
        "angles_asked": dict(Counter(str(q["angle"]) for q in qs if q.get("angle"))),
        "questions_by_state": dict(Counter(str(q.get("status")) for q in qs)),
        "gaps_outstanding": {k: v for k, v in live_gaps.items() if k},
        "designs_seen": sorted({str(f.get("design")) for f in fs if f.get("design")}),
        "populations_seen": len(populations) if brief else sorted(populations),
        "origins_seen": len(origins) if brief else sorted(origins),
        "species": dict(Counter(str(f.get("species")) for f in fs if f.get("species"))),
    }


def metrics(graph: Graph, log: list[dict[str, Any]]) -> dict[str, Any]:
    """Every number read off frontmatter and the log."""
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


def summaries() -> list[dict[str, Any]]:
    """Every topic, one entry each."""
    out = []
    for name in store.list_topics():
        graph = store.load(name)
        out.append({"topic": name, "status": str(graph.topic.get("status")),
                    "question_in_chief": graph.topic.get("question_in_chief"),
                    "depth": str(store.depth_of(graph)),
                    "cursor": graph.topic.get("cursor"), "cycles": graph.topic.get("cycles", 0),
                    "nodes": len(graph.nodes), "source": graph.topic.get("source") or {}})
    return out


def status(topic: str | None = None, full: bool = False) -> dict[str, Any]:
    """`research status [--full]`: where the topic stands. `--full` adds every log row in order (moves with what
    each cost and changed, days, readings, stops), each hypothesis's evidence lines for and against, and each
    finding's source ids: what a dashboard of the topic is drawn from."""
    name = topic or store.active_name(required=False)
    if not name:
        return {"root": str(store.root()), "topics": summaries(), "note": "no research topic yet"}
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
        "coverage": coverage(graph),
        "progress": ledger.bar(log),
        "budget": ledger.affordable(log, str((graph.topic.get("cursor") or {}).get("move") or ResearchMove.ASK)),
        "frontier": entries,
        "continue_with": frontier.continuations(graph) if not entries else [],
        "closed": frontier.closed(graph),
        "verdicts": verdicts(graph),
        **({"log": log,
            "evidence": {h["name"]: evidence(graph, h["name"]) for h in graph.of_kind(ResearchNodeKind.HYPOTHESIS)},
            "sources": {f["name"]: [s.get("id") for s in f.get("sources") or []]
                        for f in graph.of_kind(ResearchNodeKind.FINDING)}} if full else {}),
    }
