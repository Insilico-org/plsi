"""In vivo studies: genotypes called from genotyping bands, the roster with weights and ear marks, the genotype
counts against the cross (chi-square), and body-weight change per group."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from plsi.journal.results import Allele, Animal, Results
from plsi.journal.stats import chi2_p, summary
from plsi.journal.tuning import BAND_TOLERANCE, EXPECTED_MIN, WEIGHT_LOSS_PCT

FAILED = "failed"


def weights(r: Results) -> dict[str, Any]:
    """% change from each animal's first weight; per group and date the mean and SD."""
    if not r.weights:
        return {}
    groups: dict[str, set[str]] = defaultdict(set)
    for w in r.weights:
        groups[w.animal].add(w.group)
    if mixed := sorted(a for a, g in groups.items() if len(g) > 1):
        return {"checks": [f"animal ids in more than one group: {', '.join(mixed)}; give each animal its own id"]}
    first: dict[str, float] = {}
    by: dict[tuple[str, Any], list[float]] = defaultdict(list)
    checks = []
    for w in sorted(r.weights, key=lambda w: w.date):
        change = (w.grams - first.setdefault(w.animal, w.grams)) / first[w.animal] * 100
        by[(w.group, w.date)].append(change)
        if change <= -WEIGHT_LOSS_PCT:
            checks.append(f"{w.animal} ({w.group}) down {abs(change):.1f}% on {w.date}: compare with the protocol's humane endpoint")
    return {"checks": checks, "series": [{"group": g, "date": d.isoformat(), **summary(v)} for (g, d), v in sorted(by.items())]}


def _call(bands: list[float], alleles: list[Allele]) -> tuple[str, list[float]]:
    """The genotype the bands show: zygosity with two or more alleles ("WT/flox"), presence with one ("Cre+", "Cre-");
    a lane without its control band, or with no allele band, failed."""
    real = [a for a in alleles if not a.control]
    found, unmatched = set(), []
    for b in bands:
        if near := [a for a in alleles if abs(b - a.bp) <= BAND_TOLERANCE * a.bp]:
            found.add(min(near, key=lambda a: abs(b - a.bp)).name)
        else:
            unmatched.append(b)
    if any(a.control for a in alleles) and not any(a.name in found for a in alleles if a.control):
        return FAILED, unmatched
    hits = [a.name for a in real if a.name in found]
    if len(real) == 1:
        return real[0].name + ("+" if hits else "-"), unmatched
    if len(hits) == 1:
        return f"{hits[0]}/{hits[0]}", unmatched
    return ("/".join(hits) if len(hits) == 2 else FAILED), unmatched


def _alleles(genotype: str) -> list[str]:
    return sorted(x.strip().lower() for x in genotype.replace("−", "-").split("/"))


def _genotype(a: Animal, r: Results, checks: list[str]) -> str | None:
    """The call from the bands, checked against the lab's written call; the written call when there are no bands."""
    if a.bands is None or not r.alleles:
        return None
    call, unmatched = _call(a.bands, r.alleles)
    if unmatched:
        checks.append(f"{a.id}: band(s) {', '.join(f'{b:g}' for b in unmatched)} bp match no allele")
    if call == FAILED:
        checks.append(f"{a.id}: genotyping failed (no control band or no allele band); repeat the PCR")
    elif a.genotype and _alleles(a.genotype) != _alleles(call):
        checks.append(f"{a.id}: written as {a.genotype}, the bands show {call}")
    return call


def _ear_clashes(r: Results) -> list[str]:
    marks: dict[tuple, list[str]] = defaultdict(list)
    for a in r.animals:
        if a.ear_punch is not None:
            marks[(a.cage, tuple(sorted((p.ear.value, p.at.value) for p in a.ear_punch)))].append(a.id)
    return [f"{', '.join(ids)} have the same ear marks{f' in cage {cage}' if cage else ''}: they cannot be told apart"
            for (cage, _), ids in marks.items() if len(ids) > 1]


def _mendel(counts: Counter, expected: dict[str, float], checks: list[str]) -> dict[str, Any] | None:
    """Observed genotype counts against the cross's expected shares (chi-square)."""
    observed = {k: sum(n for g, n in counts.items() if _alleles(g) == _alleles(k)) for k in expected}
    total, share = sum(observed.values()), sum(expected.values())
    if other := sum(counts.values()) - total:
        checks.append(f"{other} animal(s) with a genotype the cross does not expect")
    if not total:
        return None
    exp = {k: total * expected[k] / share for k in expected}
    x = sum((observed[k] - exp[k]) ** 2 / exp[k] for k in expected if exp[k] > 0)
    df = sum(exp[k] > 0 for k in expected) - 1
    if min(exp.values()) < EXPECTED_MIN:
        checks.append(f"an expected genotype count is below {EXPECTED_MIN}: the chi-square p is rough")
    return {"rows": [{"genotype": k, "observed": observed[k], "expected": exp[k]} for k in expected],
            "chi2": x, "df": df, "p": chi2_p(x, df) if df > 0 else None, "n": total}


def roster(r: Results) -> dict[str, Any]:
    """Each animal with its genotype, latest weight and change; ear-mark clashes; genotype counts against the cross."""
    if not r.animals:
        return {}
    checks: list[str] = []
    seen: dict[str, list[float]] = defaultdict(list)
    for w in sorted(r.weights, key=lambda w: w.date):
        seen[w.animal].append(w.grams)
    rows = []
    for a in r.animals:
        call, ws = _genotype(a, r, checks), seen.get(a.id, [])
        rows.append({**a.dump(), "call": call or a.genotype, "from_bands": call is not None,
                     "weight": ws[-1] if ws else None, "change": (ws[-1] - ws[0]) / ws[0] * 100 if len(ws) > 1 else None})
    if r.weights and (extra := sorted(set(seen) - {a.id for a in r.animals})):
        checks.append(f"weights for animals not on the roster: {', '.join(extra)}")
    if dup := [k for k, n in Counter(a.id for a in r.animals).items() if n > 1]:
        checks.append(f"animal ids used twice: {', '.join(dup)}")
    checks += _ear_clashes(r)
    counts = Counter(row["call"] for row in rows if row["call"] and row["call"] != FAILED)
    out: dict[str, Any] = {"rows": rows, "counts": dict(counts), "checks": checks}
    if r.expected and counts and (m := _mendel(counts, r.expected, checks)):
        out["mendel"] = m
    return out
