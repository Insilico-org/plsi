"""Blood PhenoAge for a dashboard: the age, each marker's years against its printed range's middle, and a what-if."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from plsi.events import Event
from plsi.life.store import EventStore
from plsi.map import derive, mapper, registry, units
from plsi.map.models import CoordinateValue, MapCoordinate
from plsi.vocab import ValueStatus

MAP = "blood_phenoage"


def _printed_range(events: dict[str, Event], v: CoordinateValue, c: MapCoordinate) -> tuple[float | None, float | None]:
    """The range printed on the newest report this value came from, in the coordinate's unit."""
    for event_id in reversed(v.event_ids):
        o = events[event_id].payload
        if o.ref_low is None and o.ref_high is None:
            continue
        try:
            return tuple(None if b is None else units.to_canonical(b, o.unit, c)[0] for b in (o.ref_low, o.ref_high))
        except ValueError:  # a unit the map cannot convert: no range rather than a wrong one
            return None, None
    return None, None


def _age(inputs: dict[str, float], age: float) -> float | None:
    try:
        return derive.phenoage(inputs, age)
    except (ValueError, OverflowError):
        return None


def phenoage_view(instance: str) -> dict[str, Any] | None:
    """None without a projected state; {as_of, missing} while the map has no PhenoAge; else the map's own PhenoAge
    (inputs from draws within its window, a censored input bounded there), the draws it came from, and per marker the
    years against its printed range's middle. The breakdown is left out when a marker's latest value is not the one
    the age used (a newer single result) or is censored, rather than mixing draws or reading "<0.3" as 0.3."""
    state = mapper.latest_state(instance, MAP)
    if state is None:
        return None
    cs, m = state.coordinates, registry.get(MAP, instance)
    labels = {c.id: c for c in m.coordinates}
    rule = labels["phenoage"].derive  # a derived coordinate: derive is set
    markers, window = rule.inputs, timedelta(days=rule.window_days)  # type: ignore[union-attr]
    present = {k: cs[k] for k in (*markers, "chronological_age", "phenoage")
               if k in cs and cs[k].status == ValueStatus.PRESENT and isinstance(cs[k].value, float)}
    if "phenoage" not in present or "chronological_age" not in present:
        missing = [labels[k].label for k in markers if k not in present]
        return {"as_of": state.as_of,
                "missing": missing or [f"all {len(markers)} markers within {window.days} days of each other"]}
    pheno, age = present["phenoage"], present["chronological_age"].value
    base, drawn = pheno.value, pheno.observed_at
    first = min((present[k].observed_at for k in markers if k in present and present[k].observed_at
                 and drawn - window <= present[k].observed_at <= drawn), default=drawn)
    out = {"as_of": state.as_of, "drawn": drawn, "drawn_from": first, "phenoage": base, "age": age,
           "gap": base - age, "markers": [], "what_if": None, "moved": [],
           "gap_series": [{"t": p.t, "v": p.value} for p in (cs["phenoage_acceleration"].series
                                                            if "phenoage_acceleration" in cs else [])]}
    same = all(k in present and present[k].observed_at and drawn - window <= present[k].observed_at <= drawn
               and present[k].comparator is None for k in markers)
    if not same:
        return out | {"breakdown": "a marker has a newer or censored result than the age used"}
    inputs = {k: present[k].value for k in markers}
    events, edges = {e.id: e for e in EventStore(instance).events(active=False)}, dict(inputs)  # the log, read once
    for k in markers:
        c, v = labels[k], inputs[k]
        low, high = _printed_range(events, present[k], c)
        mid = (low + high) / 2 if low is not None and high is not None else None
        at_mid = _age({**inputs, k: mid}, age) if mid is not None else None
        if low is not None and v < low:
            edges[k] = low
        elif high is not None and v > high:
            edges[k] = high
        out["markers"].append({"coordinate": k, "label": c.label, "value": v, "unit": c.unit, "low": low,
                               "high": high, "years": None if at_mid is None else base - at_mid,
                               "outside": edges[k] != v})
    out["moved"] = [mk["label"] for mk in out["markers"] if mk["outside"]]
    out["what_if"] = _age(edges, age) if out["moved"] else None
    return out
