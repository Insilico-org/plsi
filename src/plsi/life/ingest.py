"""`plsi ingest` and `plsi retract`. No network calls; writes only through EventStore."""

from __future__ import annotations

import contextlib
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from plsi import clock, extensions
from plsi.errors import NotFound, UsageError, ValidationError
from plsi.events import Event, NewEvent
from plsi.files import canonical_json, decode_input, load_json, parse_input_json, read_input_bytes, sha256_file, sha256_hex
from plsi.life import importers
from plsi.life.models import DOCUMENT_RE, Observation, ObservationInput, RetractionInput
from plsi.life.normalize import normalize_unit, shipped_coordinates
from plsi.life.store import EventStore, _retracted
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


def _conflicts(recorded: list[Event], fresh: list[tuple[int, Observation, str]]) -> list[dict[str, str | int]]:
    """New monthly means for a metric and month that already has a value (recorded or earlier in this input)."""
    codes = _monthly_codes()
    taken: dict[tuple[str, str], str] = {}
    for e in recorded:
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


def check_document(document: str) -> None:
    """Refuse a document id that is not a stable id (such as the Drive file id), never a file name."""
    if not re.match(DOCUMENT_RE, document):
        raise ValidationError(f"invalid document id: {document!r}", hint="a stable id such as the Drive file id; never a file name")


def dedupe_key(obs: ObservationInput) -> str:
    """sha256 hex of canonical_json({kind, code or lower(original_text), effective_at, value fields, normalized unit,
    specimen, fasting, clinical_status, effective_end}): the same value of the same test at the same time is one
    reading whatever file it came from (a re-exported report has a new hash); a real second reading sets `repeat`.
    Ingest recomputes it from stored payloads, so a change here applies to existing events too."""
    d = obs.model_dump(mode="json")
    return sha256_hex(canonical_json({
        "kind": d["kind"],
        "code": {"system": d["code"]["system"], "code": d["code"]["code"]} if obs.code else obs.original_text.lower(),
        **{k: d[k] for k in ("effective_at", "value_quantity", "value_text", "value_bool", "value_comparator", "specimen", "fasting")},
        "unit": normalize_unit(obs.unit),
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


def _plan(rows: list[tuple[int, Observation]], events: list[Event],
          ) -> tuple[list[tuple[int, Observation, str]], list[str | int], list[dict[str, Any]]]:
    """(fresh rows, duplicates, conflicts) against the log `events`, read once."""
    gone = _retracted(events)
    recorded = [e for e in events if e.type == EventType.OBSERVATION and e.id not in gone]
    seen: dict[str, str | int] = {dedupe_key(e.payload): e.id for e in recorded}  # keys recomputed from stored payloads
    fresh: list[tuple[int, Observation, str]] = []
    dupes: list[str | int] = []  # an event id, or a position in fresh (same-file repeat)
    for i, obs in rows:
        key = dedupe_key(obs)
        if not obs.repeat and key in seen:
            dupes.append(seen[key])
        else:
            seen.setdefault(key, len(fresh))
            fresh.append((i, obs, key))
    return fresh, dupes, _conflicts(recorded, fresh)  # conflicts are reported, never refused


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
    document: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate, normalize unit strings, assign ids and append observations (exactly one source; '-' = stdin).

    Returns {counts: {accepted, duplicate, rejected}, accepted: [event_id], duplicates: [event_id],
             rejected: [{index, error}], conflicts: [{index, with, coordinate, month}],
             warnings: ["UNCODED: <index>", "CONFLICT: <index>", "FUTURE: <index>", ...], dropped_columns?,
             subject_updated?}
    (dry_run writes nothing; accepted then holds indexes). document: stamped on every row's origin, so a later
    `plsi revise --document` can take the next version of the same source.
    """
    sources = {k: v for k, v in {"file": file, "fhir": fhir, "csv": csv, "methylation": methylation, "ext": ext}.items() if v is not None}
    if len(sources) != 1:
        raise UsageError("give exactly one of --file, --fhir, --csv, --methylation, --ext")
    if (ext is None) != (input is None):
        raise UsageError("--ext and --input go together")
    if document is not None:
        check_document(document)
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

    if document is not None:
        imported.rows = [(i, o.model_copy(update={"origin": o.origin.model_copy(update={"document": document})}))
                         for i, o in imported.rows]
    rows = [(i, to_observation(o)) for i, o in imported.rows]
    now = clock.now()
    warnings = list(imported.warnings) + [f"UNCODED: {i}" for i, o in rows if o.code is None]
    # a date without a time is stored at 12:00 UTC, so a value dated today stays out of the state until then
    warnings += [f"FUTURE: {i}" for i, o in rows if o.effective_at > now]

    if dry_run:
        fresh, dupes, conflicts = _plan(rows, store.events(active=False))
        ids: list[str] = [f"index {i}" for i, _, _ in fresh]
        accepted: list[Any] = [i for i, _, _ in fresh]
    else:  # the log is read once, under the lock that the append holds too, so a concurrent ingest cannot slip in
        with store.locked() as events:
            fresh, dupes, conflicts = _plan(rows, events)
            written = store.append_locked(events, [NewEvent(EventType.OBSERVATION, obs, dedupe_key=key, dedupe=not obs.repeat)
                                                   for _, obs, key in fresh]) if fresh else []
        ids = [event_id for event_id, _ in written]
        accepted = [event_id for event_id, created in written if created]
        dupes.sort(key=lambda d: isinstance(d, int))  # log duplicates first, then same-file repeats
        dupes += [event_id for event_id, created in written if not created]
    warnings += [f"CONFLICT: {c['index']}" for c in conflicts]
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


def retract(instance: str, file: str, event_id: str | None = None, events_file: str | None = None,
            replacement: str | None = None) -> dict[str, Any]:
    """Append a Retraction of `event_id`, or of every id in `events_file` (one per line; blank lines and # comments
    skipped), with the reason from RetractionInput in `file`. One read of the log and one append under one lock,
    however many ids: all are checked first, and one bad id writes nothing.

    replacement: ONE ObservationInput JSON (with --event only), appended first; its id goes into
    replacement_event_id. Retraction events cannot be retracted; a retracted target raises ALREADY_RETRACTED.
    Retracting a plan event makes Policy treat its unscored predictions as void. Events are never edited.
    """
    if (event_id is None) == (events_file is None):
        raise UsageError("give exactly one of --event, --events-file")
    if replacement is not None and events_file is not None:
        raise UsageError("--replacement goes with --event, not --events-file")
    reason = parse(RetractionInput, load_json(file), "retraction").reason
    if events_file is not None:
        text, _ = read_source(events_file)
        targets = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if not targets:
            raise UsageError(f"no event ids in {Path(events_file).name}")
    else:
        targets = [event_id]  # type: ignore[list-item]
    new = None
    if replacement is not None:
        obs = to_observation(parse(ObservationInput, load_json(replacement), "replacement observation"))
        new = (obs, dedupe_key(obs))
    done = EventStore(instance).retract(targets, reason, new)
    if events_file is None:
        return done[0]
    return {"count": len(done), "retracted": done}
