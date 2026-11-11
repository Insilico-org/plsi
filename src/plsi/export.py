"""`plsi export`: everything one instance holds, as the bots exchange it - the deidentified subject, active
observations, the published state documents, screenings, plans with their status, prediction scores and calibration -
as one JSON bundle or as CSV tables. Writes only under the output folder; the log is never touched. `plsi status`:
the instance overview."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from plsi import files, paths
from plsi.clock import now, ts_filename
from plsi.errors import PlsiError
from plsi.life.store import EventStore, event_counts
from plsi.map import mapper
from plsi.policy.fold import plans
from plsi.policy.plan import list_plans
from plsi.policy.score import calibration
from plsi.vocab import EventType, ExportFormat


def _events(store: EventStore, t: EventType) -> list[dict[str, Any]]:
    return [{"event_id": e.id, "recorded_at": e.recorded_at.isoformat(), **e.payload.dump()} for e in store.events(t)]


def status(instance: str) -> dict[str, Any]:
    """`plsi status`: subject, event counts, stored states (hash-checked) and plans."""
    store = EventStore(instance)
    states = []
    for latest in sorted((store.dir / "states").glob("*/latest.json")):
        try:
            doc = mapper.latest_state(instance, latest.parent.name)
            states.append({"map_id": doc.map_id, "as_of": doc.as_of, "generated_at": doc.generated_at,
                           "state_hash": doc.state_hash, "hash_ok": doc.verify_hash()})
        except PlsiError:
            states.append({"map_id": latest.parent.name, "error": "unreadable latest.json"})
    return {"instance": instance, "path": str(store.dir), "subject": store.subject.dump(), "events": event_counts(instance),
            "states": states, "user_maps": sorted(p.stem for p in (store.dir / "maps" / "user").glob("*.yaml")),
            "plans": list_plans(instance)}


def _bundle(instance: str) -> dict[str, Any]:
    """The export document (kind plsi_export)."""
    store = EventStore(instance)
    states = [s.dump() for s in mapper.latest_states(instance)]
    plan_docs = [{**v.plan.dump(), "state": v.state.value, "statuses": [s.dump() for s in v.statuses]}
                 for v in plans(instance).values()]
    return {"kind": "plsi_export", "schema_version": 1, "exported_at": now().isoformat(), "instance": instance,
            "subject": store.subject.dump(), "observations": _events(store, EventType.OBSERVATION), "states": states,
            "screenings": _events(store, EventType.SCREENING), "plans": plan_docs,
            "scores": _events(store, EventType.PREDICTION_SCORE), "calibration": calibration(instance)}


def _flat(row: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Nested dicts -> dotted columns; lists -> JSON text."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            out |= _flat(value, f"{name}.")
        else:
            out[name] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
    return out


def _cell(value: Any) -> Any:
    """A text cell a spreadsheet would run as a formula (= + - @ after whitespace) gets a leading quote."""
    return f"'{value}" if isinstance(value, str) and value.lstrip()[:1] in ("=", "+", "-", "@") else value


def _csv(rows: list[dict[str, Any]]) -> str:
    flat = [{k: _cell(v) for k, v in _flat(r).items()} for r in rows]
    columns = list(dict.fromkeys(k for r in flat for k in r))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(flat)
    return buf.getvalue()


def _tables(doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """The bundle as tables: one row per observation, state coordinate, gap, plan, prediction, screening, score."""
    coords = [{"map_id": s["map_id"], "state_hash": s["state_hash"], "as_of": s["as_of"], "coordinate": cid, **v}
              for s in doc["states"] for cid, v in s["coordinates"].items()]
    gaps = [{"map_id": s["map_id"], **g} for s in doc["states"] for g in s.get("gaps", [])]
    predictions = [{"plan_id": p["id"], **pred} for p in doc["plans"] for pred in p.get("predictions", [])]
    plan_rows = [{k: v for k, v in p.items() if k != "predictions"} for p in doc["plans"]]
    return {"subject": [doc["subject"]], "observations": doc["observations"], "coordinates": coords, "gaps": gaps,
            "plans": plan_rows, "predictions": predictions, "screenings": doc["screenings"], "scores": doc["scores"]}


def export(instance: str, fmt: str = "json", out: str | None = None) -> dict[str, Any]:
    """`plsi export --instance N [--format json|csv] [--out DIR]`: default DIR <instance>/exports/<timestamp>/.
    Every file is owner-only: it holds health data."""
    doc = _bundle(instance)
    folder = Path(out) if out else paths.instance_dir(instance) / "exports" / ts_filename()
    folder.mkdir(parents=True, exist_ok=True)
    rows_by_table = _tables(doc)
    if ExportFormat(fmt) == ExportFormat.JSON:
        written = [folder / f"{instance}.json"]
        files.atomic_write_json(written[0], doc, private=True)
    else:
        written = [folder / f"{name}.csv" for name in rows_by_table]
        for path, rows in zip(written, rows_by_table.values()):
            files.atomic_write_text(path, _csv(rows), private=True)
    counts = {k: len(v) for k, v in rows_by_table.items()}
    return {"instance": instance, "format": fmt, "files": [str(p) for p in written], "counts": counts}
