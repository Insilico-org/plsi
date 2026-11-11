"""One patient's records as the clinic dashboard reads them: grouped, with one series per test."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from functools import cached_property
from typing import Any

from plsi.clinic import roster
from plsi.clock import now
from plsi.life.models import Observation, Subject
from plsi.life.store import EventStore
from plsi.map import registry, units
from plsi.map.models import MapCoordinate
from plsi.map.projection import accepts
from plsi.policy.plan import list_plans
from plsi.policy.score import due
from plsi.report import series_name
from plsi.vocab import ClinicalStatus, DueState, MeasureGroup, ObservationKind, OriginKind

MED_STATUS = {ClinicalStatus.ACTIVE: "current", ClinicalStatus.STOPPED: "past", ClinicalStatus.RESOLVED: "past"}
MED_ORDER = ("current", "not sure", "past")  # how the medicines table is sorted


def day(t: datetime | date | str | None) -> str:
    if isinstance(t, datetime):
        t = t.date()
    return t.isoformat() if isinstance(t, date) else (t or "")[:10]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def value(o: Observation) -> str:
    if o.value_quantity is not None:
        return (o.value_comparator.value if o.value_comparator else "") + f"{round(o.value_quantity, 4):g}"
    if o.value_bool is not None:
        return "yes" if o.value_bool else "no"
    return o.value_text or ""


def ref_range(o: Observation) -> str:
    if o.ref_low is None and o.ref_high is None:
        return ""
    return "–".join("" if v is None else f"{v:g}" for v in (o.ref_low, o.ref_high))


def outside(o: Observation) -> bool:
    """The lab's own flag, else the report's own range; neither: never outside."""
    v = o.value_quantity
    return o.flag is not None or (v is not None and ((o.ref_low is not None and v < o.ref_low)
                                                     or (o.ref_high is not None and v > o.ref_high)))


def group(o: Observation) -> str:
    """A MeasureGroup for a measurement, else the observation's kind."""
    if o.kind != ObservationKind.MEASUREMENT:
        return o.kind.value
    if o.origin.kind in (OriginKind.DEVICE, OriginKind.EXTENSION):
        return MeasureGroup.DEVICE.value
    lab = o.specimen or o.ref_low is not None or o.ref_high is not None or o.flag or o.origin.kind == OriginKind.METHYLATION
    return (MeasureGroup.LAB if lab else MeasureGroup.BODY).value


def name(o: Observation) -> str:
    return series_name(o.code.display if o.code and o.code.display else o.original_text)


def coordinates(instance: str) -> list[MapCoordinate]:
    """The coordinates a measurement can be shown as: every map coordinate with accepted codes and a unit."""
    return [c for m in registry.load_all(instance).values() for c in m.coordinates if c.accepts.codes and c.unit]


def _rounded(given: float, converted: float, conversion: dict[str, Any] | None) -> float:
    """A converted value to three significant figures; a value in its own unit as recorded."""
    unchanged = conversion is None or (conversion.get("factor") == 1.0 and not conversion.get("offset"))
    return given if unchanged else float(f"{converted:.3g}")


def as_coordinate(o: Observation, cs: list[MapCoordinate]) -> Observation:
    """A measurement as its map coordinate shows it: the coordinate's label and first code, its value and report
    range in the canonical unit (the maps' own conversion). Unchanged when no coordinate takes it or its unit does
    not convert, so one test is one row whatever code or unit it came with."""
    c = next((c for c in cs if accepts(c, o)), None) if o.value_quantity is not None else None
    if c is None:
        return o
    try:
        low, quantity, high = (None if v is None else _rounded(v, *units.to_canonical(v, o.unit, c))
                               for v in (o.ref_low, o.value_quantity, o.ref_high))
    except ValueError:
        return o
    code = c.accepts.codes[0].model_copy(update={"display": c.label})
    return o.model_copy(update={"code": code, "unit": c.unit, "value_quantity": quantity, "ref_low": low, "ref_high": high})


def series(obs: list[Observation]) -> list[list[Observation]]:
    """One list per test (its code, else its name as written, and its unit), oldest first."""
    out: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for o in sorted(obs, key=lambda o: o.effective_at):
        out[(f"{o.code.system.value}:{o.code.code}" if o.code else norm(o.original_text), o.unit or "")].append(o)
    return sorted(out.values(), key=lambda s: (not outside(s[-1]), name(s[-1]).casefold()))


def med_status(o: Observation) -> str:
    return MED_STATUS.get(o.clinical_status, "not sure")  # a past or unclear one is never shown as current


@dataclass(frozen=True)
class Patient:
    """What the dashboard reads for one roster row; both tabs are drawn from it."""

    row: dict[str, Any]
    subject: Subject
    groups: dict[str, list[Observation]]  # group() -> observations
    plans: list[dict[str, Any]]
    due: list[dict[str, Any]]
    waiting: list[dict[str, Any]]
    ledger: list[dict[str, Any]]  # this patient's clinic ledger lines

    @property
    def label(self) -> str:
        return self.row["label"]

    @property
    def link(self) -> dict[str, str]:
        return {"text": roster.shown(self.row), "href": f"#{self.label}"}

    @cached_property
    def labs(self) -> list[list[Observation]]:
        return series(self.groups.get(MeasureGroup.LAB.value, []))

    @property
    def out_of_range(self) -> list[list[Observation]]:
        return [s for s in self.labs if outside(s[-1])]

    @property
    def follow_ups(self) -> list[dict[str, Any]]:
        return [d for d in self.due if d["state"] != DueState.AWAITING.value]

    @cached_property
    def medicines(self) -> list[Observation]:
        latest = {norm(o.original_text): o for o in sorted(self.groups.get(ObservationKind.MEDICATION.value, []),
                                                            key=lambda o: o.effective_at)}
        return sorted(latest.values(), key=lambda o: (MED_ORDER.index(med_status(o)), o.original_text.casefold()))

    @property
    def latest(self) -> str:
        return max((day(o.effective_at) for g in (MeasureGroup.LAB, MeasureGroup.BODY)
                    for o in self.groups.get(g.value, [])), default="")

    @property
    def sex_age(self) -> tuple[str, str]:
        s = self.subject
        age = f"about {now().year - s.birth_year}" if s.birth_year else "90 or older" if s.age_group else "not given"
        return {"M": "male", "F": "female", "X": "other"}.get(s.sex.value, "not given"), age


def gather(row: dict[str, Any], ledger: list[dict[str, Any]]) -> Patient:
    label = row["label"]
    store = EventStore(label)
    groups: dict[str, list[Observation]] = defaultdict(list)
    cs = coordinates(label)
    for e in store.observations():
        o = as_coordinate(e.payload, cs) if e.payload.kind == ObservationKind.MEASUREMENT else e.payload
        groups[group(o)].append(o)
    return Patient(row, store.subject, dict(groups), list_plans(label), due(label)["instances"].get(label, []),
                   roster.waiting(label, ledger) if row.get("inbox") else [], [e for e in ledger if e.get("label") == label])
