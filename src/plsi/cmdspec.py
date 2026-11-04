"""The shape of a command table entry (`Cmd`), the argparse shorthands the tables are written in, and `merge`,
which joins the package tables into one. plsi.cli parses and dispatches the result."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from plsi import clock


def iso_datetime(value: str) -> datetime:
    return clock.parse_time(value)


def iso_date(value: str) -> date:
    return date.fromisoformat(value)


def A(*flags: str, **kw: Any) -> tuple[tuple[str, ...], dict[str, Any]]:
    return flags, kw


def V(enum: type[StrEnum]) -> list[str]:
    """argparse choices as plain values (Python 3.11 shows enum members as reprs in usage errors)."""
    return [m.value for m in enum]


def MX(*args: tuple[tuple[str, ...], dict[str, Any]], required: bool = True) -> tuple[str, tuple, bool]:
    return "__mx__", args, required


INSTANCE = A("--instance", required=True, help="instance name")
FILE = A("--file", required=True, help="input path ('-' = stdin)")
PLAN = A("--plan", dest="plan_id", required=True, help="plan id")
MAP = A("--map", dest="map_id", required=True)
MAP_OPT = A("--instance", help="include this instance's user maps")
SENDER = A("--instance", help="the contributor's instance (install token); omit for professional files")
HASH = A("--hash", dest="expected", required=True, help="package_hash of the checked file the user approved")


@dataclass(frozen=True)
class Cmd:
    target: str
    args: tuple = ()
    help: str = ""
    next: tuple[str, ...] = ()


def merge(*tables: dict[str, Cmd]) -> dict[str, Cmd]:
    """One command table from several, in order; a command name in two tables raises."""
    out: dict[str, Cmd] = {}
    for table in tables:
        if clash := sorted(out.keys() & table.keys()):
            raise ValueError(f"command defined twice: {', '.join(clash)}")
        out.update(table)
    return out
