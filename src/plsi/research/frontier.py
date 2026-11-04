"""The frontier: why each direction is open, how far it is from a verdict, and the ranked queue of open work.

Everything here is computed from the files on every read and never stored.
"""

from __future__ import annotations

from typing import Any

from plsi.research.store import Graph, depth_of
from plsi.research.verdict import (MIN_ABSENCE_ROUNDS, counts_for_support, evidence, independent,
                                   is_recorded_absence, lines, live_hypotheses, question_verdict, verdict, weight)
from plsi.research.working_set import clip
from plsi.vocab.research import (LIVE, RESOLVED, QuestionLink, ResearchAngle, ResearchContinuation, ResearchDepth,
                                 ResearchDesign, ResearchGap, ResearchMove, ResearchNodeKind, ResearchRoute,
                                 ResearchVerdict, Stakes)

# distance to a verdict -> (the move due, how the queue describes it)
STEPS = {0: (ResearchMove.TEST, "ready to answer"),
         1: (ResearchMove.TEST, "one move from a verdict"),  # candidates are standing against evidence
         2: (ResearchMove.EXPLAIN, "has evidence, nothing proposed yet"),
         3: (ResearchMove.GATHER, "not started"),  # a question nobody has searched
         4: (ResearchMove.ASK, "searched dry, needs rewording first")}
GAP_COST = {ResearchGap.UNSEARCHED: 0, ResearchGap.UNSTUDIED: 1, ResearchGap.NOTHING_USABLE: 1,
            ResearchGap.UNEXPLAINED: 1, ResearchGap.UNREPLICATED: 2, ResearchGap.SURROGATE_ONLY: 3,
            ResearchGap.DISPUTED: 4}
NOVEL_GAP_COST, NO_GAP_COST = 2, 4
STAKES_ORDER = {str(Stakes.HIGH): 0, str(Stakes.SOME): 1, str(Stakes.LOW): 2}
ANGLE_ASKS = {  # the question each angle opens, offered when a topic's frontier empties
    ResearchAngle.MECHANISM: "is there a route by which this could happen at all?",
    ResearchAngle.MAGNITUDE: "how large is it, and in whom?",
    ResearchAngle.BOUNDARY: "where does it stop holding - dose, age, sex, comorbidity, duration?",
    ResearchAngle.ALTERNATIVE: "what else would produce the same observation?",
    ResearchAngle.HARM: "what does it cost, and to whom?",
}
CONTINUATIONS_MAX = 8
CLOSED_IN_CONTEXT = 5  # closed directions sent with each move; `status` carries them all
CLOSED_REASON_CHARS = 200
FRONTIER_IN_CONTEXT = 12  # open directions sent with each move; `frontier_total` says how many were not
# How many independent lines make a leaf answerable without proposing a candidate; `None` means never, so the
# direction goes through Explain. Above `standard` it is off because findings alone stop at `thin`, below the
# `supported` floor those depths require.
DEPTH_ANSWER_FROM_FINDINGS: dict[ResearchDepth, int | None] = {
    ResearchDepth.FAST: 1,
    ResearchDepth.STANDARD: 2,
    ResearchDepth.DEEP: None,
    ResearchDepth.EXHAUSTIVE: None,
}


def gap(graph: Graph, question: str) -> tuple[str | None, bool]:
    """(label, computed): why this direction is open. A label the bot wrote stands as written (folded to its
    canonical spelling); otherwise it is read off the counts."""
    node = graph.nodes.get(question, {})
    if node.get("gap"):
        return ResearchGap.canonical(node["gap"]), False
    live = live_hypotheses(graph, question)
    if not graph.findings_of(question):
        search = node.get("last_search") or {}
        if not int(search.get("rounds") or 0):
            return str(ResearchGap.UNSEARCHED), True
        return str(ResearchGap.NOTHING_USABLE if int(search.get("hits") or 0) else ResearchGap.UNSTUDIED), True
    if any(verdict(graph, h["name"]) == ResearchVerdict.CONTESTED for h in live):
        return str(ResearchGap.DISPUTED), True
    if not live:
        return str(ResearchGap.UNEXPLAINED), True
    if max(weight(evidence(graph, h["name"])["for"]) for h in live) <= 1:
        return str(ResearchGap.UNREPLICATED), True
    return None, True


def route(graph: Graph, question: str) -> str:
    """How much is left on a direction, shown to the bot. Descriptive only; the move comes from `distance`."""
    node = graph.nodes.get(question, {})
    search = node.get("last_search") or {}
    findings = graph.findings_of(question)
    if int(search.get("rounds") or 0) >= MIN_ABSENCE_ROUNDS and not int(search.get("hits") or 0) and not findings:
        return str(ResearchRoute.ABSENT)
    if any(f.get("design") == ResearchDesign.AGGREGATE for f in findings):
        return str(ResearchRoute.SETTLED)
    live = live_hypotheses(graph, question)
    if live and all(verdict(graph, h["name"]) == ResearchVerdict.SUPPORTED for h in live):
        return str(ResearchRoute.SHALLOW)
    return str(ResearchRoute.DEEP)


def is_ready(graph: Graph, question: str) -> bool:
    """Whether a question can be answered now: a parent whose decomposing children are all resolved, a leaf
    whose candidates have all met evidence, or a leaf whose findings alone reach the lines its depth allows."""
    node = graph.nodes.get(question, {})
    if node.get("status") in RESOLVED or str(node.get("answer") or "").strip():
        return False
    kids = [c for c in graph.children(question) if c.get("link") == QuestionLink.DECOMPOSES]
    if kids:
        return all(c.get("status") in RESOLVED for c in kids)
    if any(c.get("status") in LIVE for c in graph.children(question)):
        return False
    live = live_hypotheses(graph, question)
    if live:
        return all(verdict(graph, h["name"]) != ResearchVerdict.UNTESTED for h in live)
    enough = DEPTH_ANSWER_FROM_FINDINGS[depth_of(graph)]
    if enough is None:
        return False
    # distinct sources, not weight: one aggregate weighs 2 but is one source
    return independent(lines([f for f in graph.findings_of(question) if counts_for_support(f)])) >= enough


def distance(graph: Graph, question: str) -> int:
    """Moves still needed before this direction yields a verdict: the one number the frontier ranks on and the
    move due is read from (`STEPS`)."""
    if is_ready(graph, question):
        return 0
    live = live_hypotheses(graph, question)
    findings = graph.findings_of(question)
    if live and findings:
        return 1
    if live:
        return 3  # candidates with no evidence to meet: gather first
    if findings:
        return 2
    rounds = int((graph.nodes.get(question, {}).get("last_search") or {}).get("rounds") or 0)
    return 4 if rounds else 3


def _reachability(node: dict[str, Any]) -> int:
    search = node.get("last_search") or {}
    rounds, hits = int(search.get("rounds") or 0), int(search.get("hits") or 0)
    return 0 if hits or not rounds else min(rounds, 3)


def rank(graph: Graph) -> list[dict[str, Any]]:
    """Open leaves and ready parents, fewest moves from a verdict first, then reachability, stakes, gap and
    depth. The second slot goes to a direction from another branch, so the queue does not narrow to one."""
    entries = []
    for node in graph.of_kind(ResearchNodeKind.QUESTION):
        if node.get("status") not in LIVE:
            continue
        ready = is_ready(graph, node["name"])
        if not ready and any(c.get("status") in LIVE for c in graph.children(node["name"])):
            continue  # a question with open children is waiting, not open
        label, computed = gap(graph, node["name"])
        steps = distance(graph, node["name"])
        unreachable = _reachability(node) if steps >= 2 else 0  # only matters while gathering comes next
        chain = graph.ancestry(node["name"])  # [node, ..., root]
        stakes = node.get("stakes") or Stakes.SOME
        entries.append({
            "question": node["name"], "ready": ready, "stakes": str(stakes),
            "candidates": len(live_hypotheses(graph, node["name"])),
            "gap": label, "gap_computed": computed, "angle": node.get("angle"),
            "verdict": question_verdict(graph, node["name"]), "depth": len(chain) - 1,
            "branch": chain[-2] if len(chain) > 1 else chain[0],
            "steps_to_a_verdict": steps,
            "why": ("ready to answer" if ready else
                    f"demoted: searched {unreachable} round(s), nothing there" if unreachable else
                    f"{STEPS[steps][1]}, stakes {stakes}" + (f", {label}" if label else "")),
            # deeper questions sort after shallower ones at equal cost, so older directions get revisited
            "_key": (steps, unreachable, STAKES_ORDER.get(str(node.get("stakes")), 1),
                     GAP_COST.get(label, NOVEL_GAP_COST) if label else NO_GAP_COST, len(chain), node["name"]),
        })
    entries.sort(key=lambda e: e["_key"])
    if len(entries) > 1 and entries[0]["branch"] == entries[1]["branch"]:
        other = next((i for i, e in enumerate(entries) if e["branch"] != entries[0]["branch"]), None)
        if other:
            entries.insert(1, entries.pop(other))
            entries[1]["why"] += " - kept as the non-greedy alternative"
    for position, entry in enumerate(entries, 1):
        entry["rank"] = position
        entry.pop("_key")
    return entries


def continuations(graph: Graph) -> list[dict[str, Any]]:
    """What is still worth asking once the frontier empties, read off what the research recorded. Offered to
    the user, who decides whether to continue."""
    out: list[dict[str, Any]] = []
    for h in graph.of_kind(ResearchNodeKind.HYPOTHESIS):
        if h.get("status") in LIVE and verdict(graph, h["name"]) == ResearchVerdict.UNTESTED:
            out.append({"kind": str(ResearchContinuation.UNTESTED), "node": h["name"],
                        "why": "proposed and never tested against anything",
                        "ask": f"what evidence would settle {h['name']!r}?"})
        for boundary in h.get("boundaries") or []:
            if not boundary.get("spawned") or boundary["spawned"] not in graph.nodes:
                out.append({"kind": str(ResearchContinuation.BOUNDARY), "node": h["name"],
                            "why": f"a contradiction dissolved into a difference in {boundary.get('differ_in')}, "
                                   "and nothing was asked about it",
                            "ask": f"where does it stop holding, by {boundary.get('differ_in')}?"})
    for q in graph.of_kind(ResearchNodeKind.QUESTION):
        if is_recorded_absence(graph, q["name"]):
            out.append({"kind": str(ResearchContinuation.ABSENT), "node": q["name"],
                        "why": f"searched in {MIN_ABSENCE_ROUNDS} or more rounds and nothing came back",
                        "ask": "is the user's own record the only evidence that exists here?"})
    asked = {str(q.get("angle")) for q in graph.of_kind(ResearchNodeKind.QUESTION) if q.get("angle")}
    for angle in ResearchAngle:
        if angle not in asked:
            out.append({"kind": str(ResearchContinuation.ANGLE), "node": None,
                        "why": f"no question took the {angle} angle", "ask": ANGLE_ASKS[angle]})
    return out[:CONTINUATIONS_MAX]


def _closed(nodes: list[dict[str, Any]], reason_chars: int | None = None) -> list[dict[str, Any]]:
    out = []
    for n in nodes:
        reason = str(n.get("closed_reason") or n.get("answer") or n.get("status"))
        out.append({"question": n["name"], "reason": clip(reason, reason_chars) if reason_chars else reason,
                    "status": str(n.get("status"))})
    return out


def closed(graph: Graph) -> list[dict[str, Any]]:
    """Every resolved question and why."""
    return _closed([n for n in graph.of_kind(ResearchNodeKind.QUESTION) if n.get("status") in RESOLVED])


def recently_closed(graph: Graph) -> dict[str, Any]:
    """What `next` sends: the most recently resolved few with their reasons shortened, and how many there are."""
    done = [n for n in graph.of_kind(ResearchNodeKind.QUESTION) if n.get("status") in RESOLVED]
    recent = sorted(done, key=lambda n: str(n.get("updated") or ""), reverse=True)[:CLOSED_IN_CONTEXT]
    return {"closed": _closed(recent, CLOSED_REASON_CHARS), "closed_total": len(done)}


def queue(graph: Graph) -> dict[str, Any]:
    """The frontier as every reply sends it: the top of the queue and its full length."""
    entries = rank(graph)
    return {"frontier": entries[:FRONTIER_IN_CONTEXT], "frontier_total": len(entries)}


def open_items(graph: Graph) -> list[str]:
    """Every open direction, so a stop says what was not reached."""
    return [e["question"] for e in rank(graph)]
