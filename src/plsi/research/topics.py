"""Topics: creating one, switching between them, its depth and question in chief, and the budget.

A topic is a folder, and topics never link to each other. One topic is active at a time, so the unattended
routine never has to guess which one it is working on.
"""

from __future__ import annotations

from typing import Any

from plsi.errors import NotFound, UsageError, warn
from plsi.research import ledger, propose, store
from plsi.research.schema import check_depth
from plsi.research.status import DEPTH_WORDS, summaries
from plsi.research.store import active_name, today
from plsi.research.verdict import floor_words
from plsi.vocab.research import ResearchLogEvent, ResearchStatus


def topics(new: str | None = None, question: str | None = None, switch: str | None = None,
           park: str | None = None, reason: str | None = None,
           kind: str | None = None, because: str | None = None, rests_on: list[str] | None = None,
           instance: str | None = None, depth: str | None = None, topic: str | None = None) -> dict[str, Any]:
    """`research topic`: list topics, or create, switch to, or park one; `--depth` alone changes a topic's depth.

    A new topic records its kind and what it rests on, and a personal topic's pointers must resolve in the
    record. `--switch` with `--depth` reactivates a parked topic at a new depth in one step."""
    if depth and not new and not switch:
        return _set_depth(topic or active_name(), depth)
    if new:
        if not question:
            raise UsageError("a new topic needs its question in chief", hint="--question 'what do we want to know?'")
        if not kind or not str(because or "").strip():
            raise UsageError("a new topic records where it came from and why",
                             hint="--kind personal_data|personal_case|open_question --because '<one line>'")
        propose.check_source(kind, list(rests_on or []), instance)
        source = {"kind": kind, "because": because, "rests_on": list(rests_on or []),
                  **({"instance": instance} if instance else {})}
        graph = store.create_topic(new, question, source, depth)
        _park_others(graph.name, f"switched to {graph.name}")
        return {"created": graph.name, "question_in_chief": question, "source": source,
                "depth": str(store.depth_of(graph)), "answer_must_reach": floor_words(store.depth_of(graph)),
                "active": graph.name, "topics": summaries()}
    if switch:
        graph = store.load(switch)
        graph.topic["status"] = str(ResearchStatus.ACTIVE)
        graph.topic.pop("ended_reason", None)
        store.write_topic(graph)
        store.append_log(graph, {"event": str(ResearchLogEvent.SWITCHED)})
        _park_others(graph.name, f"switched to {graph.name}")
        changed = _set_depth(graph.name, depth) if depth else {}
        return {"active": graph.name, "cursor": graph.topic.get("cursor"),
                "depth": changed.get("depth") or str(store.depth_of(graph)),
                "depth_was": changed.get("was"), "topics": summaries()}
    if park:
        graph = store.load(park)
        graph.topic.update(status=str(ResearchStatus.PARKED), ended_reason=reason or "parked by the user")
        store.write_topic(graph)
        store.append_log(graph, {"event": str(ResearchLogEvent.PARKED), "reason": graph.topic["ended_reason"]})
        return {"parked": graph.name, "topics": summaries()}
    return {"root": str(store.root()), "active": active_name(required=False), "topics": summaries()}


def _set_depth(name: str, depth: str) -> dict[str, Any]:
    """Change how thorough a topic is meant to be. Nothing in the graph moves; the finishing bar is read fresh
    on the next `next`, so lowering it can finish a topic there."""
    graph = store.load(name)
    was = str(store.depth_of(graph))
    graph.topic["depth"] = str(check_depth(depth))
    store.write_topic(graph)
    store.append_log(graph, {"event": str(ResearchLogEvent.DEPTH), "from": was, "to": graph.topic["depth"]})
    return {"topic": graph.name, "depth": graph.topic["depth"], "was": was,
            "means": DEPTH_WORDS[graph.topic["depth"]], "answer_must_reach": floor_words(store.depth_of(graph)),
            "note": "nothing in the graph moved; the bar is read fresh on the next `research next`"}


def reframe(question: str, because: str, topic: str | None = None) -> dict[str, Any]:
    """`research reframe`: change the question in chief, keeping the old wording and why it changed.

    The graph is untouched. A finished topic is reopened, and it cannot finish again until a move has been made
    under the new wording."""
    if not str(because or "").strip():
        raise UsageError("a reframing records why the question changed",
                         hint="--because 'the first framing assumed the effect was general; it is not'")
    # a finished topic is not active, so fall back to any topic rather than refusing it
    named = topic or active_name(required=False) or (store.list_topics() or [None])[0]
    if not named:
        raise NotFound("no research topic to reframe", hint="plsi research topic --new '<title>' …")
    graph = store.load(named)
    was = str(graph.topic.get("question_in_chief") or "")
    if store.sanitise(was) == store.sanitise(question):
        raise UsageError("that is the question it already asks", hint="plsi research status")
    graph.topic["question_in_chief"] = question
    graph.topic.setdefault("superseded", []).append({"question": was, "because": because, "on": today()})
    graph.topic["reframed_at_move"] = store.moves_logged(graph)
    reopened = graph.topic.get("status") == ResearchStatus.DONE
    if reopened:
        graph.topic.update(status=str(ResearchStatus.ACTIVE))
        graph.topic.pop("ended_reason", None)
        _park_others(graph.name, f"switched to {graph.name}")
    store.write_topic(graph)
    store.append_log(graph, {"event": str(ResearchLogEvent.REFRAMED), "from": was, "to": question,
                             "because": because, "reopened": reopened})
    return {"topic": graph.name, "question_in_chief": question, "was": was, "because": because,
            "reopened": reopened,
            "note": "the graph is untouched: directions opened under the old wording stand, and the old "
                    "wording is kept beside the new one",
            "superseded": graph.topic["superseded"]}


def _park_others(keep: str, reason: str) -> None:
    for name in store.list_topics():
        if name == keep:
            continue
        other = store.load(name)
        if other.topic.get("status") == ResearchStatus.ACTIVE:
            other.topic.update(status=str(ResearchStatus.PARKED), ended_reason=reason)
            store.write_topic(other)


def set_budget(share: float | None = None, ceiling: float | None = None) -> dict[str, Any]:
    """`research budget`: show or set what all research may use: `--share` per day, `--ceiling` per week.
    Whichever binds first stops the run; left alone, the ceiling is four days' worth of the share."""
    if share is None and ceiling is None:
        return {"budget": {**ledger.state(), "week_ceiling": ledger.ceiling()},
                "note": "one allocation covers all research, not one per topic; "
                        "--share sets the day and --ceiling the week"}
    was = ledger.state().get("share_of_day")
    budget = ledger.set_share(share, today(), ceiling)
    if ledger.ceiling() and float(budget.get("share_of_day") or 0.0) > ledger.ceiling():
        warn("SHARE_ABOVE_CEILING",
             f"a day may use {budget['share_of_day']}% but the week is capped at {ledger.ceiling()}%, "
             "so the first day will use the whole week's allowance")
    for name in store.list_topics():
        store.append_log(store.load(name), {"event": str(ResearchLogEvent.BUDGET), "from": was,
                                            "to": budget.get("share_of_day"), "ceiling": ledger.ceiling()})
    return {"budget": {**budget, "week_ceiling": ledger.ceiling()},
            "note": f"a day may use {budget.get('share_of_day')}% and the week {ledger.ceiling()}%; "
                    "takes effect at the next move boundary, for every topic"}
