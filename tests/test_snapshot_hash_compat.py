"""Snapshot integrity stays on the persisted JSON, not on fields a newer model fills in."""

from __future__ import annotations

import json

import pytest

from plsi.errors import NotFound, ValidationError
from plsi.files import hash_json
from plsi.map import registry
from plsi.map.models import MapContract
from plsi.models import parse

INSTANCE = "synth-snap"
MAP_ID = "user_synth_map"


def _body(*, offset: float | None, window_days: int | None, factor: float = 2.0, full: bool = False) -> dict:
    conversion = {"from_unit": "mmol/L", "factor": factor, "source": {"kind": "rule", "id": "synth-rule"}}
    if offset is not None:
        conversion["offset"] = offset
    derive = {"engine": "expr", "model": "synth-score", "inputs": ["marker_b"], "formula": "marker_b"}
    if window_days is not None:
        derive["window_days"] = window_days
    doc = {
        "kind": "plsi_map",
        "schema_version": 1,
        "id": MAP_ID,
        "title": "Synthetic map",
        "map_version": "0.0.1",
        "claim_level": "designed",
        "summary": "Synthetic snapshot for hash compatibility.",
        "coordinates": [
            {
                "id": "marker_a",
                "label": "Marker A",
                "kind": "measured",
                "unit": "mg/dL",
                "conversions": [conversion],
                "derive": derive,
                "correspondence_type": "unmapped",
            },
            {
                "id": "marker_b",
                "label": "Marker B",
                "kind": "measured",
                "unit": "mg/dL",
                "correspondence_type": "unmapped",
            },
        ],
        "inference_boundaries": {"min_evidence_class_for_actions": "unknown"},
    }
    return parse(MapContract, doc).dump() if full else doc


def _install(tmp_path, monkeypatch, doc: dict, expected: str | None = None) -> str:
    monkeypatch.setenv("PLSI_HOME", str(tmp_path))
    home = tmp_path / INSTANCE
    home.mkdir(parents=True, exist_ok=True)
    (home / "subject.json").write_text("{}\n", encoding="utf-8")
    digest = expected if expected is not None else hash_json(doc)
    path = registry.snapshot_path(INSTANCE, MAP_ID, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return digest


def test_legacy_missing_fields_accepted(tmp_path, monkeypatch):
    doc = _body(offset=None, window_days=None)
    digest = _install(tmp_path, monkeypatch, doc)
    loaded = registry.load_snapshot(INSTANCE, MAP_ID, digest)
    assert loaded.coordinates[0].conversions[0].offset == 0.0
    assert loaded.coordinates[0].derive is not None
    assert loaded.coordinates[0].derive.window_days == 0
    assert "offset" not in doc["coordinates"][0]["conversions"][0]
    assert "window_days" not in doc["coordinates"][0]["derive"]


def test_current_zero_defaults_accepted(tmp_path, monkeypatch):
    doc = _body(offset=0.0, window_days=0, full=True)
    digest = _install(tmp_path, monkeypatch, doc)
    loaded = registry.load_snapshot(INSTANCE, MAP_ID, digest)
    assert loaded.compute_hash() == digest
    assert loaded.coordinates[0].conversions[0].offset == 0.0
    assert loaded.coordinates[0].derive is not None
    assert loaded.coordinates[0].derive.window_days == 0


def test_current_nonzero_fields_accepted(tmp_path, monkeypatch):
    doc = _body(offset=1.5, window_days=7, full=True)
    digest = _install(tmp_path, monkeypatch, doc)
    loaded = registry.load_snapshot(INSTANCE, MAP_ID, digest)
    assert loaded.compute_hash() == digest
    assert loaded.coordinates[0].conversions[0].offset == 1.5
    assert loaded.coordinates[0].derive is not None
    assert loaded.coordinates[0].derive.window_days == 7


def test_tampered_factor_rejected(tmp_path, monkeypatch):
    digest = _install(tmp_path, monkeypatch, _body(offset=0.0, window_days=0))
    tampered = _body(offset=0.0, window_days=0, factor=9.0)
    path = registry.snapshot_path(INSTANCE, MAP_ID, digest)
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        registry.load_snapshot(INSTANCE, MAP_ID, digest)
    assert exc.value.code == "SNAPSHOT_CORRUPT"


def test_injected_defaults_change_stored_hash(tmp_path, monkeypatch):
    legacy = _body(offset=None, window_days=None)
    digest = _install(tmp_path, monkeypatch, legacy)
    injected = _body(offset=0.0, window_days=0)
    path = registry.snapshot_path(INSTANCE, MAP_ID, digest)
    path.write_text(json.dumps(injected), encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        registry.load_snapshot(INSTANCE, MAP_ID, digest)
    assert exc.value.code == "SNAPSHOT_CORRUPT"
    assert parse(MapContract, injected).compute_hash() != digest


def test_missing_file_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PLSI_HOME", str(tmp_path))
    home = tmp_path / INSTANCE
    home.mkdir()
    (home / "subject.json").write_text("{}\n", encoding="utf-8")
    digest = hash_json(_body(offset=None, window_days=None))
    with pytest.raises(NotFound) as exc:
        registry.load_snapshot(INSTANCE, MAP_ID, digest)
    assert exc.value.code == "SNAPSHOT_NOT_FOUND"


def test_invalid_json_handled(tmp_path, monkeypatch):
    digest = _install(tmp_path, monkeypatch, _body(offset=None, window_days=None))
    path = registry.snapshot_path(INSTANCE, MAP_ID, digest)
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValidationError) as exc:
        registry.load_snapshot(INSTANCE, MAP_ID, digest)
    assert exc.value.code == "SNAPSHOT_CORRUPT"
