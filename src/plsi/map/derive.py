"""Derive engines and the native derived coordinates.

Blood PhenoAge (Levine 2018, doi:10.18632/aging.101414) — NOT biolearn's DNAm "PhenoAge":
  xb = -19.907 - 0.0336*alb(g/L) + 0.0095*creat(umol/L) + 0.1953*glu(mmol/L) + 0.0954*ln(CRP mg/dL)
       - 0.0120*lymph% + 0.0268*MCV + 0.3306*RDW + 0.00188*ALP + 0.0554*WBC + 0.0804*age
  M = 1 - exp(-exp(xb) * (exp(120*g) - 1) / g), g = 0.0076927
  PhenoAge = 141.50225 + ln(-0.00553 * ln(1 - M)) / 0.090165
Verified 2026-10-20: the weights against Levine 2018 Table 1 (PMC5940111; ALP printed as 0.0019); the intercept,
Gompertz gamma and the PhenoAge transform against the BioAge reference implementation (Kwon & Belsky 2021,
doi:10.1007/s11357-021-00480-5, github.com/dayoonkwon/BioAge R/phenoage_calc.R, orig=TRUE: -19.90667, 0.007692696,
1.51714 = exp(120*g) - 1, 141.50225, -0.0055305, 0.090165). biolearn.hematology uses mistyped weights (RDW 0.3356).

Censored inputs (e.g. CRP '<0.3'): for a function monotone in each input the value at the reported bound is itself
a bound on the result; `bounded` finds its side by nudging each censored input inward. Native models are monotone;
expr formulas qualify when they have no comparison or piecewise function; extensions declare it in their manifest.

Age-based coordinates (`age_based`): a value computed from the person's age gives the birth year back (an age, or an
age acceleration with its clock's inputs), so it never leaves the computer.
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from plsi import errors, extensions
from plsi.map import biolearn, formula
from plsi.map.models import Derive, MapCoordinate
from plsi.vocab import Comparator, DeriveEngine, ExtensionKind

PHENOAGE_WEIGHTS = {
    "albumin": -0.0336, "creatinine": 0.0095, "glucose": 0.1953, "lymphocyte_pct": -0.0120, "mcv": 0.0268,
    "rdw": 0.3306, "alp": 0.00188, "wbc": 0.0554,
}


def rule_id(model: str) -> str:
    """SourceRef id for a native derivation, e.g. 'plsi.derive.phenoage' (verify kind rule)."""
    return f"plsi.derive.{model}"


def rule_ids() -> set[str]:
    """All registered rule ids (evidence verify --kind rule resolves against this)."""
    return {rule_id(m) for m in NATIVE_MODELS}


def chronological_age(birth_year: int, at: datetime) -> float:
    """Age at the draw = year_fraction(at) - (birth_year + 0.5), year_fraction = year + (day_of_year - 1)/days_in_year."""
    days = 366 if calendar.isleap(at.year) else 365
    return at.year + (at.timetuple().tm_yday - 1) / days - (birth_year + 0.5)


def phenoage(inputs: dict[str, float], age: float) -> float:
    """Blood PhenoAge from canonical-unit inputs keyed albumin, creatinine, glucose, crp, lymphocyte_pct, mcv, rdw,
    alp, wbc. Raises ValueError for crp <= 0 or a math domain error."""
    if inputs["crp"] <= 0:
        raise ValueError("PhenoAge needs CRP > 0 (ln CRP)")
    xb = -19.907 + 0.0954 * math.log(inputs["crp"]) + 0.0804 * age
    xb += sum(w * inputs[k] for k, w in PHENOAGE_WEIGHTS.items())
    gamma = 0.0076927
    mortality = 1 - math.exp(-math.exp(xb) * (math.exp(120 * gamma) - 1) / gamma)
    return 141.50225 + math.log(-0.00553 * math.log(1 - mortality)) / 0.090165


# Native model names usable as `derive.model` with engine native: (inputs, age at the draw) -> value.
NATIVE_MODELS: dict[str, Callable[[dict[str, float], float], float]] = {
    "chronological_age": lambda inputs, age: age,
    "phenoage": phenoage,
    "phenoage_acceleration": lambda inputs, age: phenoage(inputs, age) - age,
}


def compute(model: str, inputs: dict[str, float], *, birth_year: int | None, at: datetime) -> float:
    """Evaluate a NATIVE_MODELS entry from same-day canonical inputs (keys = input coordinate ids).
    Every native model needs birth_year (ValueError if None). Raises KeyError for an unknown model."""
    fn = NATIVE_MODELS[model]
    if birth_year is None:
        raise ValueError("birth_year is unknown (or withheld as 90+)")
    return fn(inputs, chronological_age(birth_year, at))


def age_at(birth_year: int | None, at: datetime) -> float | None:
    return chronological_age(birth_year, at) if birth_year is not None else None


Evaluator = Callable[[Derive, dict[str, float], int | None, str, datetime], float]  # (d, values, birth_year, sex, at)


@dataclass(frozen=True)
class Engine:
    """One derive engine. evaluate None: not a scalar deriver (biolearn runs in the mapper on an artifact).
    models: the known model names, None when they cannot be checked; unknown: (violation rule, message, hint);
    reads_age: whether the derive is given the person's age."""

    evaluate: Evaluator | None
    rule_id: Callable[[Derive], str]
    censor_safe: Callable[[Derive], bool]
    reads_age: Callable[[Derive], bool]
    models: Callable[[], set[str] | None] | None = None
    unknown: tuple[str, str, str] | None = None


ENGINES: dict[DeriveEngine, Engine] = {
    DeriveEngine.NATIVE: Engine(
        lambda d, v, birth_year, sex, at: compute(d.model, v, birth_year=birth_year, at=at),
        lambda d: rule_id(d.model), lambda d: True, lambda d: True, lambda: set(NATIVE_MODELS),
        ("map.native_model", "unknown native model {!r}", f"one of {sorted(NATIVE_MODELS)}")),
    DeriveEngine.EXPR: Engine(
        lambda d, v, birth_year, sex, at: formula.evaluate(d.formula or "", v, age=age_at(birth_year, at), sex=sex),
        lambda d: f"{DeriveEngine.EXPR.value}:{d.model}", lambda d: formula.monotone_safe(d.formula or ""),
        lambda d: "age" in formula.variables(d.formula or "")),
    DeriveEngine.EXTENSION: Engine(
        lambda d, v, birth_year, sex, at: float(extensions.deriver(d.model)(dict(v), age=age_at(birth_year, at), sex=sex)),
        lambda d: extensions.rule_id(d.model), lambda d: bool(extensions.manifest(d.model).monotone), lambda d: True,
        lambda: set(extensions.installed(ExtensionKind.DERIVER)),
        ("map.extension_missing", "no active deriver extension {!r}", "plsi ext list")),
    DeriveEngine.BIOLEARN: Engine(
        # reads_age False: the clocks that read age (GrimAge) output years, which age_based excludes by unit
        None, lambda d: f"{DeriveEngine.BIOLEARN.value}:{d.model}", lambda d: False, lambda d: False,
        lambda: {x["name"] for x in biolearn.clocks()} if biolearn.available() else None,
        ("map.biolearn_model", "{!r} is not a biolearn aging clock", "plsi clocks list")),
}


AGE_UNIT = "a"  # UCUM years: a derived value in years is an age or an age acceleration


def age_based(coordinates: list[MapCoordinate]) -> set[str]:
    """The derived coordinates computed from chronological age: the derive is given the age (every native model, an
    expr formula reading `age`, any extension), the value is in years (any clock's age or age acceleration), or an
    input is itself age-based."""
    out: set[str] = set()
    while more := {c.id for c in coordinates if c.derive and c.id not in out
                   and (ENGINES[c.derive.engine].reads_age(c.derive) or c.unit == AGE_UNIT or out & set(c.derive.inputs))}:
        out |= more
    return out


def scalar(d: Derive) -> bool:
    """Whether d's engine evaluates same-day scalar inputs (native, expr, extension)."""
    return ENGINES[d.engine].evaluate is not None


def evaluate(d: Derive, values: dict[str, float], *, birth_year: int | None, sex: str, at: datetime) -> float:
    """One derived value from same-day canonical inputs, for the scalar engines (native, expr, extension)."""
    fn = ENGINES[d.engine].evaluate
    if fn is None:
        raise ValueError(f"engine {d.engine.value} is not a scalar deriver")
    return fn(d, values, birth_year, sex, at)


def bounded(fn: Callable[[dict[str, float]], float], inputs: dict[str, float],
            censored: dict[str, Comparator]) -> tuple[float, Comparator | None]:
    """fn(inputs) with censored inputs at their reported bound -> (value, comparator of the result).
    Raises ValueError when censored inputs push the result in opposite directions."""
    value = fn(inputs)
    sides, strict = set(), False
    for cid, comparator in censored.items():
        below = comparator in (Comparator.LT, Comparator.LE)
        step = (abs(inputs[cid]) or 1.0) * 1e-6
        nudged = fn({**inputs, cid: inputs[cid] - step if below else inputs[cid] + step})
        if nudged != value:  # the true input lies on the nudged side, so the true result lies the way the result moved
            sides.add("<" if nudged < value else ">")
            strict |= comparator in (Comparator.LT, Comparator.GT)
    if len(sides) > 1:
        raise ValueError(f"censored inputs {sorted(censored)} bound the result from opposite sides")
    return value, (Comparator(sides.pop() + ("" if strict else "=")) if sides else None)


def clocks() -> list[dict[str, Any]]:
    """`plsi clocks list`: native blood PhenoAge plus plsi.map.biolearn.clocks() when the extra is installed."""
    out: list[dict[str, Any]] = [{
        "name": "phenoage", "engine": DeriveEngine.NATIVE.value, "tissue": "Blood (clinical chemistry)", "output": "Age (Years)",
        "source": "https://doi.org/10.18632/aging.101414",
        "usage_note": "Levine 2018 blood PhenoAge; biolearn's 'PhenoAge' is the DNA-methylation clock, a different model",
    }]
    if biolearn.available():
        out += [{**m, "engine": DeriveEngine.BIOLEARN.value} for m in biolearn.clocks()]
    else:
        errors.warn("DEPENDENCY_MISSING", f"biolearn clocks need the clocks extra: {biolearn.HINT}")
    return out
