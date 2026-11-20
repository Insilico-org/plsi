"""The week ledger: the day's allocation held once for all research in research/day.json, the weekly ceiling and
the user's headroom, and the charging of the self-reported meter.

Code cannot read the platform meter: the bot reports the reading (percent of this week's limit used) at the start
and end of each research run (runs.py), and outside a run on every save and on any `next` after unsaved work; code
charges the rise since the last one and stops when a reading went backwards. Enforcement is therefore over a
self-reported number.
"""

from __future__ import annotations

import math
from datetime import date
from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import ValidationError, warn
from plsi.research import store
from plsi.research.tuning import CEILING_MULTIPLE, HEADROOM, START_HOUR

BLANK = {"share_of_day": 0.0, "day": None, "opening_usage": None, "last_usage": None,
         "allocated": 0.0, "spent": 0.0, "week": None, "week_spent": 0.0, "start_hour": START_HOUR}


def week_of(day: str) -> str:
    """The ISO year-week a date falls in. The meter is weekly, so the ceiling is counted weekly."""
    year, week, _ = date.fromisoformat(day).isocalendar()
    return f"{year}-W{week:02d}"


def week_spent(budget: dict[str, Any], today: str | None = None) -> float:
    """What research has spent this week: 0 once the calendar week is not the ledger's, before a day opens in it."""
    if budget.get("week") != week_of(today or store.today()):
        return 0.0
    return float(budget.get("week_spent") or 0.0)


def _path() -> Path:
    return store.root() / store.DAY_FILE


def _load_object(path: Path, hint: str) -> dict[str, Any]:
    """A ledger file's JSON object, {} while it does not exist; anything else is refused."""
    saved = files.load_json(path) if path.is_file() else {}
    if not isinstance(saved, dict):
        raise ValidationError(f"{path} is not a JSON object", code="BAD_LEDGER", hint=hint)
    return saved


def state() -> dict[str, Any]:
    """The day's ledger, held once for all research in research/day.json, so switching topic cannot open a
    second allocation on the same day."""
    return {**BLANK, **_load_object(_path(), "remove it and set the budget again: "
                                             "plsi research budget --share <percent>")}


def _save(budget: dict[str, Any]) -> None:
    files.atomic_write_json(_path(), budget)


def ceiling(budget: dict[str, Any] | None = None) -> float:
    """What research may take out of one week: the number the user named, else four days' worth of the share. Reads
    the ledger unless `budget` is given."""
    budget = state() if budget is None else budget
    named = budget.get("week_ceiling")
    if named is not None:
        return round(float(named), 4)
    return round(float(budget.get("share_of_day") or 0.0) * CEILING_MULTIPLE, 4)


def set_share(share: float | None, today: str, week_ceiling: float | None = None,
              start_hour: int | None = None) -> dict[str, Any]:
    """Set the daily share, the weekly ceiling and/or the UTC hour a research day may start; a negative value is
    refused. A new share applies to today's allocation at once; spending already made is never clawed back."""
    if any(v is not None and not v >= 0 for v in (share, week_ceiling)):
        raise ValidationError("a share or ceiling is a percent of the weekly meter, 0 or more",
                              hint="plsi research budget --share 0 turns research off")
    budget = state()
    if share is not None:
        budget["share_of_day"] = float(share)
        if budget.get("day") == today:
            budget["allocated"] = float(share)
    if week_ceiling is not None:
        budget["week_ceiling"] = float(week_ceiling)
    if start_hour is not None:
        if not 0 <= int(start_hour) <= 23:
            raise ValidationError("the start hour is a UTC hour from 0 to 23", hint="plsi research budget --start-hour 6")
        budget["start_hour"] = int(start_hour)
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
    _save(_open(budget, usage, today, week_spent(budget, today)))
    return True


def _open(budget: dict[str, Any], usage: float, today: str, week_spent: float) -> dict[str, Any]:
    """Today's allocation at the full share, opened at `usage`; the week carries `week_spent`."""
    budget.pop("meter_fell", None)
    budget.update(day=today, opening_usage=float(usage), last_usage=float(usage),
                  allocated=float(budget.get("share_of_day") or 0.0), spent=0.0, week=week_of(today),
                  week_spent=week_spent)
    return budget


def _fell(usage: float, last: Any) -> bool:
    """Whether a reading is below the last one, which the meter never does inside a week."""
    return last is not None and float(usage) < float(last) - 1e-9


def meter_reset(usage: float, today: str) -> dict[str, Any]:
    """The user confirmed that the weekly meter reset: open today and a fresh week at the reading just taken.

    Code cannot tell a reset from a low reading, so only the user's answer opens the new week; a reading that is not
    below the last one is no reset and is refused."""
    budget = state()
    last = budget.get("last_usage")
    if not _fell(usage, last):
        raise ValidationError(f"usage {usage} is not below the last reading {last}, so the meter did not reset",
                              code="NO_METER_RESET",
                              hint="plsi research next --usage <percent of this week's limit used, read now>")
    budget = _open(budget, usage, today, 0.0)
    budget["meter_reset"] = {"saw": float(usage), "after": float(last), "day": today}
    _save(budget)
    return budget


def charge(usage: float, chars_in: int = 0, chars_out: int = 0) -> dict[str, Any]:
    """Charge the rise since the last reading to today and to the week. `chars` is the only number code owns.

    A reading below the last one is either a weekly reset or an under-report, and code cannot tell which: it
    charges nothing, records both readings as `meter_fell`, and `next` ends the run."""
    budget = state()
    chars = chars_in + chars_out
    last = budget.get("last_usage")
    if _fell(usage, last):
        # today, not the ledger's day: a run that ends after midnight UTC must still stop the new day
        budget["meter_fell"] = {"saw": float(usage), "after": float(last), "day": store.today()}
        _save(budget)
        warn("USAGE_WENT_BACKWARDS", f"the meter read {usage} after {last}. Either the week reset or the "
                                     "reading was low; the run ends here. If the user confirms a reset: "
                                     f"plsi research budget --meter-reset --usage {usage}")
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


def rebase(usage: float) -> dict[str, Any]:
    """A run starts on an open day: what the meter rose since the last reading is not research (the user's own use,
    between runs), so the day's opening moves up with it and nothing is charged. A reading below the last one is
    recorded as `meter_fell`, as `charge` does."""
    budget = state()
    last = budget.get("last_usage")
    if _fell(usage, last):
        return charge(usage)
    gap = float(usage) - float(last if last is not None else usage)
    opening = budget.get("opening_usage")
    budget["opening_usage"] = round(float(opening if opening is not None else usage) + gap, 4)
    budget["last_usage"] = float(usage)
    _save(budget)
    return {"delta": 0.0, "not_research": round(gap, 4)}


def headroom(usage: float | None) -> dict[str, Any]:
    """Whether the week still has the user's reserve after research takes its share."""
    budget = state()
    reading = usage if usage is not None else budget.get("last_usage")
    if reading is None:
        return {"ok": True, "left": None, "need": None}
    left = round(100.0 - float(reading), 4)
    need = round(float(budget.get("share_of_day") or 0.0) + HEADROOM, 4)
    return {"ok": left >= need, "left": left, "need": need, "keeps_back": HEADROOM}


def meter_fell(today: str) -> dict[str, Any] | None:
    """The fallen reading that stops today, if any. It stops the day it happened on, not every day after it."""
    budget = state()
    fell = budget.get("meter_fell")
    if fell and fell.get("day") != today:
        budget.pop("meter_fell")
        _save(budget)
        return None
    return fell


def is_off() -> bool:
    """A share or ceiling of zero is the user's "Off": no day opens and nothing is logged."""
    budget = state()
    return float(budget.get("share_of_day") or 0.0) <= 0 or ceiling(budget) <= 0
