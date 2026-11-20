"""`plsi bio signature-null`: a signature's score (mean stat of the up genes minus the down genes) against same-size
sets drawn at random or matched gene by gene on mean expression; the one-sided empirical p (+1 corrected) above
alpha is `null_as_good`. A matched run also reports the random p and how closely the stat tracks mean expression,
the contrast that shows an expression-level explanation."""

from __future__ import annotations

import random
from statistics import fmean
from typing import Any

from plsi.bio import figures, stats as bstats
from plsi.bio.flags import raise_flag
from plsi.bio.tables import genes as read_genes
from plsi.bio.tables import number, rows
from plsi.bio.tuning import ALPHA, MATCH_BINS, MAX_NULL_DRAWS, MIN_NULL_DRAWS, NULL_DRAWS
from plsi.errors import ValidationError
from plsi.vocab.bio import BioRule, NullModel


def _score(stat: dict[str, float], up: list[str], down: list[str]) -> float:
    return fmean(stat[g] for g in up) - (fmean(stat[g] for g in down) if down else 0.0)


def _pools(expr: dict[str, float]) -> dict[str, list[str]]:
    """Each gene -> the genes in its mean-expression bin, which a matched draw may put in its place."""
    order = sorted(expr, key=expr.__getitem__)
    bins = {g: min(MATCH_BINS - 1, i * MATCH_BINS // len(order)) for i, g in enumerate(order)}
    members: dict[int, list[str]] = {}
    for g, b in bins.items():
        members.setdefault(b, []).append(g)
    return {g: members[b] for g, b in bins.items()}


def _draw(rng: random.Random, sig: list[str], genes: list[str], pools: dict[str, list[str]] | None) -> list[str]:
    """A same-size stand-in for `sig`: matched gene by gene when there are pools, else at random."""
    if pools is not None:
        return [rng.choice(pools[g]) for g in sig]
    return rng.sample(genes, len(sig))


def _empirical(observed: float, nulls: list[float]) -> float:
    beyond = sum(1 for s in nulls if (s >= observed if observed >= 0 else s <= observed))
    return (beyond + 1) / (len(nulls) + 1)


def signature_null(stats: str, up: str, down: str | None = None, null: str = NullModel.MATCHED.value,
                   draws: int = NULL_DRAWS, seed: int = 1, figure: str | None = None) -> dict[str, Any]:
    matched = NullModel(null) is NullModel.MATCHED
    table = rows(stats, ("gene", "stat") + (("mean_expr",) if matched else ()))
    stat = {r["gene"].upper(): number(r, "stat", f"line {i}") for i, r in enumerate(table, start=2)}
    up_given, down_given = read_genes(up), read_genes(down) if down else []
    up_in, down_in = [g for g in up_given if g in stat], [g for g in down_given if g in stat]
    if not up_in:
        raise ValidationError("no up gene is in the stats table", code="EMPTY_LIST")
    if set(up_in) & set(down_in):
        raise ValidationError("a gene is in both the up and the down list", code="BAD_SIGNATURE")
    expr = {r["gene"].upper(): number(r, "mean_expr", f"line {i}") for i, r in enumerate(table, start=2)} if matched else {}
    pools = _pools(expr) if matched else None  # type: ignore[arg-type]
    genes, rng = list(stat), random.Random(seed)
    draws = max(MIN_NULL_DRAWS, min(draws, MAX_NULL_DRAWS))
    observed = _score(stat, up_in, down_in)
    nulls = sorted(_score(stat, _draw(rng, up_in, genes, pools), _draw(rng, down_in, genes, pools))
                   for _ in range(draws))
    p = _empirical(observed, nulls)
    contrast = {}
    if matched:
        rand = [_score(stat, _draw(rng, up_in, genes, None), _draw(rng, down_in, genes, None)) for _ in range(draws)]
        contrast = {"random_p": _empirical(observed, rand),
                    "stat_tracks_expression": bstats.spearman([stat[g] for g in genes], [expr[g] for g in genes])}
    flags: list[str] = []
    if p > ALPHA:
        raise_flag(flags, BioRule.NULL_AS_GOOD, f"{null} gene sets of the same size score as well (empirical p "
                   f"{p:.3g}): the signature adds nothing over its null")
    drawn = figures.null_hist(nulls, observed, figure, f"Signature against {null} gene sets (empirical p {p:.2g})",
                              "score (mean stat, up minus down)") if figure else []
    return {"figures": drawn, "null": null, "draws": draws, "seed": seed, "score": observed, "p_empirical": p, **contrast,
            "null_median": nulls[draws // 2], "null_95": [nulls[int(0.025 * draws)], nulls[int(0.975 * draws) - 1]],
            "up": {"given": len(up_given), "used": len(up_in)}, "down": {"given": len(down_given), "used": len(down_in)},
            "flags": flags}
