"""The deidentified package for the Longevity Mothership (WIRE §2), from published states, recorded life events and
prediction scores, gate-checked into the instance's outbox. Coded fields only: items and events go as their code, a
free or cpg code only when a map declares it, never a plsi.codes.NEVER_SHARED code (the subject is sex, a five-year age
band and the ethnicity group); a unit only when it is a map's canonical unit or in the unit table (plsi.life.normalize),
else its value stays too; a dose as {value, unit} only with a DOSE_UNITS or canonical unit, never as written.
No age leaves: every coordinate plsi.map.derive.kept_local finds in the state's map stays on this computer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from plsi import codes, files
from plsi.clock import now
from plsi.life.store import EventStore
from plsi.life.normalize import known_unit
from plsi.map import derive, mapper, registry
from plsi.map.models import CoordinateValue
from plsi.models import Code
from plsi.mothership import gate
from plsi.mothership.content import SCORE_KEYS
from plsi.mothership.enroll import active, outbox
from plsi.mothership.relay import address, header
from plsi.policy.score import calibration
from plsi.vocab import ContributionKind, EventType, MothershipMessage, ObservationKind

LIFE_KINDS = frozenset({ObservationKind.CONDITION, ObservationKind.INTERVENTION, ObservationKind.LIFESTYLE,
                        ObservationKind.SYMPTOM, ObservationKind.MEDICATION, ObservationKind.ALLERGY})
MIN_SCORES = 5
# UCUM symbols a dose may carry on the wire (annotations for counted forms)
DOSE_UNITS = frozenset({"mg", "g", "ug", "ng", "mL", "L", "uL", "[iU]", "[IU]", "U", "mmol", "umol", "meq", "%",
                        "{tablet}", "{capsule}", "{puff}", "{drop}", "{spray}", "{patch}", "{dose}"})


def _month(t: datetime | None) -> str | None:
    return t.strftime("%Y-%m") if t else None


def _monthly(series: list[Any]) -> list[dict[str, Any]]:
    """One point per month: its mean and `n`, how many recorded values the mean covers."""
    by: dict[str, list[float]] = {}
    for p in series:
        by.setdefault(str(_month(p.t)), []).append(p.value)
    return [{"t": m, "value": float(f"{fmean(vals):.6g}"), "n": len(vals)} for m, vals in sorted(by.items())]


class _Wire:
    """What may leave for this instance: the declared free and cpg codes and the known units."""

    def __init__(self, instance: str) -> None:
        self.declared = registry.declared_codes(instance)
        self.units = registry.canonical_units(instance)

    def code(self, code: Code | None) -> dict[str, str] | None:
        """{system, code} of a code that may leave (plsi.codes.shareable); the display never leaves."""
        return {"system": code.system.value, "code": code.code} if code and codes.shareable(
            code.system.value, code.code, self.declared) else None

    def unit(self, unit: str | None) -> bool:
        return unit is None or unit in self.units or known_unit(unit)

    def dose(self, quantity: float | None, unit: str | None) -> dict[str, Any]:
        """{"dose": {value, unit}} of a structured dose whose unit may leave, else {}."""
        ok = quantity is not None and unit is not None and (unit in DOSE_UNITS or unit in self.units)
        return {"dose": {"value": quantity, "unit": unit}} if ok else {}

    def coordinate(self, v: CoordinateValue) -> dict[str, Any]:
        out: dict[str, Any] = {"status": v.status.value}
        if isinstance(v.value, list):
            out["items"] = [{"code": code} | ({"clinical_status": i.clinical_status.value} if i.clinical_status else {})
                            | self.dose(i.dose_quantity, i.dose_unit) for i in v.value if (code := self.code(i.code))]
        else:
            out |= {k: val for k, val in {"value": v.value, "unit": v.unit,
                                          "comparator": v.comparator.value if v.comparator else None,
                                          "observed": _month(v.observed_at)}.items() if val is not None}
        if v.series:
            out["series"] = _monthly(v.series)
            month = [p["value"] for p in out["series"] if p["t"] == out.get("observed")]
            if "value" in out and v.comparator is None and month:  # the headline value is that month's mean too
                out["value"] = month[0]
        return out

    def states(self, store: EventStore) -> list[dict[str, Any]]:
        out = []
        for doc in mapper.latest_states(store.instance):
            if doc.map_id in mapper.LOCAL_MAPS:
                continue
            local = derive.kept_local(registry.load_snapshot(store.instance, doc.map_id, doc.map_hash).coordinates)
            out.append({"map_id": doc.map_id, "map_version": doc.map_version, "map_hash": doc.map_hash.removeprefix("sha256:"),
                        "as_of": _month(doc.as_of), "gaps": sorted(g.coordinate for g in doc.gaps),
                        "coordinates": {c: self.coordinate(v) for c, v in doc.coordinates.items()
                                        if v.value is not None and c not in local
                                        and (isinstance(v.value, list) or self.unit(v.unit))}})
        return out

    def life_events(self, store: EventStore) -> list[dict[str, Any]]:
        out = []
        for e in store.events(EventType.OBSERVATION):
            o = e.payload
            if o.kind in LIFE_KINDS and (code := self.code(o.code)):
                measured = o.value_quantity is not None and self.unit(o.unit)
                item = {"kind": o.kind.value, "year": o.effective_at.year,
                        "until": o.effective_end.year if o.effective_end else None, "basis": o.effective_basis.value,
                        "code": code, "value": o.value_quantity if measured else None, "unit": o.unit if measured else None,
                        "clinical_status": o.clinical_status.value if o.clinical_status else None}
                out.append({k: v for k, v in item.items() if v is not None} | self.dose(o.dose_quantity, o.dose_unit))
        return sorted(out, key=lambda i: (i["year"], i["kind"], i["code"]["system"], i["code"]["code"]))


def _summary(scores: dict[str, Any]) -> dict[str, Any]:
    """A calibration summary as the wire carries it: the content.SCORE_KEYS only."""
    return {k: v for k, v in scores.items() if k in SCORE_KEYS}


def _scores(store: EventStore) -> dict[str, Any]:
    cal = calibration(store.instance)
    cells = {c: _summary(s) for c, s in cal["by_coordinate"].items() if s["n_scored"] >= MIN_SCORES}
    return {"overall": _summary(cal["overall"]), "by_coordinate": cells} if cal["overall"]["n_scored"] >= MIN_SCORES else {}


def _age_band(birth_year: int | None, age_group: str | None) -> str | None:
    if age_group:
        return age_group
    if birth_year is None:
        return None
    low = (now().year - birth_year) // 5 * 5
    return f"{low}-{low + 4}"


def pack(instance: str, out: str | None = None) -> dict[str, Any]:
    """`mothership pack`: the deidentified package of the consented kinds, gate-checked; nothing is sent."""
    record = active(instance)
    store = EventStore(instance)
    kinds = set(record["kinds"])
    subject = {"sex": store.subject.sex.value, "age_band": _age_band(store.subject.birth_year, store.subject.age_group),
               "ethnicity": store.subject.ethnicity}
    doc = header(MothershipMessage.CONTRIBUTION) | {
        "contributor_id": record["contributor_id"], "consent_version": record["consent_version"], "packed": _month(now()),
        "kinds": sorted(kinds), "subject": {k: v for k, v in subject.items() if v}}
    wire = _Wire(instance)
    build = {ContributionKind.STATES: wire.states, ContributionKind.LIFE_EVENTS: wire.life_events,
             ContributionKind.SCORES: _scores}
    doc |= {kind.value: section(store) for kind, section in build.items() if kind in kinds}
    gate.require(doc, instance, what="package")
    path = Path(out) if out else outbox(instance, "contribution")
    files.atomic_write_json(path, doc)
    counts = {"states": len(doc.get("states", [])), "life_events": len(doc.get("life_events", [])),
              "scored_predictions": doc.get("scores", {}).get("overall", {}).get("n_scored", 0)}
    return {"file": str(path), "to": address(), "package_hash": files.hash_json(doc), "counts": counts}
