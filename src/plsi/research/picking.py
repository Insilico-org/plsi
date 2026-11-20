"""The project the next run works: of the projects still working today, the one furthest below its part of the
day's allocation, with a project whose topic card went unanswered on an earlier day as a candidate too."""

from __future__ import annotations

from typing import Any

from plsi.research import projects, store
from plsi.research.allocation import share, working
from plsi.vocab.research import ProjectStatus


def pick_next(last_runs: dict[str, str] | None = None) -> dict[str, Any] | None:
    """The project the next run works: of the projects still working today, the one furthest below its part (the
    largest remainder), ties to the one whose last run (`last_runs`: id -> time) is oldest. A project whose card
    for a topic went unanswered on an earlier day is a candidate too, so its run takes the top candidate. None
    when nothing is left to work on."""
    today, last_runs = store.today(), last_runs or {}
    at_work = working()
    overdue = [(d, m) for d, m in projects.scan()
               if m.get("status") == ProjectStatus.ACTIVE and m.get("topic_asked") is not None
               and str(m["topic_asked"]) < today and store.active_name(d, required=False) is None]
    found = [{"project": projects.card(m), "part": share(d, at_work)} for d, m in at_work + overdue]
    found.sort(key=lambda c: (-c["part"]["project_remaining"], last_runs.get(c["project"]["id"], "")))
    return found[0] if found else None
