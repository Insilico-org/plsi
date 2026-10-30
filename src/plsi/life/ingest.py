"""`plsi ingest` and `plsi retract`.

No network calls. Writes only through plsi.life.store.EventStore (never edits events.jsonl).
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from plsi.events import NewEvent
from plsi.life.models import Observation, ObservationInput, Retraction, RetractionInput
from plsi.models import parse
from plsi.life import importers
from plsi.life.normalize import normalize_unit
from plsi.life.store import EventStore
from plsi.errors import NotFound, UsageError, ValidationError
from plsi.files import canonical_json, decode_input, load_json, parse_input_json, read_input_bytes, sha256_hex
from plsi.vocab import EventType, OriginKind


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
    """Stored form: unit_original as reported, unit UCUM-syntax-normalized; the value is never converted."""
    return Observation.model_validate({**obs.dump(), "unit": normalize_unit(obs.unit), "unit_original": obs.unit})


def _read(path: str) -> tuple[str, str]:
    """(utf-8 text, sha256 hex of the raw bytes)."""
    data = read_input_bytes(path)
    return decode_input(data), sha256_hex(data)


def _from_json_list(text: str) -> importers.Imported:
    return importers.Imported.from_items(importers.observation_items(parse_input_json(text)))


def _from_extension(ext_id: str, path: str) -> importers.Imported:
    """Run an importer extension; its items get origin {kind: extension, file_sha256} unless they set one."""
    from plsi import extensions

    data = read_input_bytes(path)
    items = extensions.importer(ext_id)(data)
    if not isinstance(items, list):
        raise ValidationError(f"importer {ext_id} must return a list of ObservationInput dicts")
    origin = {"kind": OriginKind.EXTENSION.value, "file_sha256": sha256_hex(data)}
    return importers.Imported.from_items([{**item, "origin": item.get("origin") or origin} if isinstance(item, dict) else item for item in items])


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


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
             rejected: [{index, error}], warnings: ["UNCODED: <index>", ...], dropped_columns?, subject_updated?}
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
        with tempfile.TemporaryDirectory() as scratch:  # dry run: the artifact is written to a throwaway dir
            imported = importers.from_methylation(path, Path(scratch) if dry_run else store.dir, sample, _file_sha256(path), effective_at)
    elif ext is not None:
        imported = _from_extension(ext, input)  # type: ignore[arg-type]
    else:
        text, sha = _read(next(iter(sources.values())))
        if file is not None:
            imported = _from_json_list(text)
        elif fhir is not None:
            imported = importers.from_fhir(parse_input_json(text), sha)
        else:
            imported = importers.from_csv(text, sha)
            result["dropped_columns"] = imported.dropped_columns
    if imported.subject and not dry_run:
        _, changed = store.update_subject(**imported.subject, update=update)
        result["subject_updated"] = changed

    observations = [to_observation(o) for o in imported.observations]
    keys = [dedupe_key(o) for o in observations]
    indexes = imported.indexes
    warnings = list(imported.warnings) + [f"UNCODED: {i}" for i, o in zip(indexes, observations, strict=True) if o.code is None]
    seen: dict[str, str | int] = {dedupe_key(e.payload): e.id for e in store.observations()}  # keys recomputed from stored payloads
    fresh: list[tuple[int, Observation, str]] = []
    dupes: list[str | int] = []  # an event id, or a position in fresh (same-file repeat)
    for i, obs, key in zip(indexes, observations, keys, strict=True):
        if not obs.repeat and key in seen:
            dupes.append(seen[key])
        else:
            seen.setdefault(key, len(fresh))
            fresh.append((i, obs, key))
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
