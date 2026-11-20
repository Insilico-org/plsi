"""`plsi bio composition` (label shares per cell table, overall and per sample, against frozen `label<=share` or
`label>=share` limits) and `plsi bio order-check` (agreement of two pseudotime orderings `a` and `b` of the same
cells)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from plsi.bio import figures, stats
from plsi.bio.flags import raise_flag
from plsi.bio.tables import number, rows
from plsi.bio.tuning import MIN_ORDER_RHO
from plsi.errors import ValidationError
from plsi.vocab.bio import BioRule

_LIMIT = re.compile(r"^(.+?)\s*(<=|>=)\s*([01](?:\.\d+)?)$")


def _limits(given: list[str]) -> list[tuple[str, str, float]]:
    out = []
    for text in given:
        if not (m := _LIMIT.match(text.strip())):
            raise ValidationError(f"limit {text!r} is `label<=share` or `label>=share`, share 0-1", code="BAD_LIMIT")
        out.append((m.group(1).strip(), m.group(2), float(m.group(3))))
    return out


def composition(file: str, limit: list[str] | None = None, figure: str | None = None) -> dict[str, Any]:
    table = rows(file, ("label",))
    if not table:
        raise ValidationError("no cells", code="BAD_TABLE")
    total = Counter(r["label"] for r in table)
    by_sample: dict[str, Counter[str]] = defaultdict(Counter)
    for r in table:
        if r.get("sample"):
            by_sample[r["sample"]][r["label"]] += 1
    n = len(table)
    shares = {k: v / n for k, v in total.most_common()}
    broken = []
    limits = _limits(limit or [])
    for label, op, bound in limits:
        share = shares.get(label, 0.0)
        if (op == "<=" and share > bound) or (op == ">=" and share < bound):
            broken.append({"label": label, "limit": f"{op}{bound}", "share": share, "cells": total.get(label, 0)})
    flags: list[str] = []
    if broken:
        raise_flag(flags, BioRule.LIMIT_EXCEEDED, "; ".join(f"{b['label']} {b['share']:.1%} breaks {b['limit']}"
                                                            for b in broken))
    samples = {s: {"cells": sum(c.values()), "shares": {k: v / sum(c.values()) for k, v in c.most_common()}}
               for s, c in sorted(by_sample.items())}
    bars = {f"{s} (n = {v['cells']})": v["shares"] for s, v in samples.items()} or {f"all cells (n = {n})": shares}
    drawn = figures.stacked(bars, limits, figure, "Cell-type shares" + (" (a limit is broken)" if broken else "")) if figure else []
    return {"figures": drawn, "cells": n, "labels": len(total), "shares": shares, "samples": samples,
            "broken": broken, "stop": bool(broken), "flags": flags}


def order_check(file: str, figure: str | None = None) -> dict[str, Any]:
    table = rows(file, ("a", "b"))
    pairs = [(number(r, "a", f"line {i}", optional=True), number(r, "b", f"line {i}", optional=True))
             for i, r in enumerate(table, start=2)]
    both = [(a, b) for a, b in pairs if a is not None and b is not None]
    rho = stats.spearman([a for a, _ in both], [b for _, b in both])
    if rho is None:
        raise ValidationError("need at least 3 cells with both orderings, each with spread", code="BAD_TABLE")
    flags: list[str] = []
    if abs(rho) < MIN_ORDER_RHO:
        raise_flag(flags, BioRule.ORDER_UNSTABLE, f"the two orderings agree at Spearman {rho:.2f} (under "
                   f"{MIN_ORDER_RHO}): the order is not a result")
    drawn = figures.scatter([a for a, _ in both], [b for _, b in both], figure,  # type: ignore[misc]
                            f"Two orderings of {len(both)} cells (Spearman {rho:.2f})", "pseudotime, run a",
                            "pseudotime, run b") if figure else []
    return {"figures": drawn, "cells": len(both), "dropped": len(pairs) - len(both), "spearman": rho, "reversed": rho < 0,
            "stable": not flags, "flags": flags}
