"""`plsi bio enrich`: over-representation of a gene list in gene sets (pathways, or TF regulons as a GMT). The list
and the sets are cut to the universe (the genes measured); one-sided hypergeometric p, BH across tested sets, and a
flag when the ranks follow set size."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from plsi.bio import figures, stats
from plsi.bio.flags import raise_flag
from plsi.bio.tables import genes as read_genes
from plsi.bio.tables import gmt
from plsi.bio.tuning import (ALPHA, FIGURE_ROWS, MAX_OVERLAP_SHOWN, MAX_ROWS_SHOWN, MAX_SET, MIN_SET, SIZE_BIAS_MIN_SETS,
                              SIZE_BIAS_MIN_SPREAD, SIZE_BIAS_RHO)
from plsi.distributions import hypergeom_sf
from plsi.errors import ValidationError
from plsi.vocab.bio import BioRule


def _tested(hits: set[str], world: set[str], sets: dict[str, list[str]], min_size: int, max_size: int) -> list[dict[str, Any]]:
    out = []
    for name, members in sets.items():
        cut = [g for g in members if g in world]
        if min_size <= len(cut) <= max_size:
            overlap = sorted(hits.intersection(cut))
            expected = len(hits) * len(cut) / len(world)
            out.append({"set": name, "size": len(cut), "overlap": len(overlap), "expected": expected,
                        "ratio": len(overlap) / expected, "p": hypergeom_sf(len(overlap), len(world), len(cut), len(hits)),
                        "genes": overlap})
    return out


def _write(out: str, tested: list[dict[str, Any]]) -> None:
    with Path(out).open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["set", "size", "overlap", "expected", "ratio", "p", "padj", "genes"])
        w.writerows([t["set"], t["size"], t["overlap"], t["expected"], t["ratio"], t["p"], t["padj"], " ".join(t["genes"])]
                    for t in tested)


def enrich(genes: str, sets: str, universe: str, min_size: int = MIN_SET, max_size: int = MAX_SET, top: int = 20,
           out: str | None = None, figure: str | None = None) -> dict[str, Any]:
    """`out` writes every tested set (the output shows the top rows only); `figure` draws the top rows."""
    world, given = set(read_genes(universe)), read_genes(genes)
    hits = {g for g in given if g in world}
    if not hits:
        raise ValidationError("no gene of the list is in the universe", code="EMPTY_LIST",
                              hint="the universe is every gene measured, the list a subset of it")
    tested = _tested(hits, world, gmt(sets), min_size, max_size)
    if not tested:
        raise ValidationError(f"no set has {min_size}-{max_size} genes in the universe", code="NO_SETS_TESTED")
    for row, q in zip(tested, stats.bh([t["p"] for t in tested])):
        row["padj"] = q
    tested.sort(key=lambda t: (t["p"], -t["overlap"]))
    flags: list[str] = []
    sizes = [t["size"] for t in tested]
    judged = len(tested) >= SIZE_BIAS_MIN_SETS and max(sizes) >= SIZE_BIAS_MIN_SPREAD * min(sizes)
    rho = stats.spearman(sizes, [-math.log10(max(t["p"], 1e-300)) for t in tested]) if judged else None
    if rho is not None and rho > SIZE_BIAS_RHO:
        raise_flag(flags, BioRule.SET_SIZE_BIAS, f"Spearman of set size with -log10 p is {rho:.2f}: the ranks follow "
                   "set size; report sets by ratio and check a size-matched collection")
    if out:
        _write(out, tested)
    shown = [{**t, "genes": t["genes"][:MAX_OVERLAP_SHOWN]} for t in tested[:max(1, min(top, MAX_ROWS_SHOWN))]]
    rows = shown[:FIGURE_ROWS]
    drawn = figures.dots([t["set"] for t in rows], [t["ratio"] for t in rows], [t["overlap"] / t["size"] for t in rows],
                         [figures.neglog(t["padj"]) for t in rows], figure,
                         f"Over-representation, {len(hits)} genes in a universe of {len(world)}"
                         + (" (set size bias)" if flags else "")) if figure else []
    return {"table": out, "figures": drawn, "universe": len(world), "list": len(hits),
            "not_in_universe": len(given) - len(hits), "tested": len(tested),
            "significant": sum(1 for t in tested if t["padj"] < ALPHA), "size_rho": rho, "flags": flags,
            "top": shown}
