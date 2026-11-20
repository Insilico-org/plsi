"""Where the lab journal lives under PLSI_HOME: entries with their files, plasmids, day plans and the page."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from plsi.paths import plsi_home, safe_join, validate_id


def root() -> Path:
    return plsi_home() / "journal"


def entry_dir(entry_id: str) -> Path:
    return safe_join(root() / "entries", validate_id(entry_id, "entry id"))


def has_entry(entry_id: str) -> bool:
    return (entry_dir(entry_id) / "entry.json").is_file()


def plasmid_path(name: str) -> Path:
    return safe_join(root() / "plasmids", validate_id(name, "plasmid name") + ".json")


def day_path(day: dt.date) -> Path:
    return safe_join(root() / "days", day.isoformat() + ".json")


def page_path() -> Path:
    return root() / "journal.html"
