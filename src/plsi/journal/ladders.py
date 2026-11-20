"""DNA ladders by product name (ladders.csv): a ladder lane with no recorded sizes gets its product's standard bands;
a name that fits several products, or none, is a check, never a guess."""

from __future__ import annotations

import functools
import re
from importlib import resources
from typing import Any

from plsi.journal.results import Results

_FILLER = re.compile(r"\b(dna|ladder|marker)\b")


def _norm(name: str) -> str:
    text = re.sub(r"[^a-z0-9 ]", " ", name.lower().replace("kb", " kb ").replace("bp", " bp "))
    return " ".join(_FILLER.sub(" ", text).split())


@functools.cache
def table() -> tuple[tuple[str, tuple[str, ...], tuple[float, ...]], ...]:
    rows = resources.files("plsi.journal").joinpath("ladders.csv").read_text(encoding="utf-8").splitlines()[1:]
    return tuple((name, tuple(_norm(n) for n in names.split("|")), tuple(float(b) for b in bp.split(";")))
                 for name, names, bp in (r.split(",") for r in rows))


def match(name: str) -> list[tuple[str, tuple[float, ...]]]:
    """The products a written name means: an alias it contains, or, for a bare kind such as "1 kb plus", every
    product of that kind (more than one is ambiguous)."""
    key = f" {_norm(name)} "
    hits = {n: (max((len(a) for a in aliases if f" {a} " in key), default=0), bp) for n, aliases, bp in table()}
    if best := max(length for length, _ in hits.values()):  # the longest alias wins: "neb 1 kb plus" over "neb 1 kb"
        return [(n, bp) for n, (length, bp) in hits.items() if length == best]
    return [(n, bp) for n, aliases, bp in table() if key.strip() and any(a.endswith(key.rstrip()) for a in aliases)]


def gel(r: Results) -> dict[str, Any]:
    """Standard sizes for ladder lanes recorded without sizes, and a check for each ladder that cannot be named."""
    ladders, checks = [], []
    for lane in r.lanes:
        if not lane.ladder or lane.observed_bp:
            continue
        found = match(lane.sample or "")
        if len(found) == 1:
            ladders.append({"lane": lane.lane, "ladder": found[0][0], "bp": list(found[0][1])})
        elif found:
            checks.append(f"lane {lane.lane}: '{lane.sample}' could be {', '.join(n for n, _ in found)}; "
                          "name the product to draw its bands")
        else:
            checks.append(f"lane {lane.lane}: ladder '{lane.sample or 'unnamed'}' is not in the ladder table; "
                          "record its band sizes in observed_bp")
    return {"ladders": ladders, "checks": checks} if ladders or checks else {}
