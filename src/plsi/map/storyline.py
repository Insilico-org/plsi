"""Storyline: clock accelerations, change vs the previous projection, gaps. Nothing else."""

from __future__ import annotations

from typing import Any

from plsi.map.models import StateDocument
from plsi.vocab import ValueStatus


def build(state: StateDocument, previous: StateDocument | None) -> dict[str, Any]:
    """{accelerations: {coord_id: value} (present *_acceleration coordinates), changes: [{coordinate, from, to, delta,
    unit}] (numeric values that differ from the previous stored projection), gaps}. Pure; no I/O."""
    accelerations = {
        cid: v.value for cid, v in state.coordinates.items()
        if cid.endswith("_acceleration") and v.status == ValueStatus.PRESENT and isinstance(v.value, float)
    }
    changes = []
    for cid, v in state.coordinates.items():
        old = previous.coordinates.get(cid) if previous else None
        if old and isinstance(v.value, float) and isinstance(old.value, float) and v.value != old.value:
            changes.append({"coordinate": cid, "from": old.value, "to": v.value, "delta": v.value - old.value, "unit": v.unit})
    return {"accelerations": accelerations, "changes": changes, "gaps": [g.model_dump(mode="json") for g in state.gaps]}
