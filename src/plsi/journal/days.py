"""The bench planner: one plan per day (`journal/days/<date>.json`) and `journal today`, the day as code sees it."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Any

from pydantic import Field

from plsi.clock import now
from plsi.errors import NotFound
from plsi.files import atomic_write_json, load_json
from plsi.journal import analysis, home, store
from plsi.journal.results import Slug, Text
from plsi.journal.tuning import DAYS_AHEAD
from plsi.models import Model, parse
from plsi.vocab.journal import EntryStatus


class DayItem(Model):
    text: Text
    time: Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")] | None = None  # "09:30"
    entry: Slug | None = None  # the journal entry this item works on
    project: str | None = None
    done: bool = False
    note: Text | None = None


class DayPlan(Model):
    """What the researcher means to do on one day (`plsi journal day save`); saving it again replaces it."""

    date: dt.date
    items: list[DayItem] = Field(default=[], max_length=80)
    note: Text | None = None


def plans() -> list[dict[str, Any]]:
    folder = home.root() / "days"
    return [load_json(p) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []


def save(file: str) -> dict[str, Any]:
    """`journal day save --file day.json`: the day's plan, replacing an earlier one for that date."""
    plan = parse(DayPlan, load_json(file))
    if missing := sorted({i.entry for i in plan.items if i.entry and not home.has_entry(i.entry)}):
        raise NotFound(f"items name entries not in the journal: {', '.join(missing)}", code="ENTRY_NOT_FOUND",
                       hint="save the entry first (status planned), or drop the link")
    path = home.day_path(plan.date)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, {**plan.dump(), "saved_at": now().isoformat()}, private=True)
    return {"date": plan.date.isoformat(), "items": len(plan.items), "done": sum(i.done for i in plan.items), "path": str(path)}


def today(date: dt.date | None = None) -> dict[str, Any]:
    """`journal today [--date]`: the plan, running experiments with progress and next step, entries of the day,
    their flags, and the planned work of the days ahead."""
    day = date or now().date()
    ahead_to = day + dt.timedelta(days=DAYS_AHEAD)
    path = home.day_path(day)
    plan = load_json(path) if path.is_file() else {"date": day.isoformat(), "items": []}
    running, of_day, ahead, flags = [], [], [], []
    for doc, e in store.entries():
        status = store.status_of(doc)
        row = {"id": e.id, "title": e.title, "kind": e.kind.value, "project": e.project, "date": e.date.isoformat(),
               "status": status, "steps_done": sum(s.done for s in e.protocol), "steps": len(e.protocol),
               "next_step": next((s.text for s in e.protocol if not s.done), None)}
        running += [row] if status == EntryStatus.RUNNING else []
        of_day += [row] if e.date == day else []
        ahead += [row] if status == EntryStatus.PLANNED and day < e.date <= ahead_to else []
        if status == EntryStatus.RUNNING or e.date == day:
            flags += [f"{e.title}: {c}" for c in analysis.checks(store.derived(e.id, e.results))]
    items = plan.get("items", [])
    return {"date": day.isoformat(), "weekday": day.strftime("%A"), "plan": plan, "open": sum(not i.get("done") for i in items),
            "done": sum(bool(i.get("done")) for i in items), "running": running, "entries_of_the_day": of_day,
            "planned_ahead": sorted(ahead, key=lambda r: r["date"]), "flags": flags,
            "plans_ahead": [{"date": p["date"], "items": len(p.get("items", []))} for p in plans()
                            if day.isoformat() < p["date"] <= ahead_to.isoformat()]}
