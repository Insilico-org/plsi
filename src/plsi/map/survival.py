"""`plsi calc survival`: remaining lifespan under scenarios, from a life table and proportional hazards.

Code computes, the bot judges: the bot picks the life table (the bundled UN WPP 2024 snapshot, or a table it took
from a `base_rate` reference) and, per scenario, the hazard ratio and the age shift with their sources; this module
only turns them into survival. Hazard per single year of age is mu(x) = -ln(1 - q(x)) (constant within the year;
an abridged interval of n years spreads its q evenly in hazard). Past the table's last age the hazard follows a
Gompertz line fitted to ln mu over the last 20 ages of the table, up to age 120.

Any country: the bot downloads the latest UN WPP single-age life table CSV ("Life_Table_Complete", per sex, plain
or .gz) from the WPP download centre and names it as `un_wpp.file`; rows are matched on ISO3_code, Time and Sex and
read from AgeGrpStart and qx.

A scenario multiplies the hazard by `hazard_ratio` from `after_years` on (proportional hazards) and reads the table
at age + `age_shift` (a biological-age gap, e.g. PhenoAge acceleration). These are population averages applied to
one person, not a forecast of their death: the output says so.
"""

from __future__ import annotations

import csv
import gzip
import io
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from plsi.errors import ValidationError
from plsi.files import load_json
from plsi.map.models import Estimate
from plsi.models import Model, parse
from plsi.vocab import Sex

DATA = Path(__file__).with_name("data")
WPP = DATA / "wpp2024_lx.csv"
_WPP_SEX = {Sex.F: "female", Sex.M: "male"}
MAX_AGE = 120
TAIL_FIT_AGES = 20
REACH_AGES = (70, 80, 90, 100)
APPLICABILITY = ("population-average survival for this age and sex, shifted by the scenario's cited hazard ratio "
                 "and age gap; not a prediction of one person's lifespan")


class Ratio(Estimate):
    """A hazard ratio with its interval."""


class Scenario(Model):
    name: str = Field(min_length=1)
    hazard_ratio: float | Ratio = 1.0
    after_years: float = Field(default=0, ge=0, le=60)
    age_shift: float = Field(default=0, ge=-30, le=30)
    source: str | None = None  # pmid:, doi:, a state or a reference id; required when the scenario changes anything

    @model_validator(mode="after")
    def _sourced(self) -> "Scenario":
        hr = Ratio.of(self.hazard_ratio)
        if any(v is not None and not 0.05 <= v <= 20 for v in (hr.expected, hr.low, hr.high)):
            raise ValueError("hazard ratios lie between 0.05 and 20")
        if (hr.expected != 1 or self.age_shift) and not self.source:
            raise ValueError(f"scenario {self.name!r} changes the hazard or the age: cite its source")
        return self


class TableRow(Model):
    """One row of a single-age or abridged life table: the probability q of dying between age and age + n."""
    age: int = Field(ge=0, le=MAX_AGE)
    n: int = Field(default=1, ge=1, le=20)
    q: float = Field(ge=0, le=1)


class Table(Model):
    """UN WPP (`un_wpp`: country ISO3 and year, from the bundled snapshot or a downloaded WPP CSV `file`) or the bot's
    own `q` rows with their `source`."""
    un_wpp: dict[str, Any] | None = None
    q: list[TableRow] | None = None
    source: str | None = None

    @model_validator(mode="after")
    def _one(self) -> "Table":
        if (self.un_wpp is None) == (self.q is None):
            raise ValueError("give exactly one of un_wpp {country, year} or q [{age, n, q}]")
        if self.q is not None and not self.source:
            raise ValueError("a table given as q rows needs its source (a base_rate reference)")
        return self


class SurvivalSpec(Model):
    age: int = Field(ge=0, le=110)
    sex: Sex
    table: Table
    scenarios: list[Scenario] = Field(min_length=1, max_length=8)  # the first is the baseline the others compare to

    @model_validator(mode="after")
    def _by_sex(self) -> "SurvivalSpec":
        if self.sex not in (Sex.F, Sex.M):
            raise ValueError("life tables are by sex: run F and M and show both, saying why")
        return self


@lru_cache(maxsize=1)
def _wpp() -> dict[tuple[str, str, int], dict[int, float]]:
    out: dict[tuple[str, str, int], dict[int, float]] = {}
    with WPP.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            out.setdefault((row["iso3"], row["sex"], int(row["year"])), {})[int(row["age"])] = float(row["lx"])
    return out


def _open(path: Path) -> io.TextIOBase:
    raw = path.open("rb")
    return io.TextIOWrapper(gzip.GzipFile(fileobj=raw) if path.suffix == ".gz" else raw, encoding="utf-8-sig", newline="")


def _from_wpp_file(sex: str, ref: dict[str, Any]) -> tuple[dict[int, float], str]:
    """One country, sex and year from a downloaded WPP Life_Table_Complete CSV, streamed (the files are large)."""
    path, iso3, year = Path(str(ref["file"])), str(ref.get("country", "")).upper(), str(ref.get("year", ""))
    want = _WPP_SEX[sex]
    if not path.is_file():
        raise ValidationError(f"no WPP file at {path}", hint="download the Life_Table_Complete CSV from population.un.org/wpp")
    rows: list[TableRow] = []
    with _open(path) as handle:
        reader = csv.DictReader(handle)
        need = {"ISO3_code", "Time", "AgeGrpStart", "qx"}
        if not need <= set(reader.fieldnames or ()):
            raise ValidationError(f"{path.name} is not a WPP life table CSV: it lacks {sorted(need - set(reader.fieldnames or ()))}")
        for r in reader:
            if r["ISO3_code"] == iso3 and r["Time"] == year and r.get("Sex", want).lower() == want:
                span = int(r.get("AgeGrpSpan") or 1)  # the open last group has span -1
                rows.append(TableRow(age=int(r["AgeGrpStart"]), n=max(span, 1), q=float(r["qx"])))
    if not rows:
        raise ValidationError(f"{path.name} has no {iso3} {want} {year} rows", hint="check the country code, the year and the file's sex")
    if len({r.age for r in rows}) != len(rows):
        raise ValidationError(f"{path.name} has several variants for {iso3} {year}: use the estimates file")
    return _from_rows(rows, f"UN WPP {path.name}, {iso3} {want} {year} (CC BY 3.0 IGO)")


def _from_wpp(sex: str, ref: dict[str, Any]) -> tuple[dict[int, float], str]:
    if ref.get("file"):
        return _from_wpp_file(sex, ref)
    key = (str(ref.get("country", "")).upper(), _WPP_SEX[sex], int(ref.get("year", 0)))
    lx = _wpp().get(key)
    if lx is None:
        have = ", ".join(sorted({f"{c} {y}" for c, _, y in _wpp()}))
        raise ValidationError(f"the bundled UN WPP 2024 snapshot has no table for {key[0]} {key[2]}",
                              hint=f"it covers {have}; otherwise download the WPP life table CSV and give it as un_wpp.file")
    ages = sorted(lx)
    mu = {x: -math.log(lx[x + 1] / lx[x]) for x in ages[:-1]}
    return mu, f"UN WPP 2024 period life table, {key[0]} {key[1]} {key[2]} (CC BY 3.0 IGO)"


def _from_rows(rows: list[TableRow], source: str) -> tuple[dict[int, float], str]:
    mu: dict[int, float] = {}
    for r in sorted(rows, key=lambda r: r.age):
        if r.q >= 1:
            break  # an open last interval: the Gompertz tail takes over
        for x in range(r.age, min(r.age + r.n, MAX_AGE)):
            mu[x] = -math.log(1 - r.q) / r.n
    if len(mu) < TAIL_FIT_AGES or sorted(mu) != list(range(min(mu), max(mu) + 1)):
        raise ValidationError("the q rows must cover at least 20 consecutive years of age without gaps")
    return mu, source


def _with_tail(mu: dict[int, float]) -> dict[int, float]:
    """Extend ln mu with a least-squares Gompertz line over the table's last ages, up to MAX_AGE."""
    xs = [x for x in sorted(mu)[-TAIL_FIT_AGES:] if mu[x] > 0]
    ys = [math.log(mu[x]) for x in xs]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    full = dict(mu)
    for x in range(max(mu) + 1, MAX_AGE):
        full[x] = math.exp(my + b * (x - mx))
    return full


def _hazard(mu: dict[int, float], age: float) -> float:
    """mu at a fractional age (log-linear between whole ages; clamped to the table)."""
    lo = min(max(math.floor(age), min(mu)), MAX_AGE - 1)
    hi = min(lo + 1, MAX_AGE - 1)
    w = min(max(age - lo, 0), 1)
    a, b = max(mu[lo], 1e-12), max(mu[hi], 1e-12)
    return math.exp((1 - w) * math.log(a) + w * math.log(b))


def _run(mu: dict[int, float], age: int, hr: float, after: float, shift: float) -> dict[str, Any]:
    s, curve, life, median = 1.0, [{"age": age, "survival": 1.0}], 0.0, None
    for k in range(MAX_AGE - age):
        h = _hazard(mu, age + k + shift) * (hr if k >= after else 1.0)
        nxt = s * math.exp(-h)
        life += (s + nxt) / 2
        if median is None and nxt < 0.5:
            median = age + k + math.log(s / 0.5) / h
        s = nxt
        curve.append({"age": age + k + 1, "survival": round(s, 4)})
    reach = {str(a): round(next(p["survival"] for p in curve if p["age"] == a), 4) for a in REACH_AGES if a > age}
    return {"life_expectancy_years": round(life, 2), "expected_age_at_death": round(age + life, 1),
            "median_age_at_death": round(median, 1) if median is not None else None, "p_reach": reach,
            "curve": [p for p in curve if p["survival"] >= 0.001 or p["age"] % 10 == 0]}


def survival(file: str) -> dict[str, Any]:
    """`plsi calc survival --file spec.json`: per scenario, remaining life expectancy, median age at death, the chance
    of reaching 70/80/90/100 and the yearly survival curve, with low/high from the hazard-ratio interval."""
    spec = parse(SurvivalSpec, load_json(file), "survival spec")
    t = spec.table
    mu, table = _from_wpp(spec.sex, t.un_wpp) if t.un_wpp else _from_rows(t.q or [], t.source or "")
    mu = _with_tail(mu)
    out = []
    for sc in spec.scenarios:
        hr = Ratio.of(sc.hazard_ratio)
        row = {"name": sc.name, "hazard_ratio": hr.model_dump(exclude_none=True), "after_years": sc.after_years,
               "age_shift": sc.age_shift, "source": sc.source, **_run(mu, spec.age, hr.expected, sc.after_years, sc.age_shift)}
        bounds = [_run(mu, spec.age, v, sc.after_years, sc.age_shift)["life_expectancy_years"]
                  for v in (hr.low, hr.high) if v is not None]
        if bounds:
            span = [*bounds, row["life_expectancy_years"]]
            row["life_expectancy_low"], row["life_expectancy_high"] = min(span), max(span)
        out.append(row)
    base = out[0]["life_expectancy_years"]
    for row in out:
        row["years_vs_baseline"] = round(row["life_expectancy_years"] - base, 2)
    return {"age": spec.age, "sex": spec.sex, "table": table, "tail": f"Gompertz fit on the table's last {TAIL_FIT_AGES} ages, to {MAX_AGE}",
            "applicability": APPLICABILITY, "baseline": spec.scenarios[0].name, "scenarios": out}
