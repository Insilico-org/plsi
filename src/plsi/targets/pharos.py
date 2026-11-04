"""Pharos / TCRD: the target development level (Tclin, Tchem, Tbio, Tdark) and patent-mention series.

The level is Pharos' classification and is reported as theirs, never merged with this module's own counts.
"""

from __future__ import annotations

from typing import Any

from plsi import net, references
from plsi.models import external_str
from plsi.vocab.targets import DevelopmentLevel

# Reported as Pharos' word with its meaning, never recomputed; a level outside this list is flagged
# `level_recognised`.
TARGET_DEVELOPMENT_LEVELS: dict[DevelopmentLevel, str] = {
    DevelopmentLevel.TCLIN: "an approved drug acts on it through a known mechanism",
    DevelopmentLevel.TCHEM: "potent chemistry exists, but nothing approved",
    DevelopmentLevel.TBIO: "the biology is known and there is no chemistry",
    DevelopmentLevel.TDARK: "almost nothing is known: no chemistry, little literature",
}

CAP_DESCRIPTION = 2_000

TARGET = """query Target($sym: String!) {
  target(q: {sym: $sym}) {
    sym name tdl fam novelty description
    patentCounts { year count }
  }
}"""

# The series ends where Pharos' load ended.
PATENT_CAVEAT = ("patent counts come from Pharos/TCRD and the series ends where their load ended; a low "
                 "recent count is the source's coverage, not evidence that filing stopped")


def development_level(symbol: str) -> dict[str, Any]:
    """`{known, level, family, novelty, description, patents}` for one gene symbol. An unknown symbol answers
    `target: null` with no error and reads `known: false`; a reply carrying `errors` raises (`net.graphql`), so a
    failure never reads as an absence. An unknown level word is passed through."""
    target = net.graphql(references.api_base("pharos"), TARGET, {"sym": symbol.strip()}).get("target")
    if not target:
        return {"known": False, "symbol": external_str(symbol),
                "note": f"Pharos holds no target record for {symbol}"}
    level = external_str(target.get("tdl"))
    return {
        "known": True, "symbol": external_str(target.get("sym")), "name": external_str(target.get("name")),
        "level": level or None,
        "level_recognised": level in TARGET_DEVELOPMENT_LEVELS,
        "meaning": TARGET_DEVELOPMENT_LEVELS.get(level),
        "family": external_str(target.get("fam")) or None,
        # Pharos' novelty score: higher means less published.
        "novelty": target.get("novelty"),
        "description": external_str(target.get("description"), CAP_DESCRIPTION) or None,
        **_patents(target.get("patentCounts")),
    }


def _patents(series: list[dict[str, Any]] | None) -> dict[str, Any]:
    """The patent-mention series, as a total, a peak and where the source's coverage stops."""
    rows = [(r.get("year"), r.get("count")) for r in series or []
            if r.get("year") is not None and r.get("count") is not None]
    if not rows:
        return {"patents": None, "patent_note": "Pharos records no patent count for this target"}
    rows.sort()
    total = sum(count for _, count in rows)
    peak_year, peak = max(rows, key=lambda r: r[1])
    return {"patents": {"total": total, "peak_year": peak_year, "peak": peak,
                        "last_year_covered": rows[-1][0], "years": len(rows)},
            "patent_note": PATENT_CAVEAT}
