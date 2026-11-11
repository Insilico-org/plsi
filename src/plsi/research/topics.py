"""Topics: creating one, switching between them, its depth and question in chief, and the budget.

A topic is a folder in its project's topics/, and topics never link to each other. Each project has at most one
active topic, its daily topic, so a project's daily run never has to guess which one it is working on; switching
a topic never touches another project's.
"""

from __future__ import annotations

from typing import Any

from plsi.errors import NotFound, UsageError, warn
from plsi.research import ledger, projects, propose, store
from plsi.research.schema import check_depth
from plsi.research.store import today
from plsi.research.tuning import DEPTH_WORDS
from plsi.research.verdict import floor_words
from plsi.vocab.research import ResearchLogEvent, ResearchStatus


def topics(new: str | None = None, question: str | None = None, switch: str | None = None,
           park: str | None = None, reason: str | None = None,
           kind: str | None = None, because: str | None = None, rests_on: list[str] | None = None,
           instance: str | None = None, depth: str | None = None, topic: str | None = None,
           project: str | None = None) -> dict[str, Any]:
    """`research topic`: list topics, or create, switch to, or park one; `--depth` alone changes the depth of
    `--topic`, else of the active topic of `--project` (or of the only active project). `--switch` with `--depth`
    reactivates a parked topic at a new depth in one step. A flag the chosen action does not read is refused."""
    stray = [flag for flag, given, used in (
        ("--question", question, new), ("--kind", kind, new), ("--because", because, new),
        ("--rests-on", rests_on, new), ("--instance", instance, new), ("--reason", reason, park),
        ("--depth", depth, not park), ("--topic", topic, not (new or switch or park))) if given and not used]
    if stray:
        raise UsageError(f"{', '.join(stray)} does not go with this action", hint="plsi research topic --help")
    if project and (switch or park):
        raise UsageError("--project does not go with --switch or --park: a topic is named alone",
                         hint="plsi research topic --switch '<name>'")
    if depth and not new and not switch:
        return _set_depth(topic or projects.active_topic(project), depth)
    if new:
        if not question:
            raise UsageError("a new topic needs its question in chief", hint="--question 'what do we want to know?'")
        if not kind or not str(because or "").strip():
            raise UsageError("a new topic records where it came from and why",
                             hint="--kind personal_data|personal_case|open_question --because '<one line>'")
        propose.check_source(kind, list(rests_on or []), instance)
        source = {"kind": kind, "because": because, "rests_on": list(rests_on or []),
                  **({"instance": instance} if instance else {})}
        named = projects.pick(project)
        directory = projects.folder(named["id"])
        graph = store.create_topic(new, question, directory, named["id"], source, depth)
        _activate(graph)
        return {"created": graph.name, "question_in_chief": question, "source": source,
                "depth": str(store.depth_of(graph)), "answer_must_reach": floor_words(store.depth_of(graph)),
                "project": projects.card(named), "active": graph.name, "topics": store.summaries(directory)}
    if switch:
        graph = store.load(switch)
        _activate(graph)
        store.append_log(graph, {"event": str(ResearchLogEvent.SWITCHED)})
        changed = _set_depth(graph.name, depth) if depth else {}
        return {"active": graph.name, "project": graph.topic.get("project"), "cursor": graph.topic.get("cursor"),
                "depth": changed.get("depth") or str(store.depth_of(graph)),
                "depth_was": changed.get("was"), "topics": _listing(graph.topic.get("project"))}
    if park:
        graph = store.load(park)
        graph.topic.update(status=str(ResearchStatus.PARKED), ended_reason=reason or "parked by the user")
        store.write_topic(graph)
        store.append_log(graph, {"event": str(ResearchLogEvent.PARKED), "reason": graph.topic["ended_reason"]})
        return {"parked": graph.name, "topics": _listing(graph.topic.get("project"))}
    pid = projects.resolve(project)["id"] if project else None
    return {"active": {m["title"]: store.active_name(projects.folder(m["id"]), required=False)
                       for m in projects.actives() if not pid or m["id"] == pid},
            "topics": _listing(pid)}


def _listing(pid: str | None) -> list[dict[str, Any]]:
    return store.summaries(projects.folder(pid) if pid else None)


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


def reframe(question: str, because: str, topic: str | None = None, project: str | None = None) -> dict[str, Any]:
    """`research reframe`: change the question in chief, keeping the old wording and why it changed.

    The graph is untouched. A finished topic is reopened, and it cannot finish again until a move has been made
    under the new wording."""
    if not str(because or "").strip():
        raise UsageError("a reframing records why the question changed",
                         hint="--because 'the first framing assumed the effect was general; it is not'")
    # a finished topic is not active, so fall back to any of the project's topics rather than refusing it
    directory = None if topic else projects.folder(projects.pick(project)["id"])
    named = topic or store.active_name(directory, required=False) or (store.list_topics(directory) or [None])[0]
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
        _activate(graph)
    store.write_topic(graph)
    store.append_log(graph, {"event": str(ResearchLogEvent.REFRAMED), "from": was, "to": question,
                             "because": because, "reopened": reopened})
    return {"topic": graph.name, "question_in_chief": question, "was": was, "because": because,
            "reopened": reopened,
            "note": "the graph is untouched: directions opened under the old wording stand, and the old "
                    "wording is kept beside the new one",
            "superseded": graph.topic["superseded"]}


def _activate(graph: store.Graph) -> None:
    """Make this topic its project's active one and park the project's other active topic, writing each that
    changed; other projects' topics are not touched."""
    directory = store.project_of(graph)
    with store.locked(directory):
        graphs = {n: store.load(n) for n in store.list_topics(directory) if n != graph.name} | {graph.name: graph}
        parked = {"status": str(ResearchStatus.PARKED), "ended_reason": f"switched to {graph.name}"}
        for name, other in graphs.items():
            meta, mine = other.topic, name == graph.name
            if mine and (meta.get("status") != ResearchStatus.ACTIVE or "ended_reason" in meta):
                other.topic = {k: v for k, v in meta.items() if k != "ended_reason"}
                other.topic["status"] = str(ResearchStatus.ACTIVE)
            elif not mine and meta.get("status") == ResearchStatus.ACTIVE:
                other.topic = {**meta, **parked}
            if other.topic is not meta:
                store.write_topic(other)
        projects.topic_asked(directory, None)  # a topic is active again: nothing is asked


def set_budget(share: float | None = None, ceiling: float | None = None, meter_reset: bool = False,
               usage: float | None = None, reserve: int | None = None, release: bool = False,
               project: str | None = None) -> dict[str, Any]:
    """`research budget`: show or set the day's share and the week's ceiling (whichever binds first stops the run),
    open a fresh week once the user confirmed a meter reset, or reserve and release one project session's runs."""
    if reserve is not None or release:
        if reserve is not None and release:
            raise UsageError("--reserve and --release exclude each other")
        if not project or share is not None or ceiling is not None or meter_reset or usage is not None:
            raise UsageError("--reserve and --release go with --project only",
                             hint="plsi research budget --reserve <runs> --project '<project>'")
        named = projects.resolve(project)
        return ledger.release(named["id"]) if release else ledger.reserve(named["id"], reserve)
    if project:
        raise UsageError("--project goes with --reserve or --release", hint="plsi research budget --help")
    if meter_reset:
        if share is not None or ceiling is not None:
            raise UsageError("--meter-reset goes on its own, with --usage",
                             hint="plsi research budget --meter-reset --usage <percent used, read now>")
        budget = ledger.meter_reset(ledger.reading(usage), today())
        _log_everywhere({"event": str(ResearchLogEvent.BUDGET), "meter_reset": budget["meter_reset"]})
        note = "the weekly meter reset: today and the week start again at this reading"
    elif usage is not None:
        raise UsageError("--usage goes only with --meter-reset",
                         hint="plsi research next --usage <U> reads the meter for a move")
    elif share is None and ceiling is None:
        budget = ledger.state()
        note = "one allocation covers all research, not one per topic; --share sets the day and --ceiling the week"
    else:
        was = ledger.state().get("share_of_day")
        budget = ledger.set_share(share, today(), ceiling)
        cap = ledger.ceiling(budget)
        if cap and float(budget.get("share_of_day") or 0.0) > cap:
            warn("SHARE_ABOVE_CEILING", f"a day may use {budget['share_of_day']}% but the week is capped at {cap}%, "
                                        "so the first day will use the whole week's allowance")
        _log_everywhere({"event": str(ResearchLogEvent.BUDGET), "from": was, "to": budget.get("share_of_day"),
                         "ceiling": cap})
        note = (f"a day may use {budget.get('share_of_day')}% and the week {cap}%; "
                "takes effect at the next move boundary, for every topic")
    return {"budget": {**budget, "week_ceiling": ledger.ceiling(budget)}, "note": note}


def _log_everywhere(entry: dict[str, Any]) -> None:
    """One line in every topic's log: the budget is one for all research."""
    for name in store.list_topics():
        store.append_log(store.load(name), entry)
