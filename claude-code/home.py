"""PLSI home dashboard: one self-contained HTML page with the state of the whole install.

Read-only. Collects from the `plsi` commands (instances, latest states, due predictions, plans, Mothership status,
key status) and from Claude Code's side of the install (.plsi/memory.md, the subagents, routines, the outbox and open
threads), builds a DashboardPayload and renders it with PLSI's own report template (plsi.report.render).

    python claude-code/home.py            # writes <PLSI_HOME>/dashboard/home.html, prints one JSON line
    python claude-code/home.py --open     # ... and opens it in the default browser
    python claude-code/home.py --payload  # prints the DashboardPayload JSON instead of rendering
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
from gen_agents import installed as installed_agents, roster  # noqa: E402

PLSI = shutil.which("plsi", path=f"{REPO / '.venv' / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}") or "plsi"
YEARS = {"a": "years"}
CONTEXT_ONLY = {"chronological_age"}  # shown as a value, never charted: a calendar trend says nothing
# persona.md's output notice; report.html's markdown has *italic*, not _italic_
NOTICE = ("*Generated automatically by AI and not reviewed by a clinician. Check with your clinician before acting on "
          "it.* [Disclaimer](https://github.com/Insilico-org/plsi/blob/main/legal/DISCLAIMER.md)")


def plsi(*args: str) -> object:
    """Run one plsi command; its `data`, or None when it fails."""
    try:
        out = subprocess.run([PLSI, *args], capture_output=True, text=True, timeout=120, cwd=REPO)
        env = json.loads(out.stdout)
        return env.get("data") if env.get("ok") else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def plsi_home() -> Path:
    doctor = plsi("doctor") or {}
    return Path(doctor.get("plsi_home") or os.environ.get("PLSI_HOME") or REPO / "instances")


def memory() -> tuple[dict[str, str], dict[str, list[list[str]]]]:
    """('- Key: value' facts, '## Section' -> rows split on ' | ') from .plsi/memory.md."""
    facts: dict[str, str] = {}
    sections: dict[str, list[list[str]]] = {}
    current = None
    path = REPO / ".plsi" / "memory.md"
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif m := re.match(r"\s*-\s+(.*)", line):
            item = m.group(1).strip()
            if current:
                sections[current].append([c.strip() for c in item.split("|")])
            elif ":" in item:
                key, value = item.split(":", 1)
                facts[key.strip()] = value.strip()
    return facts, sections


def fmt_num(value: object, unit: str = "") -> str:
    if not isinstance(value, (int, float)):
        return "—"
    unit = YEARS.get(unit, unit)
    return f"{round(value, 1):g}" + (f" {unit}" if unit else "")


def day(ts: object) -> str:
    return str(ts)[:10] if ts else "—"


def due_rows(due: dict) -> list[list[str]]:
    rows = []
    for inst, items in (due.get("instances") or {}).items():
        for item in items or []:
            if isinstance(item, dict):
                what = item.get("label") or item.get("coordinate") or item.get("prediction_id") or "measurement"
                when = item.get("due_at") or item.get("review_at") or item.get("horizon") or ""
                rows.append([inst, str(what), day(when), str(item.get("status") or item.get("plan_id") or "")])
            else:
                rows.append([inst, str(item), "", ""])
    return rows


def map_labels(inst: str, map_id: str) -> tuple[str, dict[str, str]]:
    data = plsi("maps", "show", map_id, "--instance", inst) or {}
    m = data.get("map", data) if isinstance(data, dict) else {}
    return m.get("title") or map_id, {c["id"]: c.get("label") or c["id"] for c in m.get("coordinates") or []}


def state_summary(inst: str, map_ids: list[str]) -> tuple[list[dict], list[dict], int]:
    """Derived values (kv items), their series with two or more points (timeseries, one chart each: report.html
    labels only predicted series, so observed lines never share a chart), and markers recorded."""
    items, series, markers = [], [], 0
    for map_id in map_ids:
        data = plsi("state", "show", "--instance", inst, "--map", map_id) or {}
        coords = (data.get("state") or {}).get("coordinates") or {}
        _, labels = map_labels(inst, map_id)
        for cid, cv in coords.items():
            if cv.get("status") != "present":
                continue
            derived = (cv.get("provenance") or {}).get("match") == "derived"
            markers += not derived
            if not derived:
                continue
            label, unit = labels.get(cid, cid.replace("_", " ").capitalize()), cv.get("unit") or ""
            items.append({"key": label, "value": f"{fmt_num(cv.get('value'), unit)} (as of {day(cv.get('observed_at'))})"})
            points = [{"t": day(p.get("t")), "v": p.get("value")} for p in cv.get("series") or []]
            if len(points) >= 2 and cid not in CONTEXT_ONLY:
                series.append({"name": label.replace(":", " -"), "unit": YEARS.get(unit, unit),
                               "points": points, "predictions": []})
    return items, series, markers


def outbox(home: Path) -> list[dict]:
    box = home / "outbox"
    out = []
    for f in sorted(box.glob("*.md")) if box.is_dir() else []:
        first = next((ln.strip("# ").strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()), "")
        out.append({"text": f"{f.stem}: {first[:140]}" if first else f.stem})
    return out


def open_threads(home: Path) -> list[str]:
    threads = []
    for ledger in sorted((home / "work").glob("*/ledger.md")):
        text = ledger.read_text(encoding="utf-8")
        if re.search(r"\|\s*(sent|asked|retry|planned)\s*\|", text):
            threads.append(ledger.parent.name)
    return threads


def cron_routines() -> set[str]:
    try:
        tab = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return set(re.findall(r"# PLSI:(.+)$", tab, re.M))


def build() -> tuple[dict, list[str]]:
    home = plsi_home()
    facts, sections = memory()
    people = plsi("instances", "list") or []
    due = plsi("due", "--all") or {}
    keys = plsi("keys", "status") or {}
    role = (plsi("role", "show") or {}).get("role") or facts.get("Role") or "individual"
    version = subprocess.run([PLSI, "--version"], capture_output=True, text=True).stdout.strip() or "—"
    me = facts.get("User's instance") or next((p["instance"] for p in people if (p.get("subject") or {}).get("relation") == "self"), None)

    attention: list[str] = []
    if facts.get("Setup") != "complete":
        attention.append(f"Setup is not finished ({facts.get('Setup') or 'not started'}): run /plsi-setup.")
    dues = due_rows(due)
    if dues:
        attention.append(f"{len(dues)} measurement(s) due for scoring predictions: see Due below.")
    messages = outbox(home)
    if messages:
        attention.append(f"{len(messages)} unread message(s) from scheduled routines: PLSI shows them at the start of a session.")
    threads = open_threads(home)
    if threads:
        attention.append(f"Open work: {', '.join(threads)}.")
    team_roles = [row[0] for row in sections.get("Team", []) if row and row[0]]
    missing = [r for r in team_roles if r not in installed_agents()]
    if missing:
        attention.append(f"Team members not loaded: {', '.join(missing)} (run python claude-code/gen_agents.py --add {' '.join(missing)}).")

    blocks: list[dict] = [{"type": "markdown", "title": "Needs your attention",
                           "data": {"text": "\n".join(f"- {a}" for a in attention) or "All clear: nothing needs you right now."}}]

    mother = (plsi("mothership", "status", "--instance", me) or {}) if me else {}
    set_keys = [k for k, v in keys.items() if v and not k.startswith("PLSI_")]
    blocks.append({"type": "kv", "title": "Your PLSI", "data": {"items": [
        {"key": "Version", "value": version}, {"key": "Setup", "value": facts.get("Setup") or "not started"},
        {"key": "Role", "value": role}, {"key": "Own health", "value": facts.get("Own health") or "on"},
        {"key": "People tracked", "value": str(len(people))},
        {"key": "Longevity Mothership", "value": "joined" if mother.get("enrolled") else "not joined"},
        {"key": "Keys set", "value": f"{len(set_keys)} of {len([k for k in keys if not k.startswith('PLSI_')])}"},
        {"key": "Voice", "value": f"{facts.get('Voice') or 'off'} (spoken replies {facts.get('Speak replies') or 'off'})"},
        {"key": "Tips", "value": facts.get("Tips") or "on"},
    ]}})

    if me:
        mine = next((p for p in people if p.get("instance") == me), {})
        items, series, markers = state_summary(me, mine.get("states") or [])
        items = [{"key": "Markers recorded", "value": str(markers)},
                 {"key": "Last recorded", "value": day(mine.get("last_recorded_at"))}] + items
        blocks.append({"type": "kv", "title": f"Your health at a glance ({me})", "data": {"items": items}})
        if series:
            blocks.append({"type": "timeseries", "title": "Derived measures over time", "data": {"series": series}})
        if len(items) > 2:  # a score is shown: persona.md's output notice, unchanged, once
            blocks.append({"type": "markdown", "title": None, "data": {"text": NOTICE}})

    if people:
        rows = []
        for p in people:
            s = p.get("subject") or {}
            n_due = len((due.get("instances") or {}).get(p["instance"]) or [])
            rows.append([p["instance"], s.get("relation") or "—", s.get("sex") or "—", str(s.get("birth_year") or "—"),
                         p.get("active_observations", 0), day(p.get("last_recorded_at")),
                         ", ".join(p.get("states") or []) or "—", n_due])
        blocks.append({"type": "table", "title": "People", "data": {
            "columns": ["instance", "relation", "sex", "born", "observations", "last recorded", "maps", "due"], "rows": rows}})

    plan_rows = []
    for p in people:
        for plan in plsi("plan", "list", "--instance", p["instance"]) or []:
            plan_rows.append([p["instance"], plan.get("objective") or plan.get("plan_id"), plan.get("state") or "—",
                              day(plan.get("created_at")), day(plan.get("review_at"))])
    if plan_rows:
        blocks.append({"type": "table", "title": "Plans", "data": {
            "columns": ["instance", "objective", "state", "created", "review"], "rows": plan_rows}})
    if dues:
        blocks.append({"type": "table", "title": "Due", "data": {"columns": ["instance", "what", "by", "status"], "rows": dues}})

    names = {r["role"]: r for r in roster()}
    loaded = set(installed_agents())
    team_rows = [["PLSI · Chief Orchestrator", "orchestrator", "core", "main session"]]
    for role_slug in team_roles or sorted(loaded):
        r = names.get(role_slug, {})
        team_rows.append([r.get("display", role_slug), role_slug, r.get("tier", "—"), "yes" if role_slug in loaded else "no"])
    blocks.append({"type": "table", "title": "Team", "data": {"columns": ["member", "role", "tier", "loaded"], "rows": team_rows}})

    scheduled = cron_routines()
    routine_rows = [[row[0], row[1] if len(row) > 1 else "—", "yes" if row[0] in scheduled else "no"]
                    for row in sections.get("Routines", []) if row and row[0]]
    routine_rows += [[name, "—", "yes"] for name in sorted(scheduled - {r[0] for r in routine_rows})]
    if routine_rows:
        blocks.append({"type": "table", "title": "Routines", "data": {"columns": ["routine", "schedule", "in cron"], "rows": routine_rows}})
    if messages:
        blocks.append({"type": "list", "title": "Messages from routines", "data": {"items": messages}})

    payload = {"kind": "plsi_dashboard", "schema_version": 1, "title": "PLSI home",
               "subject_id": me or "plsi", "generated_at": datetime.now(timezone.utc).isoformat(), "blocks": blocks}
    return payload, attention


def main(argv: list[str]) -> int:
    payload, attention = build()
    if "--payload" in argv:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
        return 0
    try:
        from plsi.report import DashboardPayload, render
        from plsi.models import parse
    except ImportError:
        print(json.dumps({"ok": False, "error": "plsi is not importable: run with .venv/bin/python"}))
        return 1
    html = render(parse(DashboardPayload, payload))
    out = plsi_home() / "dashboard" / "home.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    if "--open" in argv:
        webbrowser.open(out.as_uri())
    print(json.dumps({"ok": True, "path": str(out), "uri": out.as_uri(), "blocks": len(payload["blocks"]),
                      "attention": attention}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
