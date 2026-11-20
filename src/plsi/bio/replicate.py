"""`plsi bio replicate`: the genes discovery called (padj below alpha, else every row) looked up in an independent
set: sign agreement with its exact binomial p, the Spearman of the effects, and the replication calls that agree."""

from __future__ import annotations

from typing import Any

from plsi.bio import figures, stats
from plsi.bio.flags import raise_flag
from plsi.bio.tables import number, rows
from plsi.bio.tuning import ALPHA, MIN_OVERLAP
from plsi.distributions import binom_sf
from plsi.vocab.bio import BioRule


def _table(file: str) -> tuple[dict[str, tuple[float, float | None]], bool]:
    """{gene: (effect, padj or None)} and whether the table has a padj column."""
    table = rows(file, ("gene", "effect"))
    return ({r["gene"].upper(): (number(r, "effect", f"line {i}"), number(r, "padj", f"line {i}", optional=True))
             for i, r in enumerate(table, start=2)}, bool(table) and "padj" in table[0])


def replicate(discovery: str, replication: str, alpha: float = ALPHA, figure: str | None = None) -> dict[str, Any]:
    """With a padj column, a gene is called when its padj is below alpha (blank: not called); without, every row is."""
    (disc, disc_padj), (rep, rep_padj) = _table(discovery), _table(replication)
    called = [g for g, (_, q) in disc.items() if not disc_padj or (q is not None and q < alpha)]
    shared = [g for g in called if g in rep]
    same = [g for g in shared if disc[g][0] * rep[g][0] > 0]
    flags: list[str] = []
    if len(shared) < MIN_OVERLAP:
        raise_flag(flags, BioRule.THIN_OVERLAP, f"{len(shared)} genes shared (under {MIN_OVERLAP}): agreement cannot "
                   "be judged")
    tail = binom_sf(max(len(same), len(shared) - len(same)), len(shared), 0.5)
    drawn = figures.replicate([disc[g][0] for g in shared], [rep[g][0] for g in shared], [g in set(same) for g in shared],
                              figure, f"Discovery genes in the replication set (n = {len(shared)})") if figure else []
    return {"figures": drawn, "called_in_discovery": len(called), "shared": len(shared), "sign_agree": len(same),
            "sign_agree_share": len(same) / len(shared) if shared else None,
            "sign_p": min(1.0, 2 * tail) if shared else 1.0,
            "spearman": stats.spearman([disc[g][0] for g in shared], [rep[g][0] for g in shared]),
            "also_called_same_sign": sum(1 for g in same if (rep[g][1] or 1) < alpha) if rep_padj else None,
            "alpha": alpha, "flags": flags}
