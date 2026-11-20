"""Numbers derived from an entry's raw results (ΔΔCt, bands, readings, cell index, gates, growth; animals, vessels and
ladders in their own modules), each block with the checks a reader should see. Arithmetic only."""

from __future__ import annotations

import math
from collections import defaultdict
from statistics import fmean
from typing import Any

from plsi.journal import animals, cellbank, ladders
from plsi.journal.results import Results
from plsi.journal.stats import line, sd, summary
from plsi.journal.tuning import CI_BLANK_MAX, CT_LATE, CT_SPREAD, ROLE_NAMES, STANDARD_R2_MIN
from plsi.vocab.journal import WellRole


def role_of(name: str, role: WellRole, by_name: set[str]) -> WellRole:
    """A well's role as given; unset, the role its name implies (recorded in `by_name`, so it is reported)."""
    if role != WellRole.SAMPLE:
        return role
    guessed = ROLE_NAMES.get("".join(ch for ch in name.lower() if ch.isalnum()), WellRole.SAMPLE)
    if guessed != WellRole.SAMPLE:
        by_name.add(f"{name} ({guessed.value})")
    return guessed


def _named(by_name: set[str]) -> list[str]:
    return [f"taken as controls by their names: {', '.join(sorted(by_name))}"] if by_name else []


def _replicates(r: Results, checks: list[str], by_name: set[str]) -> tuple[dict, dict[str, str]]:
    """Mean Ct per (sample, target), each sample's group; control wells checked and left out."""
    reps: dict[tuple[str, str], list[float]] = defaultdict(list)
    group: dict[str, str] = {}
    for c in r.cts:
        role = role_of(c.sample, c.role, by_name)
        if role != WellRole.SAMPLE:
            if c.ct is not None:
                what = "contamination or primer dimer" if role == WellRole.NTC else "genomic DNA carry-over"
                checks.append(f"{c.sample} · {c.target}: control well amplified at Ct {c.ct:.1f}; possible {what}")
            continue
        group.setdefault(c.sample, c.group or c.sample)
        if c.ct is None:
            checks.append(f"{c.sample} · {c.target}: undetermined well left out")
        else:
            reps[(c.sample, c.target)].append(c.ct)
    for (s, t), cts in reps.items():
        if max(cts) - min(cts) > CT_SPREAD:
            checks.append(f"{s} · {t}: replicates spread {max(cts) - min(cts):.2f} cycles")
        if fmean(cts) > CT_LATE:
            checks.append(f"{s} · {t}: Ct {fmean(cts):.1f}, near the detection limit")
    return {k: fmean(v) for k, v in reps.items()}, group


def _folds(rows: list[dict[str, Any]], control: str | None, checks: list[str]) -> tuple[list, list]:
    """ΔΔCt against the control group's mean ΔCt, per target; group fold 2^-(mean ΔΔCt) with a ±1 SD range."""
    out_rows, groups = [], []
    for t in dict.fromkeys(x["target"] for x in rows):
        mine = [x for x in rows if x["target"] == t]
        base = [x["dct"] for x in mine if x["group"] == control]
        if not base:
            checks.append(f"{t}: no control group {control!r} with a ΔCt: fold change not computed")
            continue
        calib = fmean(base)
        out_rows += [{**x, "ddct": x["dct"] - calib, "fold": 2 ** -(x["dct"] - calib)} for x in mine]
        for g in dict.fromkeys(x["group"] for x in mine):
            dd = [x["dct"] - calib for x in mine if x["group"] == g]
            m, s = fmean(dd), sd(dd)
            groups.append({"target": t, "group": g, "n": len(dd), "fold": 2 ** -m,
                           "low": 2 ** -(m + s) if s else None, "high": 2 ** -(m - s) if s else None})
    return out_rows, groups


def ddct(r: Results) -> dict[str, Any]:
    """Livak 2^-ΔΔCt: replicate means, ΔCt against the mean of the reference targets, ΔΔCt against the control."""
    if not r.cts:
        return {}
    checks: list[str] = []
    by_name: set[str] = set()
    mean_ct, group = _replicates(r, checks, by_name)
    checks += _named(by_name)
    refs = r.reference_targets
    if not refs:
        return {"checks": [*checks, "no reference target named: ΔΔCt not computed"]}
    rows = []
    for s in sorted({s for s, _ in mean_ct}):
        ref = [mean_ct[(s, t)] for t in refs if (s, t) in mean_ct]
        if len(ref) < len(refs):
            checks.append(f"{s}: a reference target has no Ct; sample left out")
            continue
        rows += [{"sample": s, "group": group[s], "target": t, "ct": mean_ct[(s, t)], "dct": mean_ct[(s, t)] - fmean(ref)}
                 for t in sorted({t for _, t in mean_ct} - set(refs)) if (s, t) in mean_ct]
    out_rows, groups = _folds(rows, r.control_group, checks)
    return {"rows": out_rows, "groups": groups, "checks": checks, "control": r.control_group, "references": refs}


def western(r: Results) -> dict[str, Any]:
    """Each band ÷ its lane's loading control, then ÷ the control group's mean ratio of the same target."""
    if not r.bands:
        return {}
    checks = [f"lane {b.lane} ({b.sample}, {b.target}): no loading control" for b in r.bands if b.loading is None]
    ratios = [(b, b.group or b.sample, b.intensity / b.loading) for b in r.bands if b.loading]
    base: dict[str, list[float]] = defaultdict(list)
    for b, g, x in ratios:
        if g == r.control_group:
            base[b.target].append(x)
    rows, groups = [], defaultdict(list)
    for b, g, x in ratios:
        rel = x / fmean(base[b.target]) if base.get(b.target) else None
        rows.append({"lane": b.lane, "sample": b.sample, "group": g, "target": b.target, "ratio": x, "relative": rel})
        if rel is not None:
            groups[(b.target, g)].append(rel)
    if not base:
        checks.append("no control group with bands: relative levels not computed")
    return {"rows": rows, "checks": checks, "groups": [{"target": t, "group": g, **summary(v)} for (t, g), v in groups.items()]}


def _conc_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mean concentration per group; samples outside the standards are left out and counted."""
    out = []
    for g in dict.fromkeys(x["group"] for x in rows):
        concs = [x["conc"] for x in rows if x["group"] == g and x["conc"] is not None]
        left_out = sum(x["group"] == g and x["conc"] is None for x in rows)
        out.append({"group": g, **(summary(concs) if concs else {"mean": None, "sd": None, "n": 0}), "left_out": left_out})
    return out


def readings(r: Results) -> dict[str, Any]:
    """Blank mean subtracted; with standards, a linear fit gives each sample's concentration (inside the range only)."""
    if not r.readings:
        return {}
    by_name: set[str] = set()
    roles = [role_of(x.sample, x.role, by_name) for x in r.readings]
    blanks = [x.value for x, role in zip(r.readings, roles, strict=True) if role == WellRole.BLANK]
    blank = fmean(blanks) if blanks else 0.0
    checks = _named(by_name) + ([] if blanks else ["no blank wells: values not blank-subtracted"])
    std = [(x.standard_conc, x.value - blank) for x in r.readings if x.standard_conc is not None]
    fit = line(std)
    lo, hi = (min(s[0] for s in std), max(s[0] for s in std)) if std else (None, None)
    rows = []
    for x, role in zip(r.readings, roles, strict=True):
        if role == WellRole.BLANK or x.standard_conc is not None:
            continue
        net = x.value - blank
        conc = (net - fit[0]) / fit[1] if fit and fit[1] else None
        if conc is not None and not lo <= conc <= hi:
            checks.append(f"{x.sample}: {conc:.3g} lies outside the standards ({lo:g}-{hi:g}); not reported")
            conc = None
        rows.append({"sample": x.sample, "group": x.group or x.sample, "net": net, "conc": conc})
    out = {"blank": blank, "rows": rows, "checks": checks,
           "groups": [{"group": g, **summary([x["net"] for x in rows if x["group"] == g])} for g in dict.fromkeys(x["group"] for x in rows)]}
    if fit:
        out["curve"] = {"intercept": fit[0], "slope": fit[1], "r2": fit[2], "points": std}
        out["groups_conc"] = _conc_groups(rows)
        if fit[2] < STANDARD_R2_MIN:
            checks.append(f"standard curve r² {fit[2]:.3f} is below {STANDARD_R2_MIN}")
    return out


def cell_index(r: Results) -> dict[str, Any]:
    """xCELLigence: CI ÷ CI at the last point at or before treatment (1.0 at treatment); blank wells kept apart."""
    if not r.ci:
        return {}
    out, checks, blanks = [], [], []
    by_name: set[str] = set()
    for s in r.ci:
        if role_of(s.group, s.role, by_name) == WellRole.BLANK:
            top = max(p.ci for p in s.points)
            blanks.append({"group": s.group, "well": s.well, "max": top})
            if top > CI_BLANK_MAX:
                checks.append(f"{s.well or s.group} (blank) reached cell index {top:.2f}: cells or debris in a blank well")
            continue
        pts = sorted(s.points, key=lambda p: p.t_h)
        before = [p for p in pts if r.treated_at_h is not None and p.t_h <= r.treated_at_h]
        ref = before[-1].ci if before else None
        if r.treated_at_h is not None and not ref:
            checks.append(f"{s.group}: no positive cell index at or before treatment; not normalised")
        out.append({"group": s.group, "well": s.well, "points": [{"t": p.t_h, "ci": p.ci, "norm": p.ci / ref if ref else None} for p in pts]})
    return {"series": out, "blanks": blanks, "treated_at_h": r.treated_at_h, "checks": checks + _named(by_name)}


def gates(r: Results) -> dict[str, Any]:
    """Gate percentages from the exported counts (entries without FCS files; with them, plsi.journal.flow counts)."""
    if not r.gates:
        return {}
    counts = {(c.sample, c.gate): c.events for c in r.exported_counts}
    if not counts:
        return {"rows": [], "checks": ["no FCS file and no exported counts: gates not counted"]}
    rows, checks = [], []
    for sample in dict.fromkeys(c.sample for c in r.exported_counts):
        mine = {g.name: g for g in r.gates if g.sample in (None, sample)}
        for g in mine.values():
            n, root = counts.get((sample, g.name)), g
            while root.parent in mine and mine[root.parent] is not root:
                root = mine[root.parent]
            if n is None:
                checks.append(f"{sample} · {g.name}: no exported count")
                continue
            parent, total = counts.get((sample, g.parent)) if g.parent else None, counts.get((sample, root.name))
            rows.append({"sample": sample, "gate": g.name, "parent": g.parent, "events": n,
                         "of_parent": n / parent * 100 if parent else None, "of_total": n / total * 100 if total else None})
    return {"rows": rows, "checks": checks}


def growth(r: Results) -> dict[str, Any]:
    """Doubling time between consecutive counted passages that were not split in between."""
    counted = [p for p in sorted(r.passages, key=lambda p: p.date) if p.cells]
    rows = [{"from": a.date.isoformat(), "to": b.date.isoformat(), "doubling_h": (b.date - a.date).days * 24 / math.log2(b.cells / a.cells)}
            for a, b in zip(counted, counted[1:], strict=False) if b.date > a.date and b.cells > a.cells and a.passage == b.passage]
    return {"rows": rows} if rows else {}


def derive(r: Results) -> dict[str, Any]:
    """Every derived block the results allow, empty ones left out; gates from exported counts only without FCS files
    (with them the flow block replaces it, see `store.derived`)."""
    out = {"qpcr": ddct(r), "western": western(r), "readings": readings(r), "ci": cell_index(r),
           "weights": animals.weights(r), "gates": {} if r.fcs else gates(r), "growth": growth(r),
           "animals": animals.roster(r), "vessels": cellbank.vessels(r), "gel": ladders.gel(r)}
    return {k: v for k, v in out.items() if v}


def checks(derived: dict[str, Any]) -> list[str]:
    return [c for block in derived.values() for c in block.get("checks", [])]
