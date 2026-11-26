"""The budget: one allocation per day for all research, a target the projects still working today share evenly
(`part`), with carry-on: a project that stops for the day hands what it did not spend to the others. A weekly
ceiling and the user's headroom are the hard stops. Also the meter readings that charge them, the project picker
(`pick_next`), the starvation check, and today's reservations of billed PandaOmics Agent runs, one per project
session.

The work is split by concern across `meter` (the week ledger: the day's allocation state, the weekly ceiling, and
charging the self-reported meter), `costing` (what a move costs, read off the run log), `allocation` (the day
shared out with carry-on), `picking` (the project the next run works) and `reservations` (billed PandaOmics Agent
runs held per session). This module re-exports that surface so `from plsi.research.ledger import X` and `ledger.X`
keep working from one place.
"""

from __future__ import annotations

from plsi.research.allocation import affordable, bar, part, share, starving, working
from plsi.research.costing import estimate, typical
from plsi.research.meter import (BLANK, ceiling, charge, day_is_open, headroom, is_off, meter_fell, meter_reset,
                                 open_day, over_quota, quota_renewed, reading, rebase, set_share, state, week_of, week_spent, _save)
from plsi.research.picking import pick_next
from plsi.research.reservations import BILLED, RESERVATIONS_FILE, release, reserve

__all__ = [
    # meter: the week ledger, the weekly ceiling, charging the meter
    "BLANK", "week_of", "week_spent", "state", "ceiling", "set_share", "reading", "day_is_open", "open_day",
    "meter_reset", "charge", "rebase", "headroom", "meter_fell", "is_off",
    "over_quota", "quota_renewed",
    # costing: what a move costs, read off the run log
    "estimate", "typical",
    # allocation: the day shared out, with carry-on
    "working", "share", "part", "affordable", "bar", "starving",
    # picking: the project the next run works
    "pick_next",
    # reservations: billed PandaOmics Agent runs held per session
    "RESERVATIONS_FILE", "BILLED", "reserve", "release",
]
