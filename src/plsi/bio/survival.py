"""`plsi bio km`: Kaplan-Meier per group (`time`, `event` 1/0, `group`) with Greenwood log-log intervals, the
log-rank test across the groups and, for two, the Peto hazard ratio against the reference group."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from plsi.bio import figures
from plsi.bio.flags import raise_flag
from plsi.bio.tables import number, rows
from plsi.bio.tuning import MIN_EVENTS, SURVIVAL_GROUPS
from plsi.distributions import Z95, chi2_sf
from plsi.errors import ValidationError
from plsi.vocab.bio import BioRule


def _curve(data: list[tuple[float, int]]) -> list[dict[str, float]]:
    """{time, s, gw (the Greenwood sum), at_risk} at each event time, from S = 1."""
    at_risk, s, gw, out = len(data), 1.0, 0.0, [{"time": 0.0, "s": 1.0, "gw": 0.0, "at_risk": len(data)}]
    for t in sorted({t for t, _ in data}):
        d = sum(1 for tt, e in data if tt == t and e)
        n_t = sum(1 for tt, _ in data if tt == t)
        if d:
            s *= 1 - d / at_risk
            gw += d / (at_risk * (at_risk - d)) if at_risk > d else 0.0
            out.append({"time": t, "s": s, "gw": gw, "at_risk": at_risk})
        at_risk -= n_t
    return out


def _ci(s: float, gw: float) -> list[float] | None:
    if not 0 < s < 1 or gw <= 0:
        return None
    se = math.sqrt(gw) / abs(math.log(s))
    lo, hi = math.log(-math.log(s)) + Z95 * se, math.log(-math.log(s)) - Z95 * se
    return [math.exp(-math.exp(lo)), math.exp(-math.exp(hi))]


def _logrank(groups: dict[str, list[tuple[float, int]]],
             names: list[str]) -> tuple[float, int, list[float], list[float], list[list[float]]]:
    """Chi-square, df, observed and expected per group; variance matrix of the first k-1 inverted by elimination."""
    allt = sorted({t for g in groups.values() for t, e in g if e})
    k = len(names)
    o, e = [0.0] * k, [0.0] * k
    v = [[0.0] * k for _ in range(k)]
    for t in allt:
        n = [sum(1 for tt, _ in groups[g] if tt >= t) for g in names]
        d = [sum(1 for tt, ev in groups[g] if tt == t and ev) for g in names]
        nt, dt = sum(n), sum(d)
        if nt < 2:
            continue
        for i in range(k):
            o[i] += d[i]
            e[i] += dt * n[i] / nt
            for j in range(k):
                v[i][j] += dt * (nt - dt) / (nt - 1) * n[i] * ((nt if i == j else 0) - n[j]) / nt**2
    m = k - 1
    a = [row[:m] + [o[i] - e[i]] for i, row in enumerate(v[:m])]
    for c in range(m):  # solve V x = (O - E) for the first k-1 groups
        pivot = max(range(c, m), key=lambda r: abs(a[r][c]))
        a[c], a[pivot] = a[pivot], a[c]
        if abs(a[c][c]) < 1e-12:
            return float("nan"), m, o, e, v
        for r in range(m):
            if r != c:
                f = a[r][c] / a[c][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    chi = sum((o[i] - e[i]) * a[i][m] / a[i][i] for i in range(m))
    return chi, m, o, e, v


def _group(data: list[tuple[float, int]], at: list[float]) -> tuple[dict[str, Any], list[dict[str, float]]]:
    curve = _curve(data)
    points = []
    for t in at:
        p = [c for c in curve if c["time"] <= t][-1]
        points.append({"time": t, "s": p["s"], "ci": _ci(p["s"], p["gw"]), "at_risk": sum(1 for tt, _ in data if tt >= t)})
    return {"n": len(data), "events": sum(e for _, e in data),
            "median": next((c["time"] for c in curve if c["s"] <= 0.5), None), "at": points}, curve


def _write_curves(out: str, curves: dict[str, list[dict[str, float]]]) -> None:
    with Path(out).open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["group", "time", "survival", "at_risk"])
        for g, curve in curves.items():
            w.writerows([g, c["time"], c["s"], c["at_risk"]] for c in curve)


def _risk_table(groups: dict[str, list[tuple[float, int]]], names: list[str]) -> tuple[list[float], dict[str, list[int]]]:
    """Five evenly spaced times from 0 to the last follow-up, and each group's number at risk at them."""
    end = max(t for g in groups.values() for t, _ in g) or 1.0
    ticks = [round(end * k / 4, 2) for k in range(5)]
    return ticks, {g: [sum(1 for tt, _ in groups[g] if tt >= t) for t in ticks] for g in names}


def km(file: str, at: list[float] | None = None, reference: str | None = None, out: str | None = None,
       figure: str | None = None) -> dict[str, Any]:
    groups: dict[str, list[tuple[float, int]]] = {}
    for i, r in enumerate(rows(file, ("time", "event", "group")), start=2):
        t, ev = number(r, "time", f"line {i}"), number(r, "event", f"line {i}")
        if t is None or t < 0 or ev not in (0, 1):
            raise ValidationError(f"line {i}: time is >= 0 and event is 0 or 1", code="BAD_TABLE")
        groups.setdefault(r["group"], []).append((t, int(ev)))
    low, high = SURVIVAL_GROUPS
    if not low <= len(groups) <= high:
        raise ValidationError(f"{low}-{high} groups, got {len(groups)}", code="BAD_GROUPS")
    if reference is not None and reference not in groups:
        raise ValidationError(f"no group {reference!r}", code="BAD_GROUPS")
    names = [reference] + sorted(set(groups) - {reference}) if reference else sorted(groups)
    flags: list[str] = []
    per, curves = {}, {}
    for g in names:
        per[g], curves[g] = _group(groups[g], at or [])
        if per[g]["events"] < MIN_EVENTS:
            raise_flag(flags, BioRule.FEW_EVENTS, f"a group has under {MIN_EVENTS} events ({g}: {per[g]['events']})")
    chi, df, o, e, var = _logrank(groups, names)
    result: dict[str, Any] = {"groups": per, "logrank": {"chi2": chi, "df": df,
                              "p": chi2_sf(chi, df) if math.isfinite(chi) else None,
                              "observed": dict(zip(names, o)), "expected": dict(zip(names, e))}, "flags": flags}
    if len(names) == 2 and (v := var[1][1]) > 0:
        log_hr = (o[1] - e[1]) / v
        result["hr"] = {"group": names[1], "versus": names[0], "value": math.exp(log_hr),
                        "ci": [math.exp(log_hr - Z95 / math.sqrt(v)), math.exp(log_hr + Z95 / math.sqrt(v))],
                        "method": "Peto (O-E)/V"}
    if out:
        _write_curves(out, curves)
        result["curve_file"] = out
    if figure:
        ticks, risk = _risk_table(groups, names)
        hr = result.get("hr")
        label = f"HR {hr['value']:.2f} [{hr['ci'][0]:.2f}, {hr['ci'][1]:.2f}], " if hr else ""
        result["figures"] = figures.km(curves, per, ticks, risk, figure,
                                       f"Kaplan-Meier: {label}log-rank p {result['logrank']['p']:.2g}")
    return result
