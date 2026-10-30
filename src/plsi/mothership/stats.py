"""The analyses of a Mothership data release, the same maths as the Mother's: cells pooled by n, Welch's
t-test between two groups (compare_groups) or a weighted least-squares slope on the age-band midpoint (age_trend);
the Student t CDF from the regularized incomplete beta (continued fraction). Results are rounded to 6 significant digits."""

from __future__ import annotations

import math
from typing import Any

from plsi import files
from plsi.errors import ValidationError
from plsi.vocab import AnalysisOp, Sex

GROUP_KEYS = ("age_band", "sex")
WIRE_SEXES = (Sex.F.value, Sex.M.value)  # the wire's sexes (§5); X and unknown are never in a release cell


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction of the incomplete beta (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 301):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
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


def sig(x: float, digits: int = 6) -> float:
    return float(f"{x:.{digits}g}")


def _pool(cells: list[dict[str, Any]]) -> tuple[int, float, float]:
    """n, n-weighted mean and pooled SD (within- and between-cell spread) of cells of one group."""
    n = sum(c["n"] for c in cells)
    mean = sum(c["n"] * c["mean"] for c in cells) / n
    ss = sum((c["n"] - 1) * c["sd"] ** 2 + c["n"] * (c["mean"] - mean) ** 2 for c in cells)
    return n, mean, math.sqrt(ss / (n - 1))


def _midpoint(band: str) -> float:
    """The midpoint of a closed '<low>-<high>' band; open bands such as '90+' are refused, as on the Mother."""
    low, _, high = str(band).partition("-")
    try:
        return (int(low) + int(high)) / 2.0
    except ValueError:
        raise ValidationError(f"age band {band!r} is not <low>-<high>", code="BAD_AGE_BAND",
                              hint="age_trend needs closed bands; compare_groups works on any band") from None


def _matches(cell: dict[str, Any], group: dict[str, Any]) -> bool:
    """A null filter value matches every cell (the Mother's rule)."""
    return all(cell.get(k) == v for k, v in group.items() if v is not None)


def check_spec(spec: Any) -> AnalysisOp:
    """The op of a valid §5 analysis spec; raises otherwise."""
    if not isinstance(spec, dict) or spec.get("op") not in tuple(AnalysisOp):
        raise ValidationError(f"the analysis op must be one of {', '.join(AnalysisOp)}", code="BAD_SPEC")
    op = AnalysisOp(spec["op"])
    allowed = {"op", "map_id", "coordinate"} | ({"group_a", "group_b"} if op == AnalysisOp.COMPARE_GROUPS else {"sex"})
    groups = [spec.get(g) for g in ("group_a", "group_b")] if op == AnalysisOp.COMPARE_GROUPS else []
    if (set(spec) - allowed or not all(isinstance(spec.get(k), str) and spec[k] for k in ("map_id", "coordinate"))
            or any(not isinstance(g, dict) or set(g) - set(GROUP_KEYS) for g in groups)):
        raise ValidationError(f"a {op} spec has {', '.join(sorted(allowed))} only", code="BAD_SPEC",
                              hint="groups filter by age_band and/or sex")
    sexes = [g.get("sex") for g in groups] if groups else [spec.get("sex")]
    if any(s is not None and s not in WIRE_SEXES for s in sexes):
        raise ValidationError(f"sex must be {' or '.join(WIRE_SEXES)}", code="BAD_SPEC", hint="null or absent = both")
    return op


def _result(effect: float, se: float, n: int, df: float) -> dict[str, Any]:
    if not se > 0:
        raise ValidationError("the cells have no spread to test against", code="DEGENERATE_CELLS")
    half = t_quantile(0.975, df) * se
    statistic = effect / se
    return {"effect": sig(effect), "interval": [sig(effect - half), sig(effect + half)], "n": n,
            "statistic": sig(statistic), "df": sig(df), "p": sig(t_two_sided(statistic, df))}


def analyze_release(release: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """The §5 result {effect, interval, n, statistic, df, p} of `spec` on a release."""
    op = check_spec(spec)
    cells = [c for c in release.get("cells", []) if c["map_id"] == spec["map_id"] and c["coordinate"] == spec["coordinate"]]
    if op == AnalysisOp.COMPARE_GROUPS:
        groups = [[c for c in cells if _matches(c, spec[g])] for g in ("group_a", "group_b")]
        if not all(groups) or any(sum(c["n"] for c in g) < 2 for g in groups):
            raise ValidationError("a group matches no cells", code="TOO_FEW_CELLS")
        (na, ma, sa), (nb, mb, sb) = _pool(groups[0]), _pool(groups[1])
        va, vb = sa * sa / na, sb * sb / nb
        if not va + vb > 0:
            raise ValidationError("the cells have no spread to test against", code="DEGENERATE_CELLS")
        df = (va + vb) ** 2 / (va * va / (na - 1) + vb * vb / (nb - 1))
        return _result(ma - mb, math.sqrt(va + vb), na + nb, df)
    cells = [c for c in cells if _matches(c, {"sex": spec.get("sex")})]
    bands = sorted({c["age_band"] for c in cells}, key=_midpoint)
    if len(bands) < 3:
        raise ValidationError(f"an age trend needs at least 3 age bands, the release has {len(bands)}", code="TOO_FEW_CELLS")
    pooled = [(_midpoint(b), *_pool([c for c in cells if c["age_band"] == b])) for b in bands]
    if any(not sd > 0 for *_, sd in pooled):
        raise ValidationError("a cell has no spread (sd 0)", code="DEGENERATE_CELLS")
    w = [n / sd ** 2 for _, n, _, sd in pooled]
    xs, ys = [p[0] for p in pooled], [p[2] for p in pooled]
    sw = sum(w)
    xbar, ybar = sum(wi * x for wi, x in zip(w, xs)) / sw, sum(wi * y for wi, y in zip(w, ys)) / sw
    sxx = sum(wi * (x - xbar) ** 2 for wi, x in zip(w, xs))
    slope = sum(wi * (x - xbar) * (y - ybar) for wi, x, y in zip(w, xs, ys)) / sxx
    df = len(bands) - 2
    rss = sum(wi * (y - ybar - slope * (x - xbar)) ** 2 for wi, x, y in zip(w, xs, ys))
    return _result(slope, math.sqrt(rss / df / sxx), sum(p[1] for p in pooled), df)


def analyze(release: str, spec: str) -> dict[str, Any]:
    """`mothership analyze`: run a §5 analysis spec on a downloaded release (local; nothing is sent)."""
    data, given = files.load_json(release), files.load_json(spec)
    return {"release": data.get("version"), "analysis": given, "result": analyze_release(data, given)}
