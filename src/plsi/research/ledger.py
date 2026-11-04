"""The budget: one allocation per day for all research, a weekly ceiling, and the meter readings that charge them.

Code cannot read the platform meter. The bot reports the reading (percent of this week's limit used) on every
save and on any `next` that follows unsaved work; code charges the rise since the last reading, records its own
character count beside it, and stops the run when a reading went backwards. Enforcement is therefore over a
self-reported number. The estimate for a move is its last observed cost; SEED_COST stands in until then.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import ValidationError, warn
from plsi.research import store
from plsi.vocab.research import ResearchLogEvent, ResearchMove, ResearchSpend

SEED_COST = 1.0  # percentage points of the weekly meter, until a move has been observed once
MOVES_PER_DIRECTION = 3.5  # typical moves to bring one direction to a verdict
CEILING_MULTIPLE = 4.0  # the default weekly ceiling, in days' worth of the daily share
HEADROOM = 10.0  # percentage points of the weekly meter the user keeps for themselves, whatever the share is
BLANK = {"share_of_day": 0.0, "day": None, "opening_usage": None, "last_usage": None,
         "allocated": 0.0, "spent": 0.0, "week": None, "week_spent": 0.0}


def week_of(day: str) -> str:
    """The ISO year-week a date falls in. The meter is weekly, so the ceiling is counted weekly."""
    year, week, _ = date.fromisoformat(day).isocalendar()
    return f"{year}-W{week:02d}"


def _path() -> Path:
    return store.root() / store.DAY_FILE


def state() -> dict[str, Any]:
    """The day's ledger, held once for all research in research/day.json, so switching topic cannot open a
    second allocation on the same day."""
    saved = files.load_json(_path()) if _path().is_file() else {}
    return {**BLANK, **(saved if isinstance(saved, dict) else {})}


def _save(budget: dict[str, Any]) -> None:
    files.atomic_write_json(_path(), budget)


def ceiling() -> float:
    """What research may take out of one week: the number the user named, else four days' worth of the share."""
    budget = state()
    named = budget.get("week_ceiling")
    if named is not None:
        return round(float(named), 4)
    return round(float(budget.get("share_of_day") or 0.0) * CEILING_MULTIPLE, 4)


def set_share(share: float | None, today: str, week_ceiling: float | None = None) -> dict[str, Any]:
    """Set the daily share and/or the weekly ceiling, any non-negative value. A new share applies to today's
    allocation at once; spending already made is never clawed back."""
    budget = state()
    if share is not None:
        budget["share_of_day"] = max(float(share), 0.0)
        if budget.get("day") == today:
            budget["allocated"] = max(float(share), 0.0)
    if week_ceiling is not None:
        budget["week_ceiling"] = max(float(week_ceiling), 0.0)
    _save(budget)
    return budget


def reading(value: Any) -> float:
    """A meter reading as a number: finite, from 0 to 100 percent of the week. Anything else is refused."""
    hint = "the percent of this week's limit used, read now, e.g. 41.5"
    if value is None or isinstance(value, bool):
        raise ValidationError("a meter reading is required", code="USAGE_REQUIRED", hint=hint)
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"usage {value!r} is not a number", code="USAGE_REQUIRED", hint=hint) from None
    if not math.isfinite(number) or not 0.0 <= number <= 100.0:
        raise ValidationError(f"usage {value!r} is not a percent from 0 to 100", code="USAGE_REQUIRED", hint=hint)
    return number


def day_is_open(today: str) -> bool:
    budget = state()
    return budget.get("day") == today and budget.get("opening_usage") is not None


def open_day(usage: float | None, today: str) -> bool:
    """Open today's allocation at the reading just taken, at the full share. Returns whether a day was opened."""
    if day_is_open(today):
        return False
    if usage is None:
        raise ValidationError("a new research day needs the current usage reading", code="USAGE_REQUIRED",
                              hint="plsi research next --topic <topic> --usage <percent of this week's limit used>")
    budget = state()
    week = week_of(today)
    budget.pop("meter_fell", None)
    budget.update(day=today, opening_usage=float(usage), last_usage=float(usage),
                  allocated=float(budget.get("share_of_day") or 0.0), spent=0.0,
                  week=week, week_spent=0.0 if budget.get("week") != week else budget.get("week_spent") or 0.0)
    _save(budget)
    return True


def _fell(usage: float, last: Any) -> bool:
    """Whether a reading is below the last one, which the meter never does inside a week."""
    return last is not None and float(usage) < float(last) - 1e-9


def check_monotonic(usage: float) -> None:
    """The meter only rises inside a week; a reading below the last one today is refused."""
    last = state().get("last_usage")
    if _fell(usage, last):
        raise ValidationError(f"usage {usage} is below the last reading {last} for today",
                              code="USAGE_WENT_BACKWARDS",
                              hint="the meter only rises inside a week; re-read it, or start a new day")


def charge(usage: float, chars_in: int = 0, chars_out: int = 0) -> dict[str, Any]:
    """Charge the rise since the last reading to today and to the week. `chars` is the only number code owns.

    A reading below the last one is either a weekly reset or an under-report, and code cannot tell which: it
    charges nothing, records both readings as `meter_fell`, and `next` ends the run."""
    budget = state()
    chars = chars_in + chars_out
    last = budget.get("last_usage")
    if _fell(usage, last):
        budget["meter_fell"] = {"saw": float(usage), "after": float(last), "day": budget.get("day")}
        _save(budget)
        warn("USAGE_WENT_BACKWARDS", f"the meter read {usage} after {last}. Either the week reset or the "
                                     "reading was low; the run ends here and the next day opens fresh")
        return {"delta": None, "chars": chars, "spent": budget.get("spent", 0.0), "reported": False,
                "meter_fell": budget["meter_fell"]}
    delta = round(float(usage) - float(last if last is not None else usage), 4)
    opening = budget.get("opening_usage")
    budget["last_usage"] = float(usage)
    budget["spent"] = round(float(usage) - float(opening if opening is not None else usage), 4)
    budget["week_spent"] = round(float(budget.get("week_spent") or 0.0) + max(delta, 0.0), 4)
    over = round(budget["spent"] - float(budget.get("allocated") or 0.0), 4)
    _save(budget)
    if over > 0:
        warn("OVER_ALLOCATION", f"this move put the day {over} over its allocation. Tomorrow opens at the "
                                 "full share; the overrun counts against the week's ceiling")
    return {"delta": delta, "chars": chars, "spent": budget["spent"], "reported": True,
            "over_allocation": over if over > 0 else 0.0}


def headroom(usage: float | None) -> dict[str, Any]:
    """Whether the week still has the user's reserve after research takes its share."""
    budget = state()
    reading = usage if usage is not None else budget.get("last_usage")
    if reading is None:
        return {"ok": True, "left": None, "need": None}
    left = round(100.0 - float(reading), 4)
    need = round(float(budget.get("share_of_day") or 0.0) + HEADROOM, 4)
    return {"ok": left >= need, "left": left, "need": need, "keeps_back": HEADROOM}


def clear_meter_fell() -> None:
    """A fallen reading stops the day it happened on, not every day after it."""
    budget = state()
    if budget.pop("meter_fell", None) is not None:
        _save(budget)


def is_off() -> bool:
    """A share or ceiling of zero is the user's "Off": no day opens and nothing is logged."""
    return float(state().get("share_of_day") or 0.0) <= 0 or ceiling() <= 0


def _deltas(log: list[dict[str, Any]], move: str | None = None) -> list[float]:
    return [line["cost"]["delta"] for line in log
            if (move is None or line.get("move") == move) and (line.get("cost") or {}).get("delta") is not None]


def estimate(log: list[dict[str, Any]], move: str) -> dict[str, Any]:
    """The last observed cost of this move, then the dearest move seen, then the seed."""
    own = _deltas(log, move)
    if own:
        return {"cost": max(own[-1], 0.0), "basis": f"last observed {move}"}
    seen = _deltas(log)
    if seen:
        return {"cost": max(max(seen), 0.0), "basis": "the dearest move observed so far"}
    return {"cost": SEED_COST, "basis": "seed estimate; no move has been observed yet"}


def typical(log: list[dict[str, Any]]) -> float:
    """The median cost of a move, for planning how far the remainder reaches; steadier than the last sample."""
    seen = sorted(_deltas(log))
    return seen[len(seen) // 2] if seen else SEED_COST


def affordable(log: list[dict[str, Any]], move: str) -> dict[str, Any]:
    """Whether the remaining allocation covers this move, what each move would cost, and how far it reaches."""
    budget = state()
    allocated = float(budget.get("allocated") or 0.0)
    spent = float(budget.get("spent") or 0.0)
    remaining = round(allocated - spent, 4)
    est = estimate(log, move)
    per_move = max(typical(log), est["cost"], 1e-6)
    week_spent = float(budget.get("week_spent") or 0.0)
    costs = {str(m): estimate(log, str(m))["cost"] for m in ResearchMove}
    return {
        "allocated": allocated, "spent": round(spent, 4), "remaining": remaining,
        "share_of_day": budget.get("share_of_day"), "day": budget.get("day"),
        "week": budget.get("week"), "week_spent": round(week_spent, 4),
        "week_ceiling": ceiling(), "week_left": round(ceiling() - week_spent, 4),
        "next_move": move, "estimate": est["cost"], "estimate_basis": est["basis"],
        "ok": remaining >= est["cost"],
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
    for line in log:
        if day is None or line.get("day") != day or line.get("event") == ResearchLogEvent.DAY:
            continue
        if line.get("event") == ResearchLogEvent.READING:
            segments[ResearchSpend.NOTHING] += float(line.get("delta") or 0.0)
            continue
        cost = float((line.get("cost") or {}).get("delta") or 0.0)
        if not line.get("productive"):
            segments[ResearchSpend.NOTHING] += cost
        elif (line.get("change") or {}).get("closed"):
            segments[ResearchSpend.CLOSED] += cost
        else:
            segments[ResearchSpend.FOUND] += cost
    spent = round(float(budget.get("spent") or 0.0), 4)
    return {"allocated": allocated, "spent": spent, "remaining": round(allocated - spent, 4),
            "segments": {k: round(v, 4) for k, v in segments.items()},
            "moves": {str(move): sum(line.get("move") == move for line in log) for move in ResearchMove}}
