"""Calculators for the bots (`plsi calc`): a value into a coordinate's canonical unit, and a derived coordinate
(clock, score, ratio) from given or what-if inputs. Pure: nothing is written. Bots never convert or compute by hand."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from plsi import errors
from plsi.clock import now
from plsi.files import load_json
from plsi.life.importers import observation_items
from plsi.map import derive, mapper, registry, units
from plsi.map.models import MapContract, MapCoordinate, StateDocument
from plsi.vocab import CoordinateKind, ObservationKind, ValueStatus

NO_CONVERSION_HINT = ("a different unit can mean a different measurement (RDW in fL is RDW-SD, not RDW-CV in %): "
                      "check the code with plsi normalize; never convert by hand")


def convert(map_id: str, coordinate: str, value: float, unit: str, instance: str | None = None) -> dict[str, Any]:
    """`plsi calc convert`: {value, unit, conversion} in the coordinate's canonical unit, or NO_CONVERSION."""
    c = registry.coordinate(registry.get(map_id, instance), coordinate)
    try:
        out, conversion = units.to_canonical(value, unit, c)
    except ValueError as exc:
        raise errors.ValidationError(str(exc), code="NO_CONVERSION", hint=NO_CONVERSION_HINT) from None
    return {"value": out, "unit": c.unit, "conversion": conversion}


def place(instance: str, file: str) -> dict[str, Any]:
    """`plsi calc place`: where each coded measurement of an observation file would land - the coordinate that reads
    its code, and its value in that coordinate's unit - so the result can be checked against the printed name
    before anything is recorded. Pure: nothing is written."""
    readers = {(k.system.value, k.code): (m, c) for m in registry.load_all(instance).values()
               for c in m.coordinates for k in c.accepts.codes}
    rows, problems = [], 0
    for i, item in enumerate(observation_items(load_json(file))):
        if not isinstance(item, dict) or item.get("kind") != ObservationKind.MEASUREMENT:
            continue
        code = item.get("code") or {}
        row: dict[str, Any] = {"index": i, "printed": item.get("original_text"), "value": item.get("value_quantity"),
                               "unit": item.get("unit"), "code": code.get("code"), "code_name": code.get("display")}
        found = readers.get((str(code.get("system")), str(code.get("code"))))
        if not code:
            row["problem"] = "no code"
        elif found is None:
            row["problem"] = "no map reads this code"
        else:
            m, c = found
            row |= {"lands_on": f"{m.id}.{c.id}", "lands_on_label": c.label, "canonical_unit": c.unit}
            if isinstance(row["value"], (int, float)):
                try:
                    row["canonical_value"] = units.to_canonical(float(row["value"]), row["unit"], c)[0]
                except ValueError as exc:
                    row["problem"] = f"unit: {exc}"
                    row["readings"] = units.readings(float(row["value"]), row["unit"], c)
        problems += "problem" in row
        rows.append(row)
    return {"rows": rows, "problems": problems,
            "check": "each row: the printed name and the code name are the same test, and lands_on is that test; "
                     "a unit problem with readings: the one the report supports (its printed range, the test's "
                     "usual values) goes in unit, the printed one in unit_printed"}


def _scalar(c: MapCoordinate) -> bool:
    return c.kind == CoordinateKind.DERIVED and c.derive is not None and derive.scalar(c.derive)


def _value(m: MapContract, c: MapCoordinate, given: dict[str, float], ctx: dict[str, Any], missing: set[str]) -> float | None:
    """c's value from `given`, recomputing its scalar derived inputs; None when an input is missing. Side effects:
    each recomputed input is written into `given` and each missing input id added to `missing`."""
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


def _drawn(state: StateDocument | None, coordinate: str) -> datetime | None:
    v = state.coordinates.get(coordinate) if state else None
    return v.observed_at if v and v.status == ValueStatus.PRESENT else None


def _number(raw: Any, message: str) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise errors.UsageError(message) from None


def compute(map_id: str, coordinate: str, instance: str | None = None, inputs: str | None = None,
            set_values: list[str] | None = None, birth_year: int | None = None, sex: str | None = None,
            at: datetime | None = None) -> dict[str, Any]:
    """`plsi calc derive`: a derived coordinate from the instance's published measured values (if --instance),
    overridden by --inputs {coordinate: value} and --set coordinate=value (canonical units). Derived inputs are always
    recomputed. Birth year and sex default to the instance's subject; --at (age) to the published value's draw date,
    else now. Pass --at for a value at a prediction horizon."""
    m = registry.get(map_id, instance)
    c = registry.coordinate(m, coordinate)
    if not _scalar(c):
        raise errors.ValidationError(f"{coordinate} is not a scalar derived coordinate", hint=f"plsi maps show {map_id}")
    given: dict[str, float] = {}
    state = mapper.latest_state(instance, m.id) if instance else None
    if state:
        given = {cid: v.value for cid, v in state.coordinates.items() if v.status == ValueStatus.PRESENT
                 and isinstance(v.value, float) and not _scalar(registry.coordinate(m, cid))}
    overrides = load_json(inputs) if inputs else {}
    if not isinstance(overrides, dict):
        raise errors.UsageError("--inputs expects a JSON object {coordinate: value}")
    for item in set_values or []:
        key, _, raw = item.partition("=")
        overrides[key.strip()] = _number(raw, f"--set expects coordinate=number, got {item!r}")
    for key in overrides:
        registry.coordinate(m, key)
    given |= {k: _number(v, f"--inputs {k}: expected a number, got {v!r}") for k, v in overrides.items()}
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
