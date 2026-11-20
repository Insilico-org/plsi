"""The statistics the journal's checks use: mean with SD, a least-squares line, the chi-square upper tail."""

from __future__ import annotations

import math
from statistics import fmean, stdev
from typing import Any


def sd(values: list[float]) -> float | None:
    return stdev(values) if len(values) > 1 else None


def summary(values: list[float]) -> dict[str, Any]:
    return {"mean": fmean(values), "sd": sd(values), "n": len(values)}


def line(points: list[tuple[float, float]]) -> tuple[float, float, float] | None:
    """Least squares y = a + b·x -> (a, b, r²); None for fewer than two distinct x."""
    if len(points) < 2:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    mx, my = fmean(xs), fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in points) / sxx
    a = my - b * mx
    ss = sum((y - my) ** 2 for y in ys)
    return a, b, 1 - sum((y - a - b * x) ** 2 for x, y in points) / ss if ss else 1.0


def chi2_p(x: float, df: int) -> float:
    """Upper tail of the chi-square distribution: the regularized gamma Q(df/2, x/2)."""
    s, z = df / 2, x / 2
    if z <= 0:
        return 1.0
    scale = math.exp(-z + s * math.log(z) - math.lgamma(s))
    if z < s + 1:  # series for the lower tail
        term = total = 1 / s
        n = 1
        while abs(term) > 1e-14 * abs(total):
            term *= z / (s + n)
            total += term
            n += 1
        return max(0.0, 1 - total * scale)
    b, c, d = z + 1 - s, 1e300, 1 / (z + 1 - s)
    h = d
    for i in range(1, 300):  # continued fraction for the upper tail (Lentz)
        an = -i * (i - s)
        b += 2
        d = 1 / (an * d + b if abs(an * d + b) > 1e-300 else 1e-300)
        c = b + an / c if abs(b + an / c) > 1e-300 else 1e-300
        h *= d * c
        if abs(d * c - 1) < 1e-14:
            break
    return scale * h
