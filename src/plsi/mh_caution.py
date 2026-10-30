"""Extract durable summary safety lines: red_flag / scope / soft caution.

Tiny helper for packaging audits and tests. Soft ``caution:`` is not a hard stop.
"""

from __future__ import annotations

import re
from typing import Literal

_LINE_RE = re.compile(
    r"^(?P<kind>red_flag|scope|caution):\s*(?P<body>.+?)\s*$",
    re.MULTILINE,
)

MOOD_SCREEN_TOKEN = "mood-screen-positive"


def extract_safety_lines(summary: str) -> list[dict[str, str]]:
    """Return ordered ``{kind, body, line}`` dicts for red_flag/scope/caution lines."""
    if not summary:
        return []
    out: list[dict[str, str]] = []
    for m in _LINE_RE.finditer(summary):
        kind = m.group("kind")
        body = m.group("body").strip()
        out.append({"kind": kind, "body": body, "line": f"{kind}: {body}"})
    return out


def classify_line(line: dict[str, str]) -> Literal["hard_stop", "soft_caution", "other"]:
    """Classify one extracted line. Soft caution never declines every plan."""
    kind = line.get("kind", "")
    if kind in ("red_flag", "scope"):
        return "hard_stop"
    if kind == "caution":
        return "soft_caution"
    return "other"


def has_mood_screen_caution(summary: str) -> bool:
    """True when summary carries ``caution: mood-screen-positive``."""
    for line in extract_safety_lines(summary):
        if line["kind"] == "caution" and MOOD_SCREEN_TOKEN in line["body"]:
            return True
    return False
