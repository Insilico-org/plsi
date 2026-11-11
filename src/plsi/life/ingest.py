"""`plsi ingest` and `plsi retract`. No network calls; writes only through EventStore."""

from __future__ import annotations

import contextlib
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from plsi import clock, extensions
from plsi.errors import NotFound, UsageError, ValidationError
from plsi.events import NewEvent
from plsi.files import canonical_json, decode_input, load_json, parse_input_json, read_input_bytes, sha256_file, sha256_hex
from plsi.life import importers
from plsi.life.models import Observation, ObservationInput, Retraction, RetractionInput
from plsi.life.normalize import normalize_unit, shipped_coordinates
from plsi.life.store import EventStore
from plsi.models import parse
from plsi.vocab import EventType, OriginKind

# A wearable or imported metric holds one mean per closed calendar month: the coordinates of MONTHLY_MAP whose label
# says MONTHLY_LABEL. A second value for the same metric and month is reported as a conflict, never refused.
MONTHLY_MAP = "sleep_activity"
MONTHLY_LABEL = "calendar-month mean"
MONTHLY_ORIGINS = (OriginKind.DEVICE, OriginKind.CSV, OriginKind.EXTENSION)  # the wearable import paths


def _monthly_codes() -> dict[tuple[str, str], str]:
    """(system, code) -> coordinate id of every code a calendar-month-mean coordinate accepts (not vo2_max)."""
    out = {(str(k["system"]), str(k["code"])): c["id"] for c in shipped_coordinates(MONTHLY_MAP)
           if MONTHLY_LABEL in c.get("label", "") for k in (c.get("accepts") or {}).get("codes") or []}
    if not out:  # the check keys on the label text: a relabelled map must not switch it off silently
        raise ValidationError(f"{MONTHLY_MAP}.yaml has no {MONTHLY_LABEL!r} coordinate", code="MAP_INVALID")
    return out


def _month(obs: ObservationInput, codes: dict[tuple[str, str], str]) -> tuple[str, str] | None:
    """(coordinate id, YYYY-MM) of a device or CSV-imported monthly mean, else None."""
    if obs.code is None or obs.origin.kind not in MONTHLY_ORIGINS:
        return None
    coordinate = codes.get((obs.code.system.value, obs.code.code))
    return (coordinate, obs.effective_at.strftime("%Y-%m")) if coordinate else None


def _conflicts(store: EventStore, fresh: list[tuple[int, Observation, str]]) -> list[dict[str, str | int]]:
    """New monthly means for a metric and month that already has a value (recorded or earlier in this input)."""
    codes = _monthly_codes()
    taken: dict[tuple[str, str], str] = {}
    for e in store.observations():
        if (k := _month(e.payload, codes)) is not None:
            taken.setdefault(k, e.id)
    out = []
    for i, obs, _ in fresh:
        if (k := _month(obs, codes)) is None:
            continue
        if k in taken:
            out.append({"index": i, "with": taken[k], "coordinate": k[0], "month": k[1]})
        else:
            taken[k] = f"index {i}"
    return out


def dedupe_key(obs: ObservationInput) -> str:
    """sha256 hex of canonical_json({kind, code or lower(original_text), effective_at, value fields, normalized unit,
    specimen, fasting, origin.file_sha256, origin.record_id, clinical_status, effective_end}); ingest recomputes it
    from stored payloads, so a change here applies to existing events too."""
    d = obs.model_dump(mode="json")
    return sha256_hex(canonical_json({
        "kind": d["kind"],
        "code": {"system": d["code"]["system"], "code": d["code"]["code"]} if obs.code else obs.original_text.lower(),
        **{k: d[k] for k in ("effective_at", "value_quantity", "value_text", "value_bool", "value_comparator", "specimen", "fasting")},
        "unit": normalize_unit(obs.unit),
        "file_sha256": obs.origin.file_sha256,
        "record_id": obs.origin.record_id,
        "clinical_status": d.get("clinical_status"),
        "effective_end": d.get("effective_end"),
    }))


def to_observation(obs: ObservationInput) -> Observation:
    """Stored form: unit_original as printed (`unit_printed` when a reading was chosen for it), unit UCUM-syntax-
    normalized; the value is never converted."""
    return Observation.model_validate({**{k: v for k, v in obs.dump().items() if k != "unit_printed"},
                                       "unit": normalize_unit(obs.unit), "unit_original": obs.unit_printed or obs.unit})


def read_source(path: str) -> tuple[str, str]:
    """(utf-8 text, sha256 hex of the raw bytes) of an input file ('-' = stdin)."""
    data = read_input_bytes(path)
    return decode_input(data), sha256_hex(data)


def _from_extension(ext_id: str, path: str) -> importers.Imported:
    """Run an importer extension; its items get origin {kind: extension, file_sha256} unless they set one."""
    data = read_input_bytes(path)
    items = extensions.importer(ext_id)(data)
    if not isinstance(items, list):
        raise ValidationError(f"importer {ext_id} must return a list of ObservationInput dicts")
    origin = {"kind": OriginKind.EXTENSION.value, "file_sha256": sha256_hex(data)}
    return importers.Imported.from_items([{**item, "origin": item.get("origin") or origin} if isinstance(item, dict) else item for item in items])


def ingest(
    instance: str,
    file: str | None = None,
    fhir: str | None = None,
    csv: str | None = None,
    methylation: str | None = None,
    ext: str | None = None,
    input: str | None = None,  # noqa: A002 - CLI dest name
    sample: str | None = None,
    effective_at: datetime | None = None,
    update: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate, normalize unit strings, assign ids and append observations (exactly one source; '-' = stdin).

    Returns {counts: {accepted, duplicate, rejected}, accepted: [event_id], duplicates: [event_id],
             rejected: [{index, error}], conflicts: [{index, with, coordinate, month}],
             warnings: ["UNCODED: <index>", "CONFLICT: <index>", "FUTURE: <index>", ...], dropped_columns?,
             subject_updated?}
    (dry_run writes nothing; accepted then holds indexes).
    """
    sources = {k: v for k, v in {"file": file, "fhir": fhir, "csv": csv, "methylation": methylation, "ext": ext}.items() if v is not None}
    if len(sources) != 1:
        raise UsageError("give exactly one of --file, --fhir, --csv, --methylation, --ext")
    if (ext is None) != (input is None):
        raise UsageError("--ext and --input go together")
    store = EventStore(instance)
    result: dict[str, Any] = {}
    if methylation is not None:
        path = Path(methylation)
        if not path.is_file():
            raise NotFound(f"input file not found: {path.name}", code="FILE_NOT_FOUND")
        # a dry run writes the artifact to a throwaway dir
        with tempfile.TemporaryDirectory() if dry_run else contextlib.nullcontext(store.dir) as target:
            imported = importers.from_methylation(path, Path(target), sample, sha256_file(path), effective_at)
    elif ext is not None:
        imported = _from_extension(ext, input)  # type: ignore[arg-type]
    else:
        text, sha = read_source(next(iter(sources.values())))
        if file is not None:
            imported = importers.from_json(text)
        elif fhir is not None:
            imported = importers.from_fhir(parse_input_json(text), sha)
        else:
            imported = importers.from_csv(text, sha)
            result["dropped_columns"] = imported.dropped_columns
    if imported.subject and not dry_run:
        _, changed = store.update_subject(**imported.subject, update=update)
        result["subject_updated"] = changed

    rows = [(i, to_observation(o)) for i, o in imported.rows]
    now = clock.now()
    warnings = list(imported.warnings) + [f"UNCODED: {i}" for i, o in rows if o.code is None]
    # a date without a time is stored at 12:00 UTC, so a value dated today stays out of the state until then
    warnings += [f"FUTURE: {i}" for i, o in rows if o.effective_at > now]
    seen: dict[str, str | int] = {dedupe_key(e.payload): e.id for e in store.observations()}  # keys recomputed from stored payloads
    fresh: list[tuple[int, Observation, str]] = []
    dupes: list[str | int] = []  # an event id, or a position in fresh (same-file repeat)
    for i, obs in rows:
        key = dedupe_key(obs)
        if not obs.repeat and key in seen:
            dupes.append(seen[key])
        else:
            seen.setdefault(key, len(fresh))
            fresh.append((i, obs, key))
    conflicts = _conflicts(store, fresh)  # reported, never refused
    warnings += [f"CONFLICT: {c['index']}" for c in conflicts]
    if dry_run:
        ids: list[str] = [f"index {i}" for i, _, _ in fresh]
        accepted: list[Any] = [i for i, _, _ in fresh]
    else:  # append_many dedupes again under the lock, against concurrent ingests
        written = store.append_many([NewEvent(EventType.OBSERVATION, obs, dedupe_key=key, dedupe=not obs.repeat) for _, obs, key in fresh]) if fresh else []
        ids = [event_id for event_id, _ in written]
        accepted = [event_id for event_id, created in written if created]
        dupes.sort(key=lambda d: isinstance(d, int))  # log duplicates first, then same-file and concurrent repeats
        dupes += [event_id for event_id, created in written if not created]
    duplicates = [ids[d] if isinstance(d, int) else d for d in dupes]
    return {
        "counts": {"accepted": len(accepted), "duplicate": len(duplicates), "rejected": len(imported.rejected)},
        "accepted": accepted,
        "duplicates": duplicates,
        "rejected": imported.rejected,
        "conflicts": conflicts,
        "warnings": warnings,
        "dry_run": dry_run,
        **result,
    }


def retract(instance: str, event_id: str, file: str, replacement: str | None = None) -> dict[str, Any]:
    """Append a Retraction of `event_id` (reason from RetractionInput in `file`).

    replacement: ONE ObservationInput JSON, appended first; its id goes into replacement_event_id.
    Retraction events cannot be retracted; a retracted target raises ALREADY_RETRACTED. Retracting a plan event
    makes Policy treat its unscored predictions as void. Events are never edited.
    """
    store = EventStore(instance)
    reason = parse(RetractionInput, load_json(file), "retraction").reason
    target = store.get(event_id)
    if target.type == EventType.RETRACTION:
        raise ValidationError("retraction events cannot be retracted", code="CANNOT_RETRACT_RETRACTION")
    if event_id in store.retracted_ids():
        raise ValidationError(f"event {event_id} is already retracted", code="ALREADY_RETRACTED")
    out: dict[str, Any] = {"target_event_id": event_id}
    payload: dict[str, Any] = {"target_event_id": event_id, "reason": reason}
    if replacement is not None:
        obs = to_observation(parse(ObservationInput, load_json(replacement), "replacement observation"))
        new_id, _ = store.append(EventType.OBSERVATION, obs, dedupe_key=dedupe_key(obs))  # never deduped: may equal the target
        out["replacement_event_id"] = payload["replacement_event_id"] = new_id
    out["retraction_event_id"], _ = store.append(EventType.RETRACTION, Retraction.model_validate(payload))
    return out
