"""Dashboard: typed blocks -> ONE self-contained HTML file.

The template is plsi/report.html (package data) with a single payload placeholder inside <script type="application/json">.
Payload serialized with files.canonical_json, then <, >, &, U+2028, U+2029 escaped as \\uXXXX. CSP meta
`default-src 'none'; script-src 'sha256-<hash>'; style-src 'unsafe-inline'; img-src data:` with the hash computed
at render. The JS uses only createElement/textContent; href only for http(s) with rel=noopener noreferrer.
"""

from __future__ import annotations

import base64
import hashlib
import re
from datetime import date, datetime, timedelta
from importlib import resources
from typing import Any, Literal

from plsi.clock import now, ts_filename
from plsi.errors import NotFound, warn
from plsi.files import atomic_write_bytes, atomic_write_text, canonical_json, load_json
from plsi.life.store import EventStore
from plsi.map import mapper, registry
from plsi.map.models import MapContract, StateDocument
from plsi.models import Model, UtcTime, parse
from plsi.paths import instance_dir, safe_join, validate_id
from plsi.policy.fold import plans
from plsi.policy.plan import list_plans
from plsi.policy.score import calibration
from plsi.vocab import BlockType, MatchKind, PlanState, PredictionTarget, ReportFormat, ScoreStatus, ValueStatus


class Block(Model):
    """type: a BlockType, or any other string (rendered as pretty-printed JSON). data shapes:
    markdown {text} (#, **, *, - lists, [t](https://...) only; never raw HTML) · kv {items:[{key,value}]} ·
    table {columns, rows} (cell = string | number | {text, href?}) ·
    timeseries {series:[{name, unit, points:[{t,v}], predictions:[{t,expected,low,high}]}]} · list {items:[{text, href?}]} ·
    timeline {now?, events:[{t, label, kind: past|predicted, level?: info|watch|high, t_end?, probability?, detail?, href?}]}"""

    type: BlockType | str
    title: str | None = None
    data: dict[str, Any]


class DashboardPayload(Model):
    kind: Literal["plsi_dashboard"] = "plsi_dashboard"
    schema_version: Literal[1] = 1
    title: str
    subject_id: str
    generated_at: UtcTime
    blocks: list[Block] = []

PAYLOAD_PLACEHOLDER = "__PLSI_PAYLOAD__"
HASH_PLACEHOLDER = "__PLSI_SCRIPT_HASH__"
_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)
_ESCAPES = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", "\u2028": "\\u2028", "\u2029": "\\u2029"}
_HIDDEN_PLAN_STATES = {PlanState.STOPPED, PlanState.SUPERSEDED}


# ---------------------------------------------------------------- render

def _template() -> str:
    return resources.files("plsi").joinpath("report.html").read_text(encoding="utf-8")


def script_hash(script: str) -> str:
    """CSP source expression for an inline script."""
    return "sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")


def embed_json(obj: Any) -> str:
    """canonical_json safe to place inside <script type="application/json">."""
    return re.sub("[<>&\u2028\u2029]", lambda m: _ESCAPES[m.group()], canonical_json(obj))


def render(payload: DashboardPayload) -> str:
    """Pure: payload -> complete HTML document string."""
    template = _template()
    script = _SCRIPT_RE.search(template)
    head, sep, tail = template.partition(PAYLOAD_PLACEHOLDER)
    if script is None or not sep or PAYLOAD_PLACEHOLDER in tail or head.count(HASH_PLACEHOLDER) != 1:
        raise RuntimeError("report.html must hold one inline script, one payload and one hash placeholder")
    head = head.replace(HASH_PLACEHOLDER, script_hash(script.group(1)))
    return head + embed_json(payload.dump()) + tail


# ---------------------------------------------------------------- payload

def _iso(value: datetime | date) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _cell(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return _iso(value)
    if value is None or isinstance(value, (str, int, float)):
        return "" if value is None else value
    return canonical_json(value)


def _num(value: float, unit: str | None) -> str:
    return f"{round(value, 2):g}" + (f" {unit}" if unit else "")


def _states(instance: str, map_id: str | None) -> list[StateDocument]:
    if map_id is None:
        states = mapper.latest_states(instance)
    elif (state := mapper.latest_state(instance, validate_id(map_id, "map id"))) is None:
        raise NotFound(f"no projection for map {map_id!r}", code="STATE_NOT_FOUND",
                       hint=f"plsi project --instance {instance} --map {map_id}")
    else:
        states = [state]
    for s in states:
        if not s.verify_hash():
            warn("STATE_HASH_MISMATCH", f"states/{s.map_id}/latest.json does not match its state_hash; re-project")
    return states


def _labels(instance: str, state: StateDocument) -> tuple[str, dict[str, str]]:
    """Map title and coordinate labels from the write-once map snapshot, when present."""
    snap = registry.snapshot_path(instance, state.map_id, state.map_hash)
    if not snap.is_file():
        return state.map_id, {}
    m = parse(MapContract, load_json(snap))
    return m.title, {c.id: c.label for c in m.coordinates}


def _predictions(instance: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """map_id -> coordinate -> [{t, expected, low, high}] (level scale) for live plans; void predictions excluded."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for v in plans(instance).values():
        if v.state in _HIDDEN_PLAN_STATES:
            continue
        plan, horizons = v.plan, (v.adoption.horizons if v.adoption else None) or {}
        for p in plan.predictions:
            offset = 0.0
            if p.target == PredictionTarget.CHANGE_FROM_BASELINE:
                base = p.baseline.value if p.baseline else None
                if not isinstance(base, (int, float)):
                    continue  # a change without a numeric baseline has no level to plot
                offset = float(base)
            if p.id in v.scores and v.scores[p.id].status == ScoreStatus.VOID:
                continue
            t = horizons.get(p.id) or (p.state_ref.as_of + timedelta(days=p.horizon_days)).date()
            out.setdefault(p.map_id, {}).setdefault(p.coordinate, []).append(
                {"t": _iso(t), "expected": p.expected + offset, "low": p.low + offset, "high": p.high + offset})
    return out


def _state_blocks(instance: str, state: StateDocument, predictions: dict[str, list[dict[str, Any]]]) -> list[Block]:
    title, labels = _labels(instance, state)
    items, series = [], []
    for cid, cv in state.coordinates.items():
        label = labels.get(cid, cid)
        if isinstance(cv.value, list):
            items.append({"key": label, "value": "; ".join(i.text for i in cv.value) or "none"})
            continue
        if cv.provenance is not None and cv.provenance.match == MatchKind.DERIVED:
            shown = _num(cv.value, cv.unit) if cv.value is not None else "—"
            items.append({"key": label, "value": shown + ("" if cv.status == ValueStatus.PRESENT else f" ({cv.status})")})
        points = [{"t": _iso(p.t), "v": p.value} for p in cv.series]
        if not points and isinstance(cv.value, (int, float)) and cv.observed_at:
            points = [{"t": _iso(cv.observed_at), "v": cv.value}]
        if points or predictions.get(cid):
            series.append({"name": label, "unit": cv.unit or "", "points": points, "predictions": predictions.get(cid, [])})
    as_of = f"as of {state.as_of.date().isoformat()}"
    blocks = []
    if items:
        blocks.append(Block(type=BlockType.KV, title=f"{title}: {as_of}", data={"items": items}))
    if series:
        blocks.append(Block(type=BlockType.TIMESERIES, title=f"{title}: observed and predicted", data={"series": series}))
    if state.gaps:
        rows = [[labels.get(g.coordinate, g.coordinate), g.reason, g.suggestion] for g in state.gaps]
        blocks.append(Block(type=BlockType.TABLE, title=f"{title}: gaps",
                            data={"columns": ["coordinate", "reason", "suggestion"], "rows": rows}))
    return blocks


def _policy_blocks(instance: str) -> list[Block]:
    blocks = []
    if listed := list_plans(instance):
        keys = ["plan_id", "objective", "maps", "state", "created_at", "review_at", "predictions"]
        rows = [[_cell(p.get(k)) for k in keys] for p in listed]
        blocks.append(Block(type=BlockType.TABLE, title="Plans", data={"columns": keys, "rows": rows}))
    cal = calibration(instance)
    if cal["overall"]["n_scored"] or cal["overall"]["n_missed"]:  # nothing scored or missed yet: no table
        scopes = [("overall", cal["overall"]), *cal["by_coordinate"].items()]
        columns = list(cal["overall"])
        rows = [[scope, *(_cell(row[c]) for c in columns)] for scope, row in scopes]
        blocks.append(Block(type=BlockType.TABLE, title="Prediction scores and calibration",
                            data={"columns": ["scope", *columns], "rows": rows}))
    return blocks


def default_payload(instance: str, map_id: str | None = None) -> DashboardPayload:
    """Blocks built from the instance: states (latest.json per map, or only map_id), timeseries with predictions,
    plans, scores and calibration. Unknown sources are skipped, never invented."""
    store = EventStore(instance)
    states = _states(instance, map_id)
    predictions = _predictions(instance)
    blocks = [b for s in states for b in _state_blocks(instance, s, predictions.get(s.map_id, {}))]
    if not states:
        blocks.append(Block(type=BlockType.MARKDOWN, title="No state yet",
                            data={"text": f"Nothing projected yet. Run **plsi project --instance {instance} --map <id>**."}))
    blocks += _policy_blocks(instance)
    return DashboardPayload(title=f"PLSI report: {instance}", subject_id=store.subject.subject_id, generated_at=now(), blocks=blocks)


def report(instance: str, map_id: str | None = None, payload: str | None = None, fmt: str = "html") -> dict[str, Any]:
    """`plsi report --instance N [--map ID] [--payload F] [--format html|pdf]`: payload file (DashboardPayload JSON,
    '-' = stdin) or default_payload (the CLI makes --payload and --map exclusive); write <instance>/reports/<ts>.html
    (or .pdf, a static copy for e-mail) only. Returns {path: absolute, uri: file:// URI, blocks: n}."""
    inst = instance_dir(instance)
    doc = parse(DashboardPayload, load_json(payload)) if payload is not None else default_payload(instance, map_id)
    fmt = ReportFormat(fmt)
    path = safe_join(inst, "reports", f"{ts_filename()}.{fmt.value}")
    if fmt == ReportFormat.PDF:
        from plsi.report_pdf import render_pdf
        atomic_write_bytes(path, render_pdf(doc))
    else:
        atomic_write_text(path, render(doc))
    return {"path": str(path), "uri": path.as_uri(), "blocks": len(doc.blocks)}
