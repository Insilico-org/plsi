"""The standard figure of each `plsi bio` check (`--figure <name>.png`): one plot drawn from the numbers the check
computed, saved as PNG (300 dpi), SVG and PDF beside each other. Okabe-Ito colours, labelled axes, n shown."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from plsi.errors import DependencyMissing, ValidationError

PALETTE = ("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9", "#F0E442", "#000000")
GREY, SIZE = "#888888", (6.4, 4.4)


def _plt() -> Any:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as e:  # matplotlib is in the bot's environment, not a plsi dependency
        raise DependencyMissing("figures need matplotlib", code="FIGURE_UNAVAILABLE", hint="uv pip install matplotlib") from e
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False})
    return plt


def _save(fig: Any, path: str, tight: bool = True) -> list[str]:
    """`tight`: lay the axes out first (off where a colour bar is shared across panels)."""
    p = Path(path)
    if p.suffix.lower() != ".png":
        raise ValidationError("--figure names a .png file; the .svg and .pdf are written beside it", code="BAD_FIGURE")
    p.parent.mkdir(parents=True, exist_ok=True)
    if tight:
        fig.tight_layout()
    out = [p, p.with_suffix(".svg"), p.with_suffix(".pdf")]
    for f in out:
        fig.savefig(f, dpi=300 if f.suffix == ".png" else None, bbox_inches="tight")
    _plt().close(fig)
    return [str(f) for f in out]


def _axes(title: str) -> tuple[Any, Any]:
    fig, ax = _plt().subplots(figsize=SIZE)
    ax.set_title(title, loc="left", fontsize=10)
    return fig, ax


def replicate(disc: list[float], rep: list[float], same: list[bool], path: str, title: str) -> list[str]:
    fig, ax = _axes(title)
    for keep, colour, label in ((True, PALETTE[0], "same sign"), (False, PALETTE[3], "opposite sign")):
        xs = [x for x, s in zip(disc, same) if s == keep]
        ax.scatter(xs, [y for y, s in zip(rep, same) if s == keep], s=10, color=colour, alpha=0.7,
                   label=f"{label} (n = {len(xs)})")
    ax.axhline(0, color=GREY, lw=0.6)
    ax.axvline(0, color=GREY, lw=0.6)
    ax.set_xlabel("discovery effect (log2 fold change)")
    ax.set_ylabel("replication effect (log2 fold change)")
    ax.legend(frameon=False)
    return _save(fig, path)


def forest(rows: list[tuple[str, float, float, float]], summary: tuple[str, float, float, float] | None, path: str,
           title: str, xlabel: str, null: float, log: bool = False, marked: str | None = None) -> list[str]:
    """rows: (label, estimate, low, high), drawn top to bottom; summary: the pooled row, as a diamond; `marked`: the
    label of a row drawn in the accent colour (a positive control)."""
    fig, ax = _axes(title)
    items = rows + ([summary] if summary else [])
    for i, (label, est, lo, hi) in enumerate(items):
        y = len(items) - i
        pooled = summary is not None and i == len(items) - 1
        colour = PALETTE[3] if pooled else PALETTE[1] if label == marked else PALETTE[0]
        ax.plot([lo, hi], [y, y], color=colour, lw=1.4)
        ax.plot(est, y, "D" if pooled else "s", color=colour, ms=7 if pooled else 5)
    ax.set_yticks(range(len(items), 0, -1), [r[0] for r in items])
    ax.axvline(null, color=GREY, ls="--", lw=0.8)
    if log:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel)
    return _save(fig, path)


def dots(labels: list[str], ratios: list[float], shares: list[float], neglogq: list[float], path: str,
         title: str) -> list[str]:
    """Over-representation: x fold enrichment, dot size the share of the set's genes in the list, colour -log10 FDR."""
    fig, ax = _axes(title)
    ys = list(range(len(labels), 0, -1))
    pts = ax.scatter(ratios, ys, s=[40 + 400 * f for f in shares], c=neglogq, cmap="coolwarm", edgecolors="none",
                     vmin=0, vmax=max(3.0, max(neglogq, default=0)))
    ax.set_yticks(ys, labels, fontsize=7)
    ax.axvline(1, color=GREY, ls="--", lw=0.8)
    ax.grid(axis="y", color="#dddddd", lw=0.5)
    ax.set_xlabel("fold enrichment (overlap / expected)")
    fig.colorbar(pts, ax=ax, shrink=0.6, label="-log10 FDR")
    for f in (0.1, 0.3, 0.5):
        ax.scatter([], [], s=40 + 400 * f, color=GREY, label=f"{f:.0%}")
    ax.legend(title="genes in set", frameon=False, fontsize=7, title_fontsize=7, loc="lower right", labelspacing=1.2)
    return _save(fig, path)


def signed_bars(labels: list[str], values: list[float], path: str, title: str, xlabel: str) -> list[str]:
    """Signed scores (NES): red up, blue down, the value inside the bar, a symmetric axis."""
    fig, ax = _axes(title)
    ys = list(range(len(labels), 0, -1))
    ax.barh(ys, values, color=[PALETTE[3] if v > 0 else PALETTE[0] for v in values], height=0.6)
    for y, v in zip(ys, values):
        ax.text(v - 0.05 if v > 0 else v + 0.05, y, f"{v:.2f}", va="center", ha="right" if v > 0 else "left",
                color="white", fontsize=8)
    lim = max(2.0, max((abs(v) for v in values), default=0) * 1.15)
    ax.set_xlim(-lim, lim)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_yticks(ys, labels, fontsize=8)
    ax.set_xlabel(xlabel)
    return _save(fig, path)


def embedding(panels: dict[str, list[tuple[float, float, Any]]], path: str, title: str, numeric: bool) -> list[str]:
    """Cells on a 2-D embedding, one panel per group: a value in viridis with zero or missing in light grey and one
    colour bar, or a label in fixed colours with one legend."""
    plt = _plt()
    fig, axes = plt.subplots(1, len(panels), figsize=(4.6 * len(panels) + (0.8 if numeric else 1.6), 4.6), squeeze=False)
    values = [v for cells in panels.values() for *_, v in cells if numeric and v]
    labels = sorted({v for cells in panels.values() for *_, v in cells}) if not numeric else []
    for ax, (group, cells) in zip(axes[0], panels.items()):
        if numeric:
            off = [(x, y) for x, y, v in cells if not v]
            on = sorted(((x, y, v) for x, y, v in cells if v), key=lambda c: c[2])
            ax.scatter([c[0] for c in off], [c[1] for c in off], s=3, color="#d9d9d9", linewidths=0)
            pts = ax.scatter([c[0] for c in on], [c[1] for c in on], c=[c[2] for c in on], s=3, cmap="viridis",
                             vmin=min(values, default=0), vmax=max(values, default=1), linewidths=0)
        else:
            for i, lab in enumerate(labels):
                xy = [(x, y) for x, y, v in cells if v == lab]
                ax.scatter([c[0] for c in xy], [c[1] for c in xy], s=3, color=PALETTE[i % len(PALETTE)], linewidths=0,
                           label=f"{lab}")
        ax.set_title(f"{group} (n = {len(cells)})", fontsize=9)
        ax.set_xticks([]), ax.set_yticks([])
        ax.set_xlabel("UMAP1"), ax.set_ylabel("UMAP2")
        for side in ("top", "right"):
            ax.spines[side].set_visible(True)
    if numeric:
        fig.colorbar(pts, ax=list(axes[0]), shrink=0.8, label="expression")
    else:
        axes[0][-1].legend(frameon=False, fontsize=9, markerscale=6, loc="center left", bbox_to_anchor=(1.02, 0.5))
    fig.suptitle(title, fontsize=11)
    return _save(fig, path, tight=False)


def null_hist(nulls: list[float], observed: float, path: str, title: str, xlabel: str) -> list[str]:
    fig, ax = _axes(title)
    ax.hist(nulls, bins=40, color=PALETTE[5], edgecolor="white", label=f"null draws (n = {len(nulls)})")
    ax.axvline(observed, color=PALETTE[3], lw=1.6, label=f"observed {observed:.3g}")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("draws")
    ax.legend(frameon=False)
    return _save(fig, path)


def p_hist(ps: list[float], alpha: float, path: str, title: str) -> list[str]:
    fig, ax = _axes(title)
    bins = 20
    ax.hist(ps, bins=bins, range=(0, 1), color=PALETTE[5], edgecolor="white", label=f"p-values (n = {len(ps)})")
    ax.axhline(len(ps) / bins, color=GREY, ls="--", lw=0.8, label="expected under a calibrated null")
    ax.axvline(alpha, color=PALETTE[3], lw=1, label=f"alpha {alpha}")
    ax.set_xlabel("p-value")
    ax.set_ylabel("tests")
    ax.legend(frameon=False)
    return _save(fig, path)


def km(curves: dict[str, list[dict[str, float]]], per: dict[str, dict[str, Any]], ticks: list[float],
       at_risk: dict[str, list[int]], path: str, title: str) -> list[str]:
    """Kaplan-Meier steps per group, with the numbers at risk at `ticks` in a panel under the axis."""
    fig, (ax, risk) = _plt().subplots(2, 1, figsize=(SIZE[0], SIZE[1] + 0.8), height_ratios=(5, 1), sharex=True)
    ax.set_title(title, loc="left", fontsize=10)
    for i, (g, curve) in enumerate(curves.items()):
        ax.step([c["time"] for c in curve] + [ticks[-1]], [c["s"] for c in curve] + [curve[-1]["s"]], where="post",
                color=PALETTE[i], label=f"{g} (n = {per[g]['n']}, events {per[g]['events']})")
        risk.text(-0.02, i, g, ha="right", va="center", fontsize=7, color=PALETTE[i], transform=risk.get_yaxis_transform())
        for t, n in zip(ticks, at_risk[g]):
            risk.text(t, i, str(n), ha="center", va="center", fontsize=7)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("survival probability")
    ax.legend(frameon=False, fontsize=8)
    risk.set_ylim(-0.6, len(curves) - 0.4)
    risk.set_yticks([])
    risk.spines["left"].set_visible(False)
    risk.set_xticks(ticks)
    risk.set_xlabel("time (units as recorded); numbers at risk under the axis")
    return _save(fig, path)


def stacked(samples: dict[str, dict[str, float]], limits: list[tuple[str, str, float]], path: str, title: str) -> list[str]:
    fig, ax = _axes(title)
    labels = sorted({k for s in samples.values() for k in s}, key=lambda k: -sum(s.get(k, 0) for s in samples.values()))
    left = [0.0] * len(samples)
    for i, label in enumerate(labels):
        vals = [s.get(label, 0.0) for s in samples.values()]
        ax.barh(list(samples), vals, left=left, color=PALETTE[i % len(PALETTE)], label=label)
        left = [a + b for a, b in zip(left, vals)]
    for label, op, bound in limits:
        ax.axvline(bound, color=GREY, ls="--", lw=0.8)
        ax.text(bound, len(samples) - 0.4, f" {label} {op} {bound:g}", fontsize=7, color=GREY)
    ax.set_xlim(0, 1)
    ax.set_xlabel("share of cells")
    ax.legend(frameon=False, fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5))
    return _save(fig, path)


def scatter(xs: list[float], ys: list[float], path: str, title: str, xlabel: str, ylabel: str) -> list[str]:
    fig, ax = _axes(title)
    ax.scatter(xs, ys, s=4, color=PALETTE[0], alpha=0.5)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if xs:
        lo, hi = min(xs + ys), max(xs + ys)
        ax.plot([lo, hi], [lo, hi], color=GREY, ls="--", lw=0.8)
    return _save(fig, path)


def neglog(p: float) -> float:
    return -math.log10(max(p, 1e-300))
