"""`research save`: record one move, all of it or none of it, charge the meter, and advance the cursor.

`next` recommends a question and a move; `save` takes whichever the bot actually worked and records the
divergence. Code refuses dishonest payloads and counts; it never concludes that a direction is finished.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import ValidationError
from plsi.research import cursor as cursors
from plsi.research import frontier, ledger, refusals, store, write
from plsi.research.store import active_name, today
from plsi.research.verdict import MIN_ABSENCE_ROUNDS, verdicts
from plsi.vocab.research import RESOLVED, ResearchDesign, ResearchMove, ResearchStatus

STAGNATION_NOVELTY = 0.2  # a gather whose new share of hits is below this is quiet
SECTIONS = ("expanded", "dropped", "open", "requests")  # the move's own account, kept in the log
# every top-level key a payload may carry; `stop` is listed so that its own refusal explains it
PAYLOAD_KEYS = frozenset({"move", "usage", "chars_in", "chars_out", "nodes", "update", "question",
                          "close_direction", "stop", *SECTIONS})


def _known_keys(payload: dict[str, Any]) -> None:
    """Refuse a top-level key the save does not read, so a misspelt one cannot be silently dropped."""
    unknown = sorted(set(payload) - PAYLOAD_KEYS)
    if unknown:
        raise ValidationError(f"unknown save field {', '.join(map(repr, unknown))}", code="UNKNOWN_FIELD",
                              hint=f"a save carries: {', '.join(sorted(PAYLOAD_KEYS - {'stop'}))}. Nothing was written")


def _chars(payload: dict[str, Any], key: str) -> int:
    """A character count the bot reports beside the reading; a non-negative whole number or absent."""
    value = payload.get(key) or 0
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not str(value).strip().isdigit():
        raise ValidationError(f"{key} {value!r} is not a whole number of characters", hint=f'"{key}": 4200')
    return int(value)


def _started(graph: store.Graph, cursor: dict[str, Any]) -> None:
    """Refuse a save that no `next` started: the topic must be active, research on, today's day open and the
    cursor issued. Recording a move that `next` started and that then ran over its estimate stays allowed."""
    hint = "plsi research next --topic <topic> --usage <percent used>, then work the move it returns"
    if graph.topic.get("status") != ResearchStatus.ACTIVE:
        raise ValidationError(f"topic {graph.name!r} is {graph.topic.get('status')}, so no move can be saved",
                              code="NEXT_REQUIRED",
                              hint=f"plsi research topic --switch '{graph.name}', then plsi research next")
    if ledger.is_off():
        raise ValidationError("research is Off, so no move can be saved", code="NEXT_REQUIRED",
                              hint="plsi research budget --share <percent of the weekly meter per day>")
    if not ledger.day_is_open(today()) or int(cursor.get("attempt") or 0) <= 0:
        raise ValidationError("no move is open: run plsi research next first", code="NEXT_REQUIRED", hint=hint)


def save(topic: str | None = None, file: str | None = None) -> dict[str, Any]:  # noqa: A002 - CLI dest name
    """Validate the payload, write its nodes and updates, charge the reading, log the move and move the cursor.
    Every refusal is raised before the first write; a failed write removes what this save created."""
    payload = files.load_json(file)
    if not isinstance(payload, dict):
        raise ValidationError("the save payload is a JSON object", hint="see skills/shared/research-graph")
    _known_keys(payload)
    usage = ledger.reading(payload.get("usage"))
    chars_in, chars_out = _chars(payload, "chars_in"), _chars(payload, "chars_out")
    graph = store.load(topic or active_name())
    log = store.read_log(graph)
    cursor = dict(graph.topic.get("cursor") or {})
    _started(graph, cursor)
    move = str(payload.get("move") or cursor.get("move") or ResearchMove.ASK)
    if move not in tuple(ResearchMove):
        raise ValidationError(f"unknown move {move!r}", hint=f"one of {', '.join(m for m in ResearchMove)}")
    recommended = str(cursor.get("move") or move)
    chose_otherwise = move != recommended
    suggested_q = cursor.get("question")
    if payload.get("stop"):
        raise ValidationError("`stop` is what `next` returns; it is not a field you write",
                              code="AMBIGUOUS_STOP",
                              hint="to close the direction you are on, use close_direction: '<why it is finished>'. "
                                   "The run ends by itself when the allocation is spent")
    nodes = list(payload.get("nodes") or [])
    updates = list(payload.get("update") or [])
    names = write.allocate(graph, nodes)
    by_title = write.resolve_links(graph, nodes, updates, names)
    # the worked question may be one this same save creates
    worked = write.resolve_name(str(payload["question"]), by_title) if payload.get("question") \
        else (cursor.get("question") or None)
    if payload.get("question") and worked not in graph.nodes and worked not in set(names.values()):
        raise ValidationError(f"no question named {payload['question']!r} in this topic",
                              hint="name a question that exists, or one this save creates; "
                                   "plsi research status lists them")
    refusals.check(graph, move, nodes, updates, names)
    write.check_shapes(graph, nodes, updates)

    before = verdicts(graph)
    live_before = {n: node.get("status") for n, node in graph.nodes.items()}
    open_before = {e["question"] for e in frontier.rank(graph)}
    undo: dict[Path, str | None] = {}
    try:
        created = write.write_nodes(graph, nodes, names, undo)
        changed = write.apply_updates(graph, updates, undo)
    except Exception:
        write.rollback(undo)
        raise

    quiet = _quiet(graph, move, worked)
    signals = _signals(graph, log, move, worked, quiet)
    close_why = str(payload.get("close_direction") or "")
    closed_now = cursors.close(graph, worked, close_why) if close_why and worked else None
    stops = [close_why] if closed_now else []
    ignored = None if closed_now or not close_why else (
        "no question was being worked, so there was no direction to close" if not worked
        else f"{worked!r} was already resolved; its reason stands as written")
    after = verdicts(graph)
    open_after = {e["question"] for e in frontier.rank(graph)}
    change = {
        "created": created, "changed": changed,
        "verdicts_flipped": sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n)),
        # nodes that resolved in this save, not ones that merely left the queue because a child opened
        "closed": sorted(n for n, node in graph.nodes.items()
                         if node.get("status") in RESOLVED and live_before.get(n) not in RESOLVED),
        "frontier": {"added": sorted(open_after - open_before), "left": sorted(open_before - open_after)},
    }
    productive = _productive(change, updates)

    cost = ledger.charge(usage, chars_in, chars_out)
    cursor = cursors.advance(graph, {**cursor, "question": worked}, move, bool(stops))
    graph.topic["cursor"] = cursor
    store.write_topic(graph)
    store.append_log(graph, {
        "move": move, "day": today(), "recommended": recommended if chose_otherwise else None,
        "question": worked, "suggested_question": suggested_q if worked != suggested_q else None,
        "cost": cost, "change": change, "productive": productive, "stops": stops, "signals": signals,
        "quiet": quiet, "sections": {k: payload.get(k) for k in SECTIONS if payload.get(k)},
    })

    budget = ledger.affordable(store.read_log(graph), str(cursor["move"]))
    return {
        "topic": graph.name, "move": move, "change": change, "productive": productive, "cost": cost,
        "instead_of": recommended if chose_otherwise else None,
        "stops": stops, "signals": signals,
        "closed": closed_now, "close_direction_ignored": ignored, "cursor": cursor, "budget": budget,
        "day_continues": budget["ok"],
        "verdicts": after, **frontier.queue(graph),
        "unspent": None if budget["ok"] else budget["remaining"],
        "open": frontier.open_items(graph),
    }


def _productive(change: dict[str, Any], updates: list[dict[str, Any]]) -> bool:
    """Whether the move changed what the research knows. Recording a search that retrieved nothing does not."""
    if change["created"] or change["verdicts_flipped"] or change["closed"]:
        return True
    if not change["changed"]:
        return False
    bookkeeping = [u for u in updates if set(u) <= {"name", "last_search"}]
    if len(bookkeeping) != len(updates):
        return True
    return any(int((u.get("last_search") or {}).get("hits") or 0) for u in bookkeeping)


def _search(graph: store.Graph, question: str | None) -> dict[str, Any]:
    return (graph.nodes.get(question or "") or {}).get("last_search") or {}


def _quiet(graph: store.Graph, move: str, question: str | None) -> bool:
    """Whether this move was a gather whose new share of the hits is below STAGNATION_NOVELTY."""
    search = _search(graph, question)
    hits, new = int(search.get("hits") or 0), int(search.get("new") or 0)
    return move == ResearchMove.GATHER and bool(hits) and new / hits < STAGNATION_NOVELTY


def _signals(graph: store.Graph, log: list[dict[str, Any]], move: str, question: str | None,
             quiet: bool) -> list[str]:
    """Observations about this direction for the bot to weigh; never actions."""
    if not question or question not in graph.nodes:
        return []
    out = []
    search = _search(graph, question)
    hits, rounds = int(search.get("hits") or 0), int(search.get("rounds") or 0)
    if quiet:
        out.append(f"{int(search.get('new') or 0)} of {hits} retrieved sources were new. Either the topic is "
                   "worked out or the query is; close the direction with close_direction if you judge it the first")
    if move == ResearchMove.GATHER and not hits and rounds >= MIN_ABSENCE_ROUNDS:
        out.append(f"{rounds} rounds, nothing retrieved. A recorded absence is a result; close the direction if "
                   "you have earned the claim")
    if _stagnated_before(log, question):
        out.append("the previous gather on this direction was quiet too")
    circular = [h["name"] for h in graph.hypotheses_of(question) if question in (h.get("tested_by") or [])]
    if circular:
        out.append(f"{', '.join(circular)} names this question as what would settle it, which is the question "
                   "that proposed it. Nothing can be decided by its own premise; point it at the question that "
                   "would settle it, or leave it empty and say in the body what would")
    checkable = [s for f in graph.findings_of(question) for s in (f.get("sources") or [])
                 if f.get("design") != ResearchDesign.PERSONAL_RECORD]
    unverified = [s for s in checkable if not s.get("quote_verified")]
    if len(checkable) >= 2 and len(unverified) * 2 > len(checkable):
        out.append(f"{len(unverified)} of {len(checkable)} published quotes here are unchecked - no retrieved "
                   "text was passed with them. Re-pass the source's own words if you can still reach them")
    return out


def _stagnated_before(log: list[dict[str, Any]], question: str) -> bool:
    """Whether the previous Gather on this question was already quiet."""
    for line in reversed(log):
        if line.get("move") == ResearchMove.GATHER and line.get("question") == question:
            return bool(line.get("quiet"))
    return False
