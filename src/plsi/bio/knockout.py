"""`plsi bio knockout`: a virtual knockout's result checked and drawn. The table is scTenifoldKnk's `diffRegulation`
(gene, distance, Z, FC, p.value, p.adj[, direction, directionScore]) as written by the analysis script. The genes
knocked out must rank among their own most perturbed genes (KO_TOP_RANK), the method's built-in check; when they
do not, `ko_not_perturbed` blocks support. Nearly uniform predicted directions raise `direction_uniform`, a caution:
the package's directions follow the dominant wild-type program and can lean down with sequencing depth."""

from __future__ import annotations

from typing import Any

from plsi.bio import figures
from plsi.bio.flags import raise_flag
from plsi.bio.tables import number, rows
from plsi.bio.tuning import (ALPHA, DIRECTION_MIN_GENES, DIRECTION_UNIFORM_SHARE, FIGURE_ROWS, KO_TOP_RANK,
                              MAX_ROWS_SHOWN)
from plsi.errors import ValidationError
from plsi.vocab.bio import BioRule

COLUMNS = ("gene", "distance", "Z", "p.adj")


def _row(r: dict[str, str], i: int) -> dict[str, Any]:
    where = f"line {i}"
    direction = r.get("direction", "").lower()
    if direction not in ("", "up", "down"):
        raise ValidationError(f"{where}: direction is up or down", code="BAD_TABLE")
    return {"gene": r["gene"].upper(), "distance": number(r, "distance", where), "z": number(r, "Z", where),
            "padj": number(r, "p.adj", where), "direction": direction or None}


def knockout(file: str, gene: list[str], alpha: float = ALPHA, figure: str | None = None) -> dict[str, Any]:
    """Perturbed genes at padj < alpha, up and down; each knocked-out gene's own rank; the top genes drawn by sign."""
    table = sorted((_row(r, i) for i, r in enumerate(rows(file, COLUMNS), start=2)), key=lambda t: -t["distance"])
    if not table:
        raise ValidationError("the table has no genes", code="BAD_TABLE")
    ranks = {t["gene"]: i for i, t in enumerate(table, start=1)}
    ko = [g.upper() for g in gene]
    if missing := [g for g in ko if g not in ranks]:
        raise ValidationError(f"{', '.join(missing)} not in the table: not in the network", code="KO_NOT_IN_NETWORK",
                              hint="a gene filtered out before the network was built cannot be knocked out")
    flags: list[str] = []
    if late := [f"{g} (rank {ranks[g]})" for g in ko if ranks[g] > KO_TOP_RANK]:
        raise_flag(flags, BioRule.KO_NOT_PERTURBED, f"{', '.join(late)} not within its own top {KO_TOP_RANK} "
                   "perturbed genes: the gene barely sits in the network")
    hits = [t for t in table if t["padj"] < alpha and t["gene"] not in ko]
    up, down = (sum(1 for t in hits if t["direction"] == d) for d in ("up", "down"))
    if up + down >= DIRECTION_MIN_GENES and max(up, down) >= DIRECTION_UNIFORM_SHARE * (up + down):
        raise_flag(flags, BioRule.DIRECTION_UNIFORM, f"{max(up, down)} of {up + down} responders predicted "
                   f"{'up' if up > down else 'down'}: directions follow the dominant wild-type program and can lean "
                   "down with depth; read them as predicted, not as regulation by the gene")
    drawn = []
    if figure:
        top = [t for t in table if t["gene"] in ko or t in hits][:FIGURE_ROWS]
        sign = [(-1 if t["direction"] == "down" else 1) * abs(t["z"]) for t in top]
        drawn = figures.signed_bars([t["gene"] + (" (knocked out)" if t["gene"] in ko else "") for t in top], sign,
                                    figure, f"Virtual knockout of {', '.join(ko)}: {len(hits)} genes at FDR < {alpha}",
                                    "Z of the perturbation (sign: predicted direction)")
    return {"knocked_out": {g: ranks[g] for g in ko}, "genes": len(table), "perturbed": len(hits),
            "up": up, "down": down,
            "top": hits[:MAX_ROWS_SHOWN], "alpha": alpha, "flags": flags, "figures": drawn}
