"""The daily budget shared out, with carry-on: one day's allocation split evenly across the projects still working
today, where a project that stops for the day hands what it did not spend to the others. A project's part
(`share`, `part`), whether the next move is affordable (`affordable`), today's spend segmented by what it bought
(`bar`), the projects still working (`working`), and the starvation check (`starving`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files
from plsi.research import projects, runs, store
from plsi.research.costing import estimate, typical
from plsi.research.meter import ceiling, state, week_spent
from plsi.research.tuning import MOVES_PER_DIRECTION, SEED_RUN_COST
from plsi.vocab.research import ProjectStatus, ResearchLogEvent, ResearchMove, ResearchSpend, ResearchStop


def _line_cost(line: dict[str, Any]) -> float:
    """What one line of a `runs.costed` log charged: an unsaved reading's rise, a run's rise that no move took, or a
    saved move's cost; 0 for any other line."""
    if line.get("event") in (ResearchLogEvent.READING, ResearchLogEvent.RUN):
        return float(line.get("delta") or 0.0)
    return float((line.get("cost") or {}).get("delta") or 0.0)


def _spent_by(logs: list[list[dict[str, Any]]], day: str | None) -> float:
    """What these topics' logs charged on `day`."""
    return round(sum(_line_cost(line) for log in logs for line in runs.costed(log)
                     if day is not None and line.get("day") == day), 4)


def _stopped_today(log: list[dict[str, Any]], day: str) -> bool:
    """Whether the topic stopped for the day: stuck on its first move today. A spent part is no stop, since
    carry-on can refill it; a finished topic is no longer active at all."""
    return any(line.get("event") == ResearchLogEvent.STOP and line.get("why") == ResearchStop.STUCK
               and line.get("day") == day for line in log)


def working() -> list[tuple[Path, dict[str, Any]]]:
    """(folder, frontmatter) of the projects still working today: active (not on hold, not closed), with an active
    topic that has not stopped for the day."""
    out = []
    for directory, meta in projects.scan():
        name = meta.get("status") == ProjectStatus.ACTIVE and store.active_name(directory, required=False)
        if name and not _stopped_today(files.read_jsonl(directory / store.TOPICS_FOLDER / name / store.LOG_FILE),
                                       store.today()):
            out.append((directory, meta))
    return out


def _project_spent(directory: Path, day: str | None) -> float:
    return _spent_by([files.read_jsonl(d / store.LOG_FILE) for d in store.topic_dirs(directory)], day)


def share(directory: Path, at_work: list[tuple[Path, dict[str, Any]]] | None = None) -> dict[str, Any]:
    """A project's part of today's allocation, with carry-on: what the projects that are not working spent today
    comes off the day, and the rest is split evenly across the working ones and this one; less what this project's
    topics charged today. `at_work` is `working()`, when the caller has it."""
    budget = state()
    day = budget.get("day")
    sharing = {d.resolve() for d, _ in (working() if at_work is None else at_work)} | {directory.resolve()}
    stopped = round(sum(_project_spent(d, day) for d in store.project_dirs() if d.resolve() not in sharing), 4)
    allocated = round(max(float(budget.get("allocated") or 0.0) - stopped, 0.0) / len(sharing), 4)
    spent = _project_spent(directory, day)
    return {"projects_sharing": len(sharing), "spent_by_stopped": stopped, "project_allocated": allocated,
            "project_spent": spent, "project_remaining": round(allocated - spent, 4)}


def part(graph: store.Graph) -> dict[str, Any]:
    """This topic's project's part of today's allocation (`share`)."""
    return share(store.project_of(graph))


def affordable(graph: store.Graph, log: list[dict[str, Any]], move: str | None = None) -> dict[str, Any]:
    """Whether what is left covers `move` (default: the move the topic's cursor holds), what each move would cost and
    how far it reaches. What is left is the smaller of the day's remainder and the topic's project's `part`."""
    move = str(move or (graph.topic.get("cursor") or {}).get("move") or ResearchMove.ASK)
    share_, budget = part(graph), state()
    allocated = float(budget.get("allocated") or 0.0)
    spent = float(budget.get("spent") or 0.0)
    remaining = min(round(allocated - spent, 4), share_["project_remaining"])
    est = estimate(log, move)
    per_move = max(typical(log), est["cost"], 1e-6)
    spent_week, cap = week_spent(budget), ceiling(budget)
    costs = {str(m): estimate(log, str(m))["cost"] for m in ResearchMove}
    return {
        **share_,
        "allocated": allocated, "spent": round(spent, 4), "remaining": remaining,
        "share_of_day": budget.get("share_of_day"), "day": budget.get("day"),
        "week": budget.get("week"), "week_spent": round(spent_week, 4),
        "week_ceiling": cap, "week_left": round(cap - spent_week, 4),
        "next_move": move, "estimate": est["cost"], "estimate_basis": est["basis"],
        # inside a run the move is metered at the run's end: any remainder starts it, whatever the estimate
        "ok": remaining > 0 if runs.open_run(graph.topic.get("project")) else remaining >= est["cost"],
        "affordable": {m: round(c, 2) for m, c in costs.items() if remaining >= c},
        "a_typical_move_costs": round(typical(log), 2),
        "directions_reached": int(max(remaining, 0) // (per_move * MOVES_PER_DIRECTION)),
    }


def bar(log: list[dict[str, Any]]) -> dict[str, Any]:
    """Today's spend, segmented by what it bought. No completion percentage: research has no known total.

    The segments count this topic's log lines dated the ledger's day; `spent` is that day's spend across every
    topic."""
    budget = state()
    allocated = float(budget.get("allocated") or 0.0)
    segments = {str(s): 0.0 for s in ResearchSpend}
    day = budget.get("day")
    for line in runs.costed(log):
        if day is None or line.get("day") != day or line.get("event") == ResearchLogEvent.DAY:
            continue
        cost = _line_cost(line)
        if line.get("event") in (ResearchLogEvent.READING, ResearchLogEvent.RUN) or not line.get("productive"):
            segments[ResearchSpend.NOTHING] += cost
        elif (line.get("change") or {}).get("closed"):
            segments[ResearchSpend.CLOSED] += cost
        else:
            segments[ResearchSpend.FOUND] += cost
    spent = round(float(budget.get("spent") or 0.0), 4)
    return {"allocated": allocated, "spent": spent, "remaining": round(allocated - spent, 4),
            "segments": {k: round(v, 4) for k, v in segments.items()},
            "moves": {str(move): sum(line.get("move") == move for line in log) for move in ResearchMove}}


def starving(run_cost: float = SEED_RUN_COST) -> dict[str, Any] | None:
    """Too many projects for the share: each working project's part of the day is below one run's cost, so none
    makes real progress. Says how many to put on hold; None when the parts are big enough, or when holding would
    leave fewer than one (a lone project starves no other)."""
    n = len(working())
    day = float(state().get("share_of_day") or 0.0)
    if not n or day <= 0 or day / n >= run_cost:
        return None
    hold = n - max(int(day // run_cost), 1)
    return {"working": n, "part": round(day / n, 4), "a_run_costs": run_cost, "hold": hold} if hold >= 1 else None
