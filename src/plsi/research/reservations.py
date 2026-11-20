"""Today's reservations of billed PandaOmics Agent runs, one entry per project session: a session holds some of
today's oracle cap so parallel sessions do not all spend it at once. A reservation is a promise between sessions;
the oracle's own daily cap is what actually stops a call."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import UsageError, ValidationError
from plsi.policy import oracles
from plsi.research import store
from plsi.research.meter import _load_object

RESERVATIONS_FILE = "reservations.json"  # in research/, beside day.json
BILLED = "pandaclaw"  # the oracle family a session's runs are reserved from


def _reservations_path() -> Path:
    return store.root() / RESERVATIONS_FILE


def _reservations(day: str) -> dict[str, int]:
    """Today's reservations by project id; yesterday's are gone with the UTC day's cap."""
    saved = _load_object(_reservations_path(), "remove it; each session reserves again: "
                                               "plsi research budget --reserve <runs> --project <p>")
    return {k: int(v) for k, v in (saved.get("runs") or {}).items()} if saved.get("day") == day else {}


def reserve(pid: str, runs: int) -> dict[str, Any]:
    """Hold `runs` billed PandaOmics Agent runs of today's cap for one project's session, replacing what that
    project held; refused when today's spend and every reservation together would pass the cap."""
    if runs is None or runs < 0:
        raise UsageError("reserve 0 or more runs", hint="plsi research budget --reserve <runs> --project <p>")
    day = store.today()  # the oracle cap's day
    with store.locked(store.root()):
        held = _reservations(day)
        cap = int(oracles.budget()["cap_per_oracle_per_day"])
        spent = int(oracles.spent_today().get(BILLED, 0))
        others = sum(n for k, n in held.items() if k != pid)
        left = cap - spent - others
        if runs > left:
            raise ValidationError(f"{runs} run(s) asked, {max(left, 0)} left today: {spent} spent and {others} held "
                                  f"by other projects of a cap of {cap}", code="BUDGET_EXCEEDED",
                                  hint="ask for fewer runs, or release another project's: "
                                       "plsi research budget --release --project <p>")
        held[pid] = runs
        files.atomic_write_json(_reservations_path(), {"day": day, "runs": held})
    return {"project": pid, "reserved": runs, "day": day, "left_today": left - runs, "cap": cap, "spent_today": spent,
            "note": "a reservation is a promise between sessions; the oracle's own cap is what stops a call"}


def release(pid: str) -> dict[str, Any]:
    day = store.today()  # the oracle cap's day
    with store.locked(store.root()):
        held = _reservations(day)
        freed = held.pop(pid, 0)
        files.atomic_write_json(_reservations_path(), {"day": day, "runs": held})
    return {"project": pid, "released": freed, "day": day, "held": held}
