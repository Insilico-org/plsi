"""The working set: the nodes one move needs, handed over in the `next` reply so the bot never walks the folder."""

from __future__ import annotations

from typing import Any

from plsi.research.store import Graph, prose
from plsi.research.verdict import canonical_origin, evidence, question_verdict, verdict
from plsi.vocab.research import LIVE, RESOLVED, ResearchNodeKind

WORKING_SET_MAX = 40
NOTE_CHARS = 1400


def clip(text: str, limit: int) -> str:
    """Shorten to `limit` characters at a sentence end where one is near, else at a word boundary."""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind(". "), head.rfind("? "), head.rfind("! "), head.rfind("\n"))
    return (head[:cut + 1] if cut > limit // 2 else head.rsplit(" ", 1)[0]).rstrip() + " […]"


def note(node: dict[str, Any]) -> str | None:
    """The body the bot wrote on a node, without the generated links, clipped."""
    return clip(prose(node.get("body") or "").strip(), NOTE_CHARS) or None


def origins_in_use(graph: Graph) -> list[str]:
    """Every origin string already recorded in this topic, one spelling each. Never capped: its job is to stop
    a source being written a second way, which would count as a second independent line."""
    out: dict[str, str] = {}
    for f in graph.of_kind(ResearchNodeKind.FINDING):
        if f.get("origin"):
            out.setdefault(canonical_origin(f["origin"]), str(f["origin"]))
    return sorted(out.values())


def working_set(graph: Graph, question: str | None) -> dict[str, Any]:
    """The question, its ancestry, live hypotheses with their evidence, the findings that bear on them, and
    resolved children. Findings filed elsewhere but linked to a candidate here are included; findings that bear
    only on closed hypotheses are left out. The keys are the same when no question is open."""
    if not question or question not in graph.nodes:
        return {"question": None, "ancestry": [], "hypotheses": [], "findings": [], "findings_omitted": 0,
                "closed_hypotheses": [], "children_resolved": [], "origins_in_use": origins_in_use(graph)}
    live_h = [h for h in graph.hypotheses_of(question) if h.get("status") in LIVE]
    dead = {h["name"] for h in graph.hypotheses_of(question) if h.get("status") not in LIVE}
    here = {h["name"] for h in graph.hypotheses_of(question)}
    mine = {f["name"] for f in graph.findings_of(question)}
    elsewhere = [f for f in graph.of_kind(ResearchNodeKind.FINDING) if f["name"] not in mine
                 and here & set((f.get("supports") or []) + (f.get("contradicts") or []))]
    keep = []
    for f in graph.findings_of(question) + elsewhere:
        linked = set((f.get("supports") or []) + (f.get("contradicts") or []))
        if not linked or linked - dead:
            keep.append(f)
    node = graph.nodes[question]
    return {
        "question": {**{k: v for k, v in node.items() if k != "body"}, "note": note(node)},
        "ancestry": graph.ancestry(question),
        "hypotheses": [{"name": h["name"], "if_false": h.get("if_false"), "verdict": verdict(graph, h["name"]),
                        "evidence": evidence(graph, h["name"]), "boundaries": h.get("boundaries") or [],
                        "tested_by": h.get("tested_by") or [], "note": note(h)} for h in live_h],
        "findings": [{**{k: v for k, v in f.items() if k != "body"}, "note": note(f)}
                     for f in keep[:WORKING_SET_MAX]],
        "findings_omitted": max(0, len(keep) - WORKING_SET_MAX),
        "closed_hypotheses": sorted(dead),
        "children_resolved": [{"question": c["name"], "link": str(c.get("link") or ""),
                               "status": str(c.get("status")), "answer": c.get("answer"),
                               "verdict": question_verdict(graph, c["name"]),
                               "closed_reason": c.get("closed_reason")}
                              for c in graph.children(question) if c.get("status") in RESOLVED],
        "origins_in_use": origins_in_use(graph),
    }
