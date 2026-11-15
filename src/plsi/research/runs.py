"""The run log, research/runs.jsonl: one line per run event (vocab `RunEvent`), since the bot cannot see a routine's
run history; and how a run's metered rise reaches the moves it saved. Imports only the store, so the loop, the save
and the ledger can all read it; the commands are in chain.py."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from plsi import files
from plsi.clock import now, parse_time
from plsi.research import store
from plsi.research.tuning import OPEN_RUN_STALE_MIN, SEED_RUN_COST
from plsi.vocab.research import ResearchLogEvent, RunEvent

RUNS_FILE = "runs.jsonl"  # in research/, beside day.json


def path() -> Path:
    return store.root() / RUNS_FILE


def read() -> list[dict[str, Any]]:
    return files.read_jsonl(path())


def log(event: RunEvent, run: str | None, source: str | None = None, **fields: Any) -> dict[str, Any]:
    """Append one line; fields that are None are left out. The watchdog and a run can race, so it holds the
    research root's lock."""
    line = {"at": now().isoformat(), "event": str(event), "run": run, "source": None if source is None else str(source),
            **{k: v for k, v in fields.items() if v is not None}}
    with store.locked(store.root()):
        files.append_jsonl(path(), line)
    return line


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def age_minutes(line: dict[str, Any]) -> float:
    return (now() - parse_time(line["at"])).total_seconds() / 60


def unended(lines: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The newest start whose run never logged an end, however old."""
    lines = read() if lines is None else lines
    ended = {line.get("run") for line in lines if line.get("event") == RunEvent.END}
    return next((line for line in reversed(lines)
                 if line.get("event") == RunEvent.START and line.get("run") not in ended), None)


def beat(run: dict[str, Any]) -> None:
    """A `next` or `save` inside `run`: it is still working, however long ago it started."""
    log(RunEvent.BEAT, run["run"], run.get("source"), project=run.get("project"))


def idle_minutes(run: dict[str, Any], lines: list[dict[str, Any]] | None = None) -> float:
    """Minutes since `run` (its start line) last showed it was working: its start or its newest `beat`."""
    lines = read() if lines is None else lines
    seen = [line for line in lines
            if line.get("run") == run["run"] and line.get("event") in (RunEvent.START, RunEvent.BEAT)]
    return min(age_minutes(line) for line in seen or [run])


def open_run(project: str | None = None, lines: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The run in progress: not ended, and working (a start, `next` or `save`) within OPEN_RUN_STALE_MIN minutes;
    on `project` (an id) when named. Inside it `next` and `save` need no meter reading: the run is metered at its
    start and end."""
    lines = read() if lines is None else lines
    run = unended(lines)
    if run and idle_minutes(run, lines) < OPEN_RUN_STALE_MIN and project in (None, run.get("project")):
        return run
    return None


def last_kicked(lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest `kicked` line: the run last asked for, and once the webhook answered, what it said."""
    return next((line for line in reversed(lines) if line.get("event") == RunEvent.KICKED), None)


def refused(lines: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The last kick, when the webhook refused it (a wrong or revoked address or key, or no network)."""
    kicked = last_kicked(lines)
    return kicked if kicked and kicked.get("failed") is not None else None


def last_runs(lines: list[dict[str, Any]]) -> dict[str, str]:
    """Each project's newest start time, for the picker's tie-break."""
    return {line["project"]: line["at"] for line in lines
            if line.get("event") == RunEvent.START and line.get("project")}


def of_day(lines: list[dict[str, Any]], event: RunEvent, day: str) -> list[dict[str, Any]]:
    return [line for line in lines if line.get("event") == event and line.get("day") == day]


def run_cost(lines: list[dict[str, Any]]) -> float:
    """The median meter rise of a run that rose, else the seed."""
    rises = sorted(float(line["rise"]) for line in lines
                   if line.get("event") == RunEvent.END and (line.get("rise") or 0) > 0)
    return rises[len(rises) // 2] if rises else SEED_RUN_COST


def costed(log_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A topic's log with each run's rise spread over the moves it saved: a move saved inside a run has no reading of
    its own (`cost.delta` None) and takes the `each` of its run's `run` line, which then counts no more. A run line
    that spread nothing (`each` None) keeps its whole rise, like an unsaved reading."""
    each = {line.get("run"): line.get("each") for line in log_lines if line.get("event") == ResearchLogEvent.RUN}
    out = []
    for line in log_lines:
        if line.get("event") == ResearchLogEvent.RUN and line.get("each") is not None:
            continue
        cost = line.get("cost") or {}
        if line.get("move") and cost.get("delta") is None and each.get(line.get("run")) is not None:
            line = {**line, "cost": {**cost, "delta": each[line["run"]]}}
        out.append(line)
    return out
