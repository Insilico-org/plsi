"""The cursor: which direction the loop recommends next, which move is due on it, closing a direction, and when
the topic is finished: answered at the depth it asked for, or out of directions short of that bar."""

from __future__ import annotations

from typing import Any

from plsi.research import frontier, store
from plsi.research.schema import meta_of
from plsi.research.verdict import DEPTH_FLOOR, answered, meets
from plsi.vocab.research import (RESOLVED, ResearchLogEvent, ResearchMove, ResearchStatus, ResearchStop,
                                 ResearchVerdict)

MAX_ATTEMPTS = 3  # unsaved attempts on one direction before it is closed as stuck
UNPRODUCTIVE_STOP = 3  # moves in a row on one direction that changed nothing before it is closed


def move_for(graph: store.Graph, question: str | None) -> str:
    """The move due on a direction, read off its distance to a verdict; Ask when no direction is open."""
    return str(frontier.STEPS[frontier.distance(graph, question)][0]) if question else str(ResearchMove.ASK)


def select(graph: store.Graph, after_cycle: bool, prefer: str | None = None) -> dict[str, Any]:
    """The top of the frontier with the move its distance implies. An empty frontier gives `question: None`,
    which asks for the question in chief to be decomposed further."""
    entries = frontier.rank(graph)
    if after_cycle:
        graph.topic["cycles"] = int(graph.topic.get("cycles") or 0) + 1
    if not entries:
        return {"question": None, "move": str(ResearchMove.ASK), "attempt": 0}
    top = next((e for e in entries if e["question"] == prefer), entries[0])
    return {"question": top["question"], "move": move_for(graph, top["question"]), "attempt": 0}


def current(graph: store.Graph) -> dict[str, Any]:
    """The stored cursor, reselected when its question is gone or resolved, or when none is set but the
    frontier has work."""
    cursor = dict(graph.topic.get("cursor") or {})
    question = cursor.get("question")
    stale = question and (question not in graph.nodes or graph.nodes[question].get("status") in RESOLVED)
    if stale or (not question and frontier.rank(graph)):
        return select(graph, after_cycle=False)
    cursor.setdefault("move", str(ResearchMove.ASK))
    cursor.setdefault("attempt", 0)
    return cursor


def advance(graph: store.Graph, cursor: dict[str, Any], move: str, stopped: bool) -> dict[str, Any]:
    """The cursor after a save: stay on the direction while it is still open, else move to the top of the
    frontier. After an Ask the new children are the work and the parent waits for them."""
    question = cursor.get("question")
    resolved = (not question or question not in graph.nodes
                or graph.nodes[question].get("status") in RESOLVED)
    if stopped or resolved:
        return select(graph, after_cycle=True)
    entries = frontier.rank(graph)
    if move == ResearchMove.ASK:
        here = [e for e in entries
                if e["question"] in {question, *(c["name"] for c in graph.children(question))}]
        if here:
            return {"question": here[0]["question"], "move": move_for(graph, here[0]["question"]), "attempt": 0}
        return select(graph, after_cycle=True)
    if question not in {e["question"] for e in entries}:
        return select(graph, after_cycle=True)  # children opened under it, or it resolved
    return {"question": question, "move": move_for(graph, question), "attempt": 0}


def close(graph: store.Graph, question: str, reason: str) -> str | None:
    """Close a direction with a reason: `answered` if it has an answer, else `closed`. Returns its name, or None
    when it was missing or already resolved."""
    node = graph.nodes.get(question)
    if not node or node.get("status") in RESOLVED:
        return None
    meta = meta_of(node)
    meta["status"] = str(ResearchStatus.ANSWERED if meta.get("answer") else ResearchStatus.CLOSED)
    meta["closed_reason"] = reason
    store.write_node(graph, str(node["kind"]), question, meta, str(node.get("body") or ""))
    return question


def _top_answers(graph: store.Graph) -> list[dict[str, Any]] | None:
    """Answers of the top-level directions, or None while any of them is unresolved."""
    tops = graph.tops()
    if not tops or any(q.get("status") not in RESOLVED for q in tops):
        return None
    return [a for a in (answered(graph, q["name"]) for q in tops) if a]


def answers_in_chief(graph: store.Graph) -> list[dict[str, Any]]:
    """The top-level answers, when every top-level direction is resolved and at least one answer reaches the
    topic's depth floor; else []. After a reframe, at least one move must happen under the new wording."""
    found = _top_answers(graph)
    if not found:
        return []
    since = graph.topic.get("reframed_at_move")
    if since is not None and store.moves_logged(graph) <= int(since):
        return []
    floor = DEPTH_FLOOR[store.depth_of(graph)]
    return found if any(meets(a["verdict"], floor) for a in found) else []


def short_of_bar(graph: store.Graph) -> str | None:
    """Why the topic cannot reach its depth floor: every top-level direction is answered and none of the
    answers is strong enough. None when that is not the situation.

    Resolved directions are off the frontier and cannot be strengthened, so this ends the topic; switching to
    it with a lower `--depth` finishes it as `answered` on the next `next`."""
    answers = _top_answers(graph)
    floor = DEPTH_FLOOR[store.depth_of(graph)]
    if not answers or floor is None or any(meets(a["verdict"], floor) for a in answers):
        return None
    best = max(answers, key=lambda a: ResearchVerdict(a["verdict"]).rank)
    return (f"every direction is resolved and the strongest answer is {best['verdict']}, short of the "
            f"{floor} this topic asked for. `plsi research topic --switch '{graph.name}' --depth standard` "
            "takes it as it stands; otherwise continue with one of these")


def exhausted_why(graph: store.Graph) -> str:
    return short_of_bar(graph) or (f"the frontier is empty and the last {UNPRODUCTIVE_STOP} moves opened no new "
                                   "direction")


def finished(graph: store.Graph, budget: dict[str, Any], why: ResearchStop, because: str,
             answer: dict[str, Any] | None = None, answers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """End the topic (`answered` -> done, `exhausted` -> parked), hand back the allocation, and return what the
    research found with continuations for the user to choose from."""
    done = why == ResearchStop.ANSWERED
    graph.topic.update(status=str(ResearchStatus.DONE if done else ResearchStatus.PARKED),
                       ended_reason=f"{why}: {because}")
    store.write_topic(graph)
    store.append_log(graph, {"event": str(ResearchLogEvent.STOP), "why": str(why), "unspent": budget["remaining"]})
    return {
        "topic": graph.name, "stop": str(why), "why": because, "budget": budget,
        "unspent": budget["remaining"],
        "note": "the allocation is handed back rather than spent on a question nobody can move",
        "answer": answer,
        "in_chief": answers or [],
        "answered": [a for a in (answered(graph, n) for n in graph.nodes) if a],
        "closed": frontier.closed(graph),
        "continue_with": frontier.continuations(graph),
        "ask_the_user": "report the answer in plain words with its verdict, then offer: one of these "
                        "directions, a question from the user's own newer data, a new topic, or stop here",
    }
