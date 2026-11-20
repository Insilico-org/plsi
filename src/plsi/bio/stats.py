"""Ranks, correlations and the Benjamini-Hochberg adjustment the `plsi bio` checks share."""

from __future__ import annotations

import math
from statistics import fmean


def ranks(values: list[float]) -> list[float]:
    """Average ranks (1-based), ties sharing their mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def pearson(xs: list[float], ys: list[float]) -> float | None:
    """None for fewer than 3 pairs or a side with no spread."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx, my = fmean(xs), fmean(ys)
    sxx, syy = sum((x - mx) ** 2 for x in xs), sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def spearman(xs: list[float], ys: list[float]) -> float | None:
    return pearson(ranks(xs), ranks(ys)) if len(xs) == len(ys) else None


def bh(ps: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values, in the order given."""
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, running = [1.0] * len(ps), 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        running = min(running, ps[i] * len(ps) / rank)
        out[i] = min(1.0, running)
    return out
