"""Tail probabilities and quantiles shared by the analyses: normal, Student t, chi-square, binomial and
hypergeometric. Pure Python."""

from __future__ import annotations

import math
from statistics import NormalDist

CONFIDENCE = 0.95
Z95 = NormalDist().inv_cdf(0.5 + CONFIDENCE / 2)
_TINY = 1e-300


def norm_sf(z: float) -> float:
    return 1 - NormalDist().cdf(z)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete beta (modified Lentz)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > _TINY else _TINY)
    h = d
    for m in range(1, 301):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > _TINY else _TINY)
            c = 1.0 + aa / c
            c = c if abs(c) > _TINY else _TINY
            h *= d * c
        if abs(d * c - 1.0) < 3e-16:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """The regularized incomplete beta I_x(a, b)."""
    if x <= 0.0 or x >= 1.0:
        return 0.0 if x <= 0.0 else 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided(t: float, df: float) -> float:
    """Two-sided p of Student's t with df degrees of freedom."""
    return betainc(df / 2.0, 0.5, df / (df + t * t))


def t_quantile(q: float, df: float) -> float:
    """The t with P(T <= t) = q, for q > 0.5 (bisection on the two-sided p)."""
    target, lo, hi = 2.0 * (1.0 - q), 0.0, 1.0
    while t_two_sided(hi, df) > target:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        lo, hi = (mid, hi) if t_two_sided(mid, df) > target else (lo, mid)
    return (lo + hi) / 2.0


def chi2_sf(x: float, df: int) -> float:
    """P(X > x) for chi-square: the regularized upper gamma Q(df/2, x/2)."""
    s, z = df / 2, x / 2
    if z <= 0:
        return 1.0
    scale = math.exp(-z + s * math.log(z) - math.lgamma(s))
    if z < s + 1:  # series for the lower tail
        term = total = 1 / s
        for n in range(1, 1000):
            term *= z / (s + n)
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1 - total * scale)
    b, c, d = z + 1 - s, 1 / _TINY, 1 / (z + 1 - s)  # continued fraction for the upper tail
    h = d
    for n in range(1, 1000):
        an = -n * (n - s)
        b += 2
        d = an * d + b
        d = 1 / (d if abs(d) >= _TINY else _TINY)
        c = b + an / c
        c = c if abs(c) >= _TINY else _TINY
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return min(1.0, max(0.0, h * scale))


def _lchoose(n: int, k: int) -> float:
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p)."""
    if k <= 0:
        return 1.0
    return min(1.0, sum(math.exp(_lchoose(n, i) + i * math.log(p) + (n - i) * math.log1p(-p)) for i in range(k, n + 1)))


def hypergeom_sf(hits: int, universe: int, in_set: int, drawn: int) -> float:
    """P(X >= hits): `drawn` items taken from `universe`, `in_set` of them marked."""
    if hits <= 0:
        return 1.0
    base = _lchoose(universe, drawn)
    total = sum(math.exp(_lchoose(in_set, i) + _lchoose(universe - in_set, drawn - i) - base)
                for i in range(hits, min(in_set, drawn) + 1) if drawn - i <= universe - in_set)
    return min(1.0, max(0.0, total))
