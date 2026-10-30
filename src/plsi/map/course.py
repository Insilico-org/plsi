"""`plsi calc course`: where a measurement heads under scenarios, as a first-order approach to a new steady state.

Code computes, the bot judges: per scenario the bot gives the steady-state change (expected, low, high) and the
half-life of the approach, each from a cited source (for body weight, a published energy-balance model; for a marker,
a trial's effect and time course); this module only draws v(t) = v0 + change * (1 - 2^(-t / half_life)).
A baseline scenario with no change stays flat.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pydantic import Field, model_validator

from plsi.files import load_json
from plsi.map.models import Estimate
from plsi.models import Model, parse


class Change(Estimate):
    """The steady-state change, in the start value's unit."""


class CourseScenario(Model):
    name: str = Field(min_length=1)
    change: float | Change = 0.0  # the steady-state change, in the start value's unit
    half_life_days: float = Field(default=365, gt=0, le=3650)
    source: str | None = None

    @model_validator(mode="after")
    def _sourced(self) -> "CourseScenario":
        c = Change.of(self.change)
        if any(v for v in (c.expected, c.low, c.high)) and not self.source:
            raise ValueError(f"scenario {self.name!r} changes the course: cite its source")
        return self


class Start(Model):
    t: date
    v: float


class CourseSpec(Model):
    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    start: Start  # the recorded value the courses start from (state show)
    horizon_days: int = Field(ge=7, le=3650)
    step_days: int = Field(default=30, ge=1, le=365)
    scenarios: list[CourseScenario] = Field(min_length=1, max_length=8)  # the first is the baseline


def _at(v0: float, change: float, half_life: float, days: int) -> float:
    return v0 + change * (1 - 2 ** (-days / half_life))


def course(file: str) -> dict[str, Any]:
    """`plsi calc course --file spec.json`: per scenario, points {t, expected, low, high} every `step_days` to the horizon."""
    spec = parse(CourseSpec, load_json(file), "course spec")
    days = sorted({*range(0, spec.horizon_days, spec.step_days), spec.horizon_days})
    out = []
    for sc in spec.scenarios:
        c = Change.of(sc.change)
        points = []
        for d in days:
            values = [_at(spec.start.v, x, sc.half_life_days, d) for x in (c.expected, c.low, c.high) if x is not None]
            points.append({"t": (spec.start.t + timedelta(days=d)).isoformat(),
                           "expected": round(values[0], 2), "low": round(min(values), 2), "high": round(max(values), 2)})
        out.append({"name": sc.name, "change": c.model_dump(exclude_none=True), "half_life_days": sc.half_life_days,
                    "source": sc.source, "points": points})
    return {"label": spec.label, "unit": spec.unit, "start": spec.start.model_dump(mode="json"),
            "baseline": spec.scenarios[0].name, "scenarios": out}
