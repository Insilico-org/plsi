"""Durable summary safety lines (`red_flag:`, `scope:`, `caution:`) and how each one counts: red_flag and scope
are hard stops, a soft `caution:` never declines a plan."""

from __future__ import annotations

import re
from typing import Literal

_LINE_RE = re.compile(r"^(?P<kind>red_flag|scope|caution):\s*(?P<body>.+?)\s*$", re.MULTILINE)
_CLASS: dict[str, Literal["hard_stop", "soft_caution"]] = {"red_flag": "hard_stop", "scope": "hard_stop",
                                                            "caution": "soft_caution"}
MOOD_SCREEN_TOKEN = "mood-screen-positive"


def extract_safety_lines(summary: str) -> list[dict[str, str]]:
    """Ordered `{kind, body, line}` for every safety line in the summary."""
    return [{"kind": m["kind"], "body": m["body"].strip(), "line": f"{m['kind']}: {m['body'].strip()}"}
            for m in _LINE_RE.finditer(summary or "")]


def classify_line(line: dict[str, str]) -> Literal["hard_stop", "soft_caution", "other"]:
    return _CLASS.get(line.get("kind", ""), "other")


def has_mood_screen_caution(summary: str) -> bool:
    """The summary carries `caution: mood-screen-positive`."""
    return any(line["kind"] == "caution" and MOOD_SCREEN_TOKEN in line["body"] for line in extract_safety_lines(summary))
