"""Time: aware-UTC now (overridable in tests), ISO parsing, filename timestamps."""

from __future__ import annotations

import os
import re
from datetime import UTC, date, datetime


def now() -> datetime:
    """Aware UTC now; PLSI_NOW (ISO) is honoured only when PLSI_TEST_MODE=1."""
    if os.environ.get("PLSI_TEST_MODE") == "1" and os.environ.get("PLSI_NOW"):
        return parse_time(os.environ["PLSI_NOW"])
    return datetime.now(UTC)


def parse_time(value: str | date | datetime) -> datetime:
    """ISO date or datetime -> aware UTC datetime. Date-only -> T12:00:00Z; naive -> assumed UTC."""
    if isinstance(value, str):
        s = value.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            value = date.fromisoformat(s)
        else:
            try:
                value = datetime.fromisoformat(s)
            except ValueError:
                raise ValueError(f"not an ISO date or datetime: {value!r}") from None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, 12, tzinfo=UTC)
    raise ValueError(f"not a date or datetime: {value!r}")


def ts_filename(dt: datetime | None = None) -> str:
    return (dt or now()).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
