"""The physician's clinic dashboard: one HTML file, a tab for the whole panel and one per active or paused patient."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from plsi.clinic import roster
from plsi.clinic.patient import Patient, day, gather, med_status, name, outside, ref_range, series, value
from plsi.clock import now
from plsi.errors import warn
from plsi.files import atomic_write_text
from plsi.life.models import Observation
from plsi.map import bioage, units
from plsi.paths import plsi_home
from plsi.report import Block, DashboardPayload, Tab, kv, render, table
from plsi.vocab import (CLOSED_PLAN_STATES, AlertLevel, BlockIcon, BlockType, DueState, MeasureGroup, ObservationKind,
                        RosterStatus, SyncStatus)

RELOAD_SECONDS = 300
RECENT_DAYS = 30
MAX_CHARTS = 24
MAX_EVENTS = 80
PANEL_TAB = "Panel"  # upper case: never an instance id
SHOWN = (RosterStatus.ACTIVE.value, RosterStatus.PAUSED.value)
RESULT_COLUMNS = ["Test", "Latest", "Unit", "Date", "Report range", "Lab flag", "Previous", "Change", "Results"]
ITEM_COLUMNS = ["Kind", "Item", "Detail", "Status", "Date"]
NOTE = ("For the physician only. Values are as recorded, each result compared with the range printed on its own "
        "report; a summary of records, not a diagnosis.")


def path() -> Path:
    return plsi_home() / "work" / "clinic-dashboard" / "dashboard.html"


def _mark(text: Any, level: AlertLevel) -> dict[str, Any]:
    return {"text": str(text), "level": level.value}


def _in_range(labs: list[list[Observation]]) -> tuple[int, int, int]:
    """Latest result of each test: (inside its report's range, outside it, no range printed)."""
    ranged = [s[-1] for s in labs if s[-1].ref_low is not None or s[-1].ref_high is not None or s[-1].flag]
    out = sum(outside(o) for o in ranged)
    return len(ranged) - out, out, len(labs) - len(ranged)


def _event(t: Any, label: str, level: AlertLevel = AlertLevel.INFO, detail: str = "", kind: str = "past") -> dict[str, Any]:
    return {"t": day(t), "label": label, "kind": kind, "level": level.value, "detail": detail}


def _result_row(s: list[Observation]) -> list[Any]:
    last, prev = s[-1], s[-2] if len(s) > 1 else None
    change = ""
    if prev and last.value_quantity is not None and prev.value_quantity is not None:
        change = f"{last.value_quantity - prev.value_quantity:+.4g}"
    shown = _mark(value(last), AlertLevel.HIGH) if outside(last) else value(last)
    return [name(last), shown, units.display(last.unit), day(last.effective_at), ref_range(last), last.flag.value if last.flag else "",
            f"{value(prev)} ({day(prev.effective_at)})" if prev else "", change, len(s)]


def _trend(s: list[Observation]) -> dict[str, Any]:
    points = [{"t": day(o.effective_at), "v": o.value_quantity, "ref_low": o.ref_low, "ref_high": o.ref_high,
               "flag": o.flag.value if o.flag else None} for o in s if o.value_quantity is not None]
    return {"name": name(s[-1]), "unit": units.display(s[-1].unit),
            "points": [{k: v for k, v in pt.items() if v is not None} for pt in points]}


def _items(obs: list[Observation], kinds: dict[str, str]) -> list[list[Any]]:
    rows = []
    for o in sorted(obs, key=lambda o: o.effective_at, reverse=True):
        detail = "" if o.value_bool is True or value(o) == o.original_text else value(o)
        rows.append([kinds[o.kind.value], o.original_text, detail + (f" {units.display(o.unit)}" if o.unit and detail else ""),
                     o.clinical_status.value if o.clinical_status else "", day(o.effective_at)])
    return rows


def _bioage(label: str) -> list[Block]:
    """Blood PhenoAge: the age, the ages on one line, what each marker does to it and its course over draws."""
    view = bioage.phenoage_view(label)
    if view is None:
        return []
    title = "Biological age"
    if "missing" in view:
        return [Block(type=BlockType.MARKDOWN, title=title, icon=BlockIcon.AGE, data={
            "text": f"PhenoAge needs these markers, drawn within 30 days of each other: {', '.join(view['missing'])}."})]
    gap, what_if = view["gap"], view["what_if"]
    items = [{"key": "PhenoAge", "value": f"{view['phenoage']:.1f}", "unit": "years", "hero": True},
             {"key": "Calendar age at the draw", "value": f"{view['age']:.1f} years"},
             {"key": "Difference", "value": f"{abs(gap):.1f} years {'younger' if gap < 0 else 'older'}"},
             {"key": "Blood drawn", "value": day(view["drawn"]) if day(view["drawn_from"]) == day(view["drawn"])
              else f"{day(view['drawn_from'])} to {day(view['drawn'])}"}]
    marks = [{"label": "calendar age", "value": view["age"], "tone": AlertLevel.NEUTRAL.value},
             {"label": "PhenoAge", "value": view["phenoage"], "tone": AlertLevel.INFO.value}]
    if what_if is not None:
        items.append({"key": "If the markers outside their range sat at its edge", "value": f"{what_if:.1f} years"})
        marks.append({"label": "what-if", "value": what_if})
    ranged = sorted((m for m in view["markers"] if m["years"] is not None), key=lambda m: -m["years"])
    blocks = [Block(type=BlockType.KV, title=title, icon=BlockIcon.AGE, data={"items": items}),
              Block(type=BlockType.SCALE, title="The ages on one line", icon=BlockIcon.AGE,
                    data={"unit": "years", "marks": marks})]
    if ranged:
        blocks.append(Block(type=BlockType.BARS, title="What each marker does to PhenoAge", icon=BlockIcon.LAB, data={
            "unit": "years", "items": [{"label": m["label"], "value": round(m["years"], 2), "note": (
                f"{m['value']:g} {units.display(m['unit'])}, range {m['low']:g}–{m['high']:g}")} for m in ranged]}))
    if len(view["gap_series"]) > 1:
        blocks.append(Block(type=BlockType.TIMESERIES, title="PhenoAge over time", icon=BlockIcon.TREND, data={
            "series": [{"name": "PhenoAge minus calendar age", "unit": "years",
                        "points": [{"t": day(pt["t"]), "v": round(pt["v"], 2)} for pt in view["gap_series"]]}]}))
    unranged = [m["label"] for m in view["markers"] if m["years"] is None]
    text = ("PhenoAge (Levine 2018) is calculated from nine markers drawn within 30 days and the age at the newest "
            "draw. Each bar "
            "is the change in PhenoAge if that one marker sat at the middle of the range printed on its report.")
    if unranged:
        text += f" No range was printed for: {', '.join(unranged)}."
    if "breakdown" in view:
        text += (" The per-marker bars are left out: a marker has a newer result than this age used, or a result "
                 "printed as below or above a limit.")
    if what_if is not None:
        text += (f" The what-if moves only {', '.join(view['moved'])} to the edge of the printed range: a calculation, "
                 "not a target or a prediction.")
    blocks.append(Block(type=BlockType.MARKDOWN, icon=BlockIcon.NOTE, data={"text": text}))
    return blocks


def _visits(p: Patient) -> list[dict[str, Any]]:
    """Each date results were taken, notes, procedures, files in, reports out, reviews and plan dates."""
    events = []
    for group, what in ((MeasureGroup.LAB, "Blood and lab tests"), (MeasureGroup.BODY, "Body and vitals")):
        by_day: dict[str, list[Observation]] = defaultdict(list)
        for o in p.groups.get(group.value, []):
            by_day[day(o.effective_at)].append(o)
        for d, items in by_day.items():
            out = sorted({name(o) for o in items if outside(o)})
            events.append(_event(d, f"{what}: {len(items)} result(s)", AlertLevel.WATCH if out else AlertLevel.INFO,
                                 f"outside range: {', '.join(out[:6])}" if out else ""))
    for kind, what in ((ObservationKind.NOTE, "Note"), (ObservationKind.INTERVENTION, "Procedure or treatment")):
        events += [_event(o.effective_at, f"{what}: {o.original_text[:60]}", detail=o.value_text or "")
                   for o in p.groups.get(kind.value, [])]
    what = {SyncStatus.NEW: "File received", SyncStatus.PUBLISHED: "Report sent to the patient"}
    events += [_event(e["at"], what[e["status"]]) for e in p.ledger if e.get("status") in what and e.get("at")]
    if p.row.get("reviewed"):
        events.append(_event(p.row["reviewed"], "Last review with the patient"))
    for x in p.plans:
        if x.get("start"):
            events.append(_event(x["start"], f"Plan started: {x['objective'][:50]}"))
        if x.get("review_at") and x["state"] not in CLOSED_PLAN_STATES:
            ahead = day(x["review_at"]) > day(now())
            events.append(_event(x["review_at"], f"Plan review: {x['objective'][:50]}",
                                 AlertLevel.INFO if ahead else AlertLevel.WATCH, kind="predicted" if ahead else "past"))
    return sorted(events, key=lambda e: e["t"])[-MAX_EVENTS:]


def _patient_tab(p: Patient) -> Tab:
    sex, age = p.sex_age
    g = p.groups
    blocks = [kv("Patient", (
        ("Patient", roster.shown(p.row)), ("Status on the panel", p.row.get("status", "")), ("Sex", sex), ("Age", age),
        ("On the panel since", p.row.get("since", "")), ("Latest result", p.latest or "none yet"),
        ("Last review with the patient", p.row.get("reviewed", "not yet")),
        ("Records", sum(map(len, g.values()))), ("Files waiting for intake", len(p.waiting)),
        ("Shared by the patient", ", ".join(p.row.get("shared", [])) or "not stated")), BlockIcon.PATIENT)]
    inside, out, _ = _in_range(p.labs)
    if inside + out:
        blocks.append(Block(type=BlockType.METER, title="Lab results in range", icon=BlockIcon.LAB, data={
            "value": inside, "max": inside + out, "label": "latest results inside the range printed on their report"}))
    if p.medicines:
        current = sum(med_status(o) == "current" for o in p.medicines)
        blocks.append(Block(type=BlockType.METER, title="Medicines taken now", icon=BlockIcon.MEDICINE, data={
            "value": current, "max": len(p.medicines), "label": "recorded medicines and supplements are current"}))
    blocks += _bioage(p.label)
    visits = _visits(p)
    blocks.append(Block(type=BlockType.TIMELINE, title="Visits and records", icon=BlockIcon.VISITS,
                        data={"now": day(now()), "events": visits})
                  if visits else Block(type=BlockType.MARKDOWN, title="Visits and records", icon=BlockIcon.VISITS,
                                       data={"text": "No dated records yet."}))
    for title, tests, ico in (("Blood and lab tests", p.labs, BlockIcon.LAB),
                              ("Body and vitals", series(g.get(MeasureGroup.BODY.value, [])), BlockIcon.VITALS)):
        if tests:
            blocks.append(table(f"{title}: latest results", RESULT_COLUMNS, [_result_row(s) for s in tests], ico))
        if trends := [_trend(s) for s in tests if sum(o.value_quantity is not None for o in s) > 1][:MAX_CHARTS]:
            blocks.append(Block(type=BlockType.TIMESERIES, title=f"{title}: trends", icon=BlockIcon.TREND,
                                data={"series": trends}))
    if devices := sorted(series(g.get(MeasureGroup.DEVICE.value, [])), key=lambda s: name(s[-1]).casefold()):
        blocks.append(table("Wearables and devices", ["Measure", "Latest", "Unit", "Date", "First", "Readings"],
                             [[name(s[-1]), value(s[-1]), units.display(s[-1].unit), day(s[-1].effective_at),
                               day(s[0].effective_at), len(s)] for s in devices], BlockIcon.DEVICE))
    if p.medicines:
        blocks.append(table("Medicines and supplements", ["Name as written", "Dose as written", "Status", "From", "Until"],
                             [[o.original_text, o.dose or (f"{o.dose_quantity:g} {o.dose_unit}" if o.dose_quantity else ""),
                               med_status(o), day(o.effective_at), day(o.effective_end)]
                              for o in p.medicines], BlockIcon.MEDICINE))
    for title, kinds, ico in (("Conditions, allergies and symptoms",
                               {"condition": "condition", "allergy": "allergy", "symptom": "symptom"}, BlockIcon.CONDITION),
                              ("Diet and lifestyle", {"lifestyle": "habit", "preference": "diet or preference", "goal": "goal"},
                               BlockIcon.DIET)):
        if obs := [o for k in kinds for o in g.get(k, [])]:
            blocks.append(table(title, ITEM_COLUMNS, _items(obs, kinds), ico))
    if p.plans:
        blocks.append(table("Plans", ["Objective", "State", "Start", "Review", "Predictions"],
                             [[x["objective"], x["state"], day(x.get("start")), day(x.get("review_at")),
                               x["predictions"]]
                              for x in sorted(p.plans, key=lambda x: (x["state"] in CLOSED_PLAN_STATES, x["created_at"]))],
                             BlockIcon.PLAN))
    if p.due:
        blocks.append(table("Follow-up measurements", ["Measure", "State", "From", "To", "How"],
                             [[d["coordinate"],
                               d["state"] if d["state"] == DueState.AWAITING else _mark(d["state"], AlertLevel.WATCH),
                               day(d["window"]["from"]), day(d["window"]["to"]), d.get("measure_hint") or ""]
                              for d in p.due], BlockIcon.FOLLOW_UP))
    if p.waiting:
        blocks.append(table("Files waiting for intake", ["Received", "Drive file"],
                             [[day(w["at"]), w["file"]] for w in p.waiting], BlockIcon.FILE))
    return Tab(id=p.label, title=roster.shown(p.row), blocks=blocks)


def _panel_tab(found: list[dict[str, Any]], patients: list[Patient], held: dict[str, str]) -> Tab:
    counts = {s.value: sum(r.get("status") == s.value for r in found) for s in RosterStatus}
    recent = day(now() - timedelta(days=RECENT_DAYS))
    ranges = [_in_range(p.labs) for p in patients]
    inside, out, unranged = (sum(r[i] for r in ranges) for i in range(3))
    blocks = [kv("Panel", (
        ("Patients", len(found)), ("Active / paused / closed", " / ".join(str(n) for n in counts.values())),
        ("With a result outside its range or a follow-up due", sum(bool(p.out_of_range or p.follow_ups) for p in patients)),
        ("Files waiting for intake", sum(len(p.waiting) for p in patients)),
        ("Updated", now().strftime("%Y-%m-%d %H:%M UTC"))), BlockIcon.PANEL),
        Block(type=BlockType.PARTS, title="Patients by status", icon=BlockIcon.PANEL, data={
            "unit": "patients on the panel", "items": [{"label": k, "value": n} for k, n in counts.items()]}),
        Block(type=BlockType.PARTS, title="Latest lab results", icon=BlockIcon.LAB, data={
            "unit": "tests, the latest result of each", "items": [
                {"label": "inside the report's range", "value": inside, "tone": AlertLevel.INFO.value},
                {"label": "outside it", "value": out, "tone": AlertLevel.HIGH.value},
                {"label": "no range printed", "value": unranged, "tone": AlertLevel.NEUTRAL.value}]}),
        table("Patients", ["Patient", "Status", "Sex, age", "Latest result", "Outside range", "Current medicines",
                            "Plans", "Follow-ups due", "Files waiting", "Last review"],
               [[p.link, p.row["status"], ", ".join(x for x in p.sex_age if x != "not given"), p.latest,
                 _mark(len(p.out_of_range), AlertLevel.HIGH) if p.out_of_range else 0,
                 sum(med_status(o) == "current" for o in p.medicines),
                 sum(x["state"] not in CLOSED_PLAN_STATES for x in p.plans), len(p.follow_ups), len(p.waiting),
                 p.row.get("reviewed", "")] for p in patients]
               + [[r["label"], r["status"]] + [""] * 8 for r in found if r.get("status") == RosterStatus.CLOSED.value],
               BlockIcon.PANEL)]
    tables = (("Latest results outside their range", BlockIcon.ALERT,
               ["Date", "Patient", "Test", "Result", "Report range", "Lab flag"],
               [[day(s[-1].effective_at), p.link, name(s[-1]),
                 _mark(f"{value(s[-1])} {units.display(s[-1].unit)}".strip(), AlertLevel.HIGH), ref_range(s[-1]),
                 s[-1].flag.value if s[-1].flag else ""] for p in patients for s in p.out_of_range]),
              ("Follow-ups due or missed", BlockIcon.FOLLOW_UP, ["To", "Patient", "Measure", "State", "From"],
               [[day(d["window"]["to"]), p.link, d["coordinate"], _mark(d["state"], AlertLevel.WATCH),
                 day(d["window"]["from"])] for p in patients for d in p.follow_ups]),
              (f"Last {RECENT_DAYS} days", BlockIcon.VISITS, ["Date", "Patient", "What", "Detail"],
               [[e["t"], p.link, e["label"], e["detail"]] for p in patients for e in _visits(p)
                if e["kind"] == "past" and e["t"] >= recent]))
    blocks += [table(title, columns, sorted(rows, key=lambda r: r[0], reverse=True), ico)  # newest first
               for title, ico, columns, rows in tables if rows]
    if held:
        blocks.append(Block(type=BlockType.LIST, title="Not shown", icon=BlockIcon.ALERT,
                            data={"items": [f"{k}: {v}" for k, v in held.items()]}))
    blocks.append(Block(type=BlockType.MARKDOWN, data={"text": NOTE}))
    return Tab(id=PANEL_TAB, title="All patients", blocks=blocks)


def dashboard() -> dict[str, Any]:
    """`plsi clinic dashboard`: rewrite the dashboard in place; the open page reloads itself."""
    found, held = roster.checked_rows()  # two patients who could be confused never share one page
    ledger = roster.ledger()
    patients = [gather(r, ledger) for r in found if r.get("status") in SHOWN and r["label"] not in held]
    closed = {r["label"] for r in found if r.get("status") == RosterStatus.CLOSED}
    held = {k: v for k, v in held.items() if k not in closed}  # a closed row is listed, never read
    doc = DashboardPayload(title="Clinic dashboard", subject_id="panel", generated_at=now(), refresh_seconds=RELOAD_SECONDS,
                           tabs=[_panel_tab(found, patients, held), *map(_patient_tab, patients)])
    atomic_write_text(path(), render(doc), private=True)
    return {"path": str(path()), "uri": path().as_uri(), "patients": len(patients),
            "outside_range": sum(bool(p.out_of_range) for p in patients),
            "follow_ups_due": sum(len(p.follow_ups) for p in patients)}


def refresh_after(dry_run: bool = False) -> None:
    """After a command that changed records or the roster: rebuild an existing dashboard, warning on failure."""
    if dry_run or not path().is_file():
        return
    try:
        dashboard()
    except Exception as e:  # noqa: BLE001 - the command itself succeeded
        warn("CLINIC_DASHBOARD_STALE", f"the clinic dashboard was not rebuilt ({e}); run plsi clinic dashboard")
