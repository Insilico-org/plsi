"""`plsi bio plot nes` and `plsi bio plot umap`: the standard figures for results computed in an analysis's own
scripts (fgsea's preranked table, a scanpy embedding), drawn the same way as every `plsi bio` figure."""

from __future__ import annotations

from typing import Any

from plsi.bio import figures
from plsi.bio.tables import number, rows
from plsi.bio.tuning import ALPHA, FIGURE_ROWS, MAX_PANELS
from plsi.errors import ValidationError


def nes(file: str, figure: str, alpha: float = ALPHA, title: str | None = None) -> dict[str, Any]:
    """Columns pathway, nes, padj: the sets below alpha, strongest |NES| first, at most FIGURE_ROWS, drawn by sign."""
    table = [(r["pathway"], number(r, "nes", f"line {i}"), number(r, "padj", f"line {i}"))
             for i, r in enumerate(rows(file, ("pathway", "nes", "padj")), start=2)]
    kept = sorted((t for t in table if t[2] < alpha), key=lambda t: -abs(t[1]))[:FIGURE_ROWS]  # type: ignore[operator, arg-type]
    if not kept:
        raise ValidationError(f"no pathway has padj below {alpha}; nothing to draw", code="NOTHING_TO_DRAW")
    kept.sort(key=lambda t: -t[1])  # type: ignore[operator]
    drawn = figures.signed_bars([t[0] for t in kept], [t[1] for t in kept], figure,  # type: ignore[misc]
                                title or f"Preranked enrichment: {len(kept)} of {len(table)} sets at FDR < {alpha}",
                                "normalized enrichment score (NES)")
    return {"tested": len(table), "drawn": len(kept), "up": sum(1 for t in kept if t[1] > 0),  # type: ignore[operator]
            "down": sum(1 for t in kept if t[1] < 0), "figures": drawn}  # type: ignore[operator]


def umap(file: str, figure: str, title: str | None = None) -> dict[str, Any]:
    """Columns umap1, umap2 and either `value` (a gene's expression or a score; 0 or empty is drawn grey) or `label`
    (a cell type); an optional `group` splits the cells into panels (at most MAX_PANELS)."""
    table = rows(file, ("umap1", "umap2"))
    if not table:
        raise ValidationError("no cells", code="BAD_TABLE")
    numeric = "value" in table[0]
    if not numeric and "label" not in table[0]:
        raise ValidationError("a `value` or a `label` column colours the cells", code="BAD_TABLE")
    panels: dict[str, list[tuple[float, float, Any]]] = {}
    for i, r in enumerate(table, start=2):
        colour = number(r, "value", f"line {i}", optional=True) if numeric else r["label"]
        panels.setdefault(r.get("group") or "all cells", []).append(
            (number(r, "umap1", f"line {i}"), number(r, "umap2", f"line {i}"), colour))  # type: ignore[arg-type]
    if len(panels) > MAX_PANELS:
        raise ValidationError(f"{len(panels)} groups; at most {MAX_PANELS} panels", code="TOO_MANY_PANELS")
    drawn = figures.embedding(panels, figure, title or ("expression" if numeric else "cell types"), numeric)
    return {"cells": len(table), "panels": {g: len(c) for g, c in panels.items()}, "figures": drawn}
