"""`plsi calc range`: the range of a coordinate that fits the subject, the most specific match by sex and ethnicity."""

from __future__ import annotations

from typing import Any

from plsi import errors
from plsi.map import mapper, registry
from plsi.vocab import ValueStatus


def range_for(map_id: str, coordinate: str, instance: str) -> dict[str, Any]:
    m = registry.get(map_id, instance)
    c = next((x for x in m.coordinates if x.id == coordinate), None)
    if c is None:
        raise errors.NotFound(f"{coordinate} is not in {map_id}", hint=f"plsi maps show {map_id}")
    if not c.ranges:
        raise errors.ValidationError(f"{map_id} has no range for {coordinate}", code="NO_RANGE",
                                     hint="use the range printed on the lab report")
    subject = mapper.subject(instance)
    fits = c.best_ranges(subject.sex, subject.ethnicity)
    if not fits:
        raise errors.ValidationError(f"no range for {coordinate} fits this subject", code="NO_RANGE",
                                     hint="the ranges need the subject's sex: plsi init --sex")
    r = fits[0]  # one: registry rejects ties
    out: dict[str, Any] = {"map_id": m.id, "coordinate": c.id, "unit": c.unit, "low": r.low, "high": r.high,
                           "basis": {"sex": r.sex, "ethnicity": subject.ethnicity.value if r.ethnicity else None},
                           "source": r.source.model_dump(mode="json")}
    state = mapper.latest_state(instance, m.id)
    v = state.coordinates.get(c.id) if state else None
    if v and v.status == ValueStatus.PRESENT and isinstance(v.value, float):
        position = ("below" if r.low is not None and v.value < r.low
                    else "above" if r.high is not None and v.value >= r.high else "within")
        out |= {"value": v.value, "observed_at": v.observed_at.isoformat(), "position": position}
    return out
