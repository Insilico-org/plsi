"""`research next`: everything one move needs in a single response, or the stop that ends the run.

Two calls run the loop: `next` (here) and `save` (save.py). The cursor only moves on a save, so a move either
saved or it did not, and retry, resume and extend follow from the cursor plus the append-only log.
"""

from __future__ import annotations

from typing import Any

from plsi.errors import ValidationError
from plsi.research import cursor as cursors
from plsi.research import frontier, ledger, projects, store
from plsi.research.store import clip, today
from plsi.research.tuning import DEPTH_LIMITS, HEADROOM, MAX_ATTEMPTS, TRIED_CHARS, TRIED_MOVES, UNPRODUCTIVE_STOP
from plsi.research.verdict import floor_words
from plsi.research.working_set import working_set
from plsi.vocab.research import ResearchLogEvent, ResearchMove, ResearchStatus, ResearchStop


def _log_stop_once(graph: store.Graph, log: list[dict[str, Any]], why: ResearchStop, day: str | None,
                   **fields: Any) -> None:
    """Log a stop, unless the same stop is already logged for that day."""
    if not any(line.get("event") == ResearchLogEvent.STOP and line.get("why") == why and line.get("day") == day
               for line in log):
        store.append_log(graph, {"event": str(ResearchLogEvent.STOP), "why": str(why), "day": day, **fields})


def _orient(graph: store.Graph, cursor: Any = None) -> dict[str, Any]:
    """What every stop carries so its reader knows where the topic stands."""
    return {"topic": graph.name, "question_in_chief": graph.topic.get("question_in_chief"),
            "cursor": cursor if cursor is not None else graph.topic.get("cursor"), **frontier.queue(graph)}


def _read_meter(graph: store.Graph, usage: float | None) -> bool:
    """Open the day on the first reading, or charge a later reading's rise as work no save recorded.

    Returns whether a day was opened. After an unsaved attempt a reading is required, so retries cannot spend
    outside the meter."""
    if ledger.open_day(usage, today()):
        store.write_topic(graph)
        store.append_log(graph, {"event": str(ResearchLogEvent.DAY), "day": today(), "opening_usage": usage,
                                 "allocated": ledger.state()["allocated"]})
        return True
    if usage is None:
        if int((graph.topic.get("cursor") or {}).get("attempt") or 0) > 0:
            raise ValidationError("the last move was not saved, so its cost is only on the meter",
                                  code="USAGE_REQUIRED",
                                  hint="plsi research next --usage <percent of this week's limit used, read now>")
        return False
    reading = ledger.charge(usage)
    if reading["delta"]:
        store.append_log(graph, {"event": str(ResearchLogEvent.READING), "day": today(), "usage": usage,
                                 "delta": reading["delta"]})
    return False


def _meter_stop(graph: store.Graph) -> dict[str, Any] | None:
    """The `meter` stop when a reading today went below the one before it; only the user can say it was a reset."""
    fell = ledger.meter_fell(today())
    if not fell:
        return None
    return {**_orient(graph), "stop": str(ResearchStop.METER), **fell,
            "why": f"the meter read {fell['saw']} after {fell['after']}. Either the weekly limit reset "
                   "between moves or a reading was low; code cannot tell those apart and does not guess",
            "if_reset": f"plsi research budget --meter-reset --usage {fell['saw']}",
            "resumes": "after the user confirms a reset, or the next run on a new day"}


def _no_topic(meta: dict[str, Any]) -> dict[str, Any]:
    """The stop when the project has no active topic: the first run asks the user, a later one takes the top
    candidate. The day it first asked is the project's, so one project's open card never moves another."""
    if ledger.is_off():
        return {"stop": str(ResearchStop.OFF), "why": "research has no share of the meter"}
    directory = projects.folder(meta["id"])
    asked = projects.topic_asked(directory, today())
    metas = {d.name: store.topic_meta(d) for d in store.topic_dirs(directory)}
    return {"stop": str(ResearchStop.NO_TOPIC), "why": "this project has no active topic",
            "project": projects.card(meta), "asked_on": asked, "propose": "plsi research propose --instance <name>",
            "topics": [{"topic": n, "status": m.get("status"), "why": m.get("ended_reason")} for n, m in metas.items()],
            "then": "post the card for the user to pick a topic" if asked == today() else
                    f"the card of {asked} went unanswered: take the top candidate (plsi research topic --new "
                    f"--project {meta['id']}) and say so in one line"}


def next_move(topic: str | None = None, usage: float | None = None, project: str | None = None) -> dict[str, Any]:
    """`research next`: the move due on the topic named, else on the active topic of the project named (or of the
    only active project), and everything it needs, or a stop. Writes only the cursor, the day's opening and meter
    readings. The day's allocation is shared by the active projects, so a move must fit this project's part."""
    usage = None if usage is None else ledger.reading(usage)
    if not topic:
        meta = projects.pick(project)
        if store.active_name(projects.folder(meta["id"]), required=False) is None:
            return _no_topic(meta)
    graph = store.load(topic or projects.active_topic(project))
    log = store.read_log(graph)
    if graph.topic.get("status") != ResearchStatus.ACTIVE:
        done = graph.topic.get("status") == ResearchStatus.DONE
        return {**_orient(graph), "stop": str(ResearchStop.DONE if done else ResearchStop.PARKED),
                "why": graph.topic.get("ended_reason") or "the topic is not active",
                "answer": (cursors.answers_in_chief(graph) or [None])[0] if done else None,
                "continue_with": frontier.continuations(graph),
                "budget": ledger.affordable(graph, log, ResearchMove.ASK)}
    if stop := _meter_stop(graph):
        return stop
    if ledger.is_off():
        return {**_orient(graph), "stop": str(ResearchStop.OFF), "why": "research has no share of the meter",
                "turn_it_on": "plsi research budget --share <percent of the weekly meter per day>"}

    opened = _read_meter(graph, usage)
    if stop := _meter_stop(graph):
        return stop
    room = ledger.headroom(usage)
    if not room["ok"]:
        _log_stop_once(graph, log, ResearchStop.HEADROOM, today(), **room)
        return {**_orient(graph), "stop": str(ResearchStop.HEADROOM), **room,
                "why": f"{room['left']}% of the weekly meter is left and research would need {room['need']}%; "
                       f"the user keeps {HEADROOM}% for themselves",
                "open": frontier.open_items(graph), "resumes": "when the weekly meter resets"}
    week = ledger.affordable(graph, log)
    if week["week_left"] <= 0:
        _log_stop_once(graph, log, ResearchStop.CEILING, today(), week=week["week"], week_spent=week["week_spent"])
        return {**_orient(graph), "stop": str(ResearchStop.CEILING),
                "why": f"research has used {week['week_spent']}% of the weekly meter and its ceiling is "
                       f"{week['week_ceiling']}%",
                "week": week["week"], "week_spent": week["week_spent"], "week_ceiling": week["week_ceiling"],
                "open": frontier.open_items(graph), "budget": week, "resumes": "when the weekly meter resets"}

    cursor = cursors.current(graph)
    attempts = int(cursor.get("attempt") or 0)
    if attempts >= MAX_ATTEMPTS and not cursor.get("question"):
        # nothing is open to close, so the attempts start again and the next run retries the first move
        graph.topic["cursor"] = {**cursor, "attempt": 0}
        store.write_topic(graph)
        _log_stop_once(graph, log, ResearchStop.STUCK, today(), attempts=attempts)
        return {**_orient(graph, cursor), "stop": str(ResearchStop.STUCK),
                "why": f"{MAX_ATTEMPTS} attempts at the first move without a save, and no direction is open yet",
                "budget": ledger.affordable(graph, log, cursor["move"]),
                "resumes": "the next run; nothing was closed because nothing had been opened"}
    gave_up, moved_on = None, None
    if attempts >= MAX_ATTEMPTS:
        gave_up = cursors.close(graph, cursor["question"], f"stuck: {MAX_ATTEMPTS} attempts without a save")
        store.append_log(graph, {"event": str(ResearchLogEvent.GAVE_UP), "question": gave_up,
                                 "why": f"{MAX_ATTEMPTS} attempts without a save"})
        cursor = cursors.select(graph, after_cycle=False)
    elif opened and frontier.rank(graph):
        # a new day starts at the top of the queue, and says so when that changes the direction
        was = cursor.get("question")
        cursor = cursors.select(graph, after_cycle=False)
        if was and was != cursor.get("question"):
            moved_on = {"from": was, "to": cursor.get("question"),
                        "still_open": any(e["question"] == was for e in frontier.rank(graph)),
                        "why": "a new day starts at the top of the queue"}
    if not cursor.get("question") and cursor.get("move") != ResearchMove.ASK:
        cursor["move"] = str(ResearchMove.ASK)

    budget = ledger.affordable(graph, log, cursor["move"])
    # a finished topic is finished whether or not today's allocation is spent, so these come first
    in_chief = cursors.answers_in_chief(graph)
    if in_chief and not frontier.rank(graph):
        return cursors.finished(graph, budget, ResearchStop.ANSWERED,
                               "every direction under the question in chief is resolved and the topic has answers",
                               answer=in_chief[0], answers=in_chief)
    short = cursors.short_of_bar(graph)
    if short and not frontier.rank(graph):
        return cursors.finished(graph, budget, ResearchStop.EXHAUSTED, short)

    if not budget["ok"]:
        _log_stop_once(graph, log, ResearchStop.BUDGET, budget["day"], unspent=budget["remaining"],
                       open=frontier.open_items(graph))
        return {**_orient(graph, cursor), "stop": str(ResearchStop.BUDGET),
                "why": f"today's allocation is spent: {budget['remaining']} left and {cursor['move']} costs about "
                       f"{budget['estimate']}",
                "unspent": budget["remaining"], **frontier.recently_closed(graph), "open": frontier.open_items(graph),
                "budget": budget, "resumes": "the next run on a new day, from this cursor"}
    if _unproductive_run(log, cursor.get("question")) >= UNPRODUCTIVE_STOP:
        # motion without progress ends the direction, not the day
        if cursor.get("question"):
            cursors.close(graph, cursor["question"], f"stuck: {UNPRODUCTIVE_STOP} moves in a row changed nothing")
            cursor = cursors.select(graph, after_cycle=True)
            store.append_log(graph, {"event": str(ResearchLogEvent.PIVOT), "why": "unproductive",
                                     "to": cursor["question"]})
        elif not frontier.rank(graph):
            return cursors.finished(graph, budget, ResearchStop.EXHAUSTED, cursors.exhausted_why(graph))

    cursor["attempt"] = int(cursor.get("attempt") or 0) + 1
    graph.topic["cursor"] = cursor
    store.write_topic(graph)
    return _move_reply(graph, log, cursor, budget, gave_up, moved_on)


def _move_reply(graph: store.Graph, log: list[dict[str, Any]], cursor: dict[str, Any], budget: dict[str, Any],
                gave_up: str | None, moved_on: dict[str, Any] | None) -> dict[str, Any]:
    depth = store.depth_of(graph)
    max_depth, max_breadth = DEPTH_LIMITS[depth]
    question = cursor.get("question")
    return {
        **_orient(graph, cursor),
        "topic_rests_on": graph.topic.get("source") or {},
        "move": str(cursor["move"]),
        "skill": f"lab/{cursor['move']}",
        "needs": None if question else ("No direction is open. Open one under the question in chief - a part of it "
                                        "nobody has worked, or a continuation of what is already answered."),
        "route": frontier.route(graph, question) if question else None,
        "ready_to_answer": bool(question) and frontier.is_ready(graph, question),
        "budget": budget,
        **frontier.recently_closed(graph),
        "working_set": working_set(graph, question),
        "already_tried": _already_tried(log, question),
        "gave_up_on": gave_up,
        "moved_on": moved_on,
        "question_in_chief_answered": (cursors.answers_in_chief(graph) or [None])[0],
        "coverage": frontier.coverage(graph, brief=True),
        "depth": str(depth), "answer_must_reach": floor_words(depth),
        "limits": {"max_depth": max_depth, "max_breadth": max_breadth,
                   "depth_here": len(graph.ancestry(question)) if question else 0},
    }


def _already_tried(log: list[dict[str, Any]], question: str | None) -> list[dict[str, Any]]:
    """The `open` and `dropped` sections of the last few moves on this direction, most recent first, clipped."""
    if not question:
        return []
    out = []
    for line in reversed(log):
        if line.get("question") != question or not line.get("sections"):
            continue
        kept = {k: clip(str(v), TRIED_CHARS) for k, v in line["sections"].items() if k in ("open", "dropped")}
        if kept:
            out.append({"move": line.get("move"), **kept})
        if len(out) >= TRIED_MOVES:
            break
    return out


def _unproductive_run(log: list[dict[str, Any]], question: str | None = None) -> int:
    """Moves in a row on this direction that changed nothing."""
    run = 0
    for line in reversed([line for line in log if line.get("move")]):
        if question is not None and line.get("question") != question:
            continue
        if line.get("productive"):
            break
        run += 1
    return run
