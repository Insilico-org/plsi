"""Calculators for the bots (`plsi calc`): a value into a coordinate's canonical unit, and a derived coordinate
(clock, score, ratio) from given or what-if inputs. Pure: nothing is written. Bots never convert or compute by hand."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from plsi import errors
from plsi.clock import now
from plsi.files import load_json
from plsi.map import derive, mapper, registry, units
from plsi.map.models import MapContract, MapCoordinate
from plsi.vocab import CoordinateKind, ValueStatus

NO_CONVERSION_HINT = ("a different unit can mean a different measurement (RDW in fL is RDW-SD, not RDW-CV in %): "
                      "check the code with plsi normalize; never convert by hand")


def _coordinate(m: MapContract, coordinate: str) -> MapCoordinate:
    if (c := m.coordinate(coordinate)) is None:
        raise errors.NotFound(f"map {m.id} has no coordinate {coordinate!r}", code="COORDINATE_NOT_FOUND",
                              hint=f"plsi maps show {m.id}")
    return c


def convert(map_id: str, coordinate: str, value: float, unit: str, instance: str | None = None) -> dict[str, Any]:
    """`plsi calc convert`: {value, unit, conversion} in the coordinate's canonical unit, or NO_CONVERSION."""
    c = _coordinate(registry.get(map_id, instance), coordinate)
    try:
        out, conversion = units.to_canonical(value, unit, c)
    except ValueError as exc:
        raise errors.ValidationError(str(exc), code="NO_CONVERSION", hint=NO_CONVERSION_HINT) from None
    return {"value": out, "unit": c.unit, "conversion": conversion}


def _scalar(c: MapCoordinate) -> bool:
    return c.kind == CoordinateKind.DERIVED and c.derive is not None and derive.scalar(c.derive)


def _value(m: MapContract, c: MapCoordinate, given: dict[str, float], ctx: dict[str, Any], missing: set[str]) -> float | None:
    values = {}
    for cid in c.derive.inputs:  # type: ignore[union-attr]
        if cid in given:
            values[cid] = given[cid]
        elif (inner := m.coordinate(cid)) is not None and _scalar(inner):
            if (v := _value(m, inner, given, ctx, missing)) is not None:
                values[cid] = given[cid] = v
        else:
            missing.add(cid)
    if missing:
        return None
    try:
        return derive.evaluate(c.derive, values, **ctx)  # type: ignore[arg-type]
    except (ValueError, KeyError) as exc:
        raise errors.ValidationError(f"{c.id}: {exc}", code="CALC_FAILED") from None


def _drawn(state: Any, coordinate: str) -> datetime | None:
    v = state.coordinates.get(coordinate) if state else None
    return v.observed_at if v and v.status == ValueStatus.PRESENT else None


def compute(map_id: str, coordinate: str, instance: str | None = None, inputs: str | None = None,
            set_values: list[str] | None = None, birth_year: int | None = None, sex: str | None = None,
            at: datetime | None = None) -> dict[str, Any]:
    """`plsi calc derive`: a derived coordinate from the instance's published measured values (if --instance),
    overridden by --inputs {coordinate: value} and --set coordinate=value (canonical units). Derived inputs are always
    recomputed. Birth year and sex default to the instance's subject; --at (age) to the published value's draw date,
    else now. Pass --at for a value at a prediction horizon."""
    m = registry.get(map_id, instance)
    c = _coordinate(m, coordinate)
    if not _scalar(c):
        raise errors.ValidationError(f"{coordinate} is not a scalar derived coordinate", hint=f"plsi maps show {map_id}")
    given: dict[str, float] = {}
    state = mapper.latest_state(instance, m.id) if instance else None
    if state:
        given = {cid: v.value for cid, v in state.coordinates.items() if v.status == ValueStatus.PRESENT
                 and isinstance(v.value, float) and not _scalar(_coordinate(m, cid))}
    overrides = {**(load_json(inputs) if inputs else {})}
    for item in set_values or []:
        key, sep, raw = item.partition("=")
        try:
            overrides[key.strip()] = float(raw)
        except ValueError:
            sep = ""
        if not sep:
            raise errors.UsageError(f"--set expects coordinate=number, got {item!r}")
    for key in overrides:
        _coordinate(m, key)
    given |= {k: float(v) for k, v in overrides.items()}
    subject = mapper.subject(instance) if instance else None
    ctx = {"birth_year": birth_year if birth_year is not None else (subject.birth_year if subject else None),
           "sex": sex or (subject.sex.value if subject else "unknown"), "at": at or _drawn(state, c.id) or now()}
    missing: set[str] = set()
    value = _value(m, c, given, ctx, missing)
    if value is None:
        raise errors.ValidationError(f"missing inputs for {coordinate}: {sorted(missing)}", code="MISSING_INPUTS",
                                     hint="give them with --set coordinate=value in canonical units (plsi calc convert)")
    used = {cid: given[cid] for cid in c.derive.inputs if cid in given}  # type: ignore[union-attr]
    return {"map_id": m.id, "coordinate": c.id, "value": value, "unit": c.unit, "inputs": used,
            "overrides": sorted(overrides), "from_state": state.state_hash if state else None}
