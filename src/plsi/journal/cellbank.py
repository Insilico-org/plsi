"""Plates, flasks and vials of cells: an entry's vessels, and the cell bank - every vial at its latest record, by
freezer box and position, with stock per cell line and passage."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from plsi.journal.models import EntryInput
from plsi.journal.results import Results
from plsi.vocab.journal import VesselStatus, VesselType


def _in_box(status: VesselStatus | None) -> bool:
    return status in (None, VesselStatus.FROZEN)


def vessels(r: Results) -> dict[str, Any]:
    if not r.vessels:
        return {}
    checks = []
    ids = defaultdict(int)
    slots: dict[tuple[str, str], list[str]] = defaultdict(list)
    for v in r.vessels:
        ids[v.id] += 1
        if v.box and v.position and _in_box(v.status):
            slots[(v.box, v.position)].append(v.id)
    checks += [f"vessel id {k} used {n} times" for k, n in ids.items() if n > 1]
    checks += [f"{', '.join(vs)} share box {b} position {p}" for (b, p), vs in slots.items() if len(vs) > 1]
    return {"rows": [v.dump() for v in r.vessels], "checks": checks}


def bank(entries: list[tuple[dict[str, Any], EntryInput]]) -> dict[str, Any]:
    """Every cryovial at its latest record (the latest entry date, then save time, wins); boxes, stock, clashes."""
    latest: dict[str, dict[str, Any]] = {}
    for _, e in sorted(entries, key=lambda x: (x[1].date, x[0].get("saved_at", ""))):
        for v in e.results.vessels:
            if v.type == VesselType.CRYOVIAL:
                key = f"{v.cell_line or ''}|{v.id}"
                latest[key] = {**latest.get(key, {}), **v.dump(), "entry": e.id, "entry_title": e.title}
    checks, boxes = [], defaultdict(dict)
    stock: dict[tuple[str, Any], int] = defaultdict(int)
    for v in latest.values():
        status = VesselStatus(v["status"]) if v.get("status") else None
        if not _in_box(status):
            continue
        stock[(v.get("cell_line") or "unnamed", v.get("passage"))] += 1
        if v.get("box") and v.get("position"):
            if (other := boxes[v["box"]].get(v["position"])) is not None:
                checks.append(f"box {v['box']} {v['position']}: {other['id']} and {v['id']} both recorded there")
            boxes[v["box"]][v["position"]] = v
        else:
            checks.append(f"vial {v['id']} ({v.get('cell_line') or 'no line'}) frozen without a box position")
    return {"vials": sorted(latest.values(), key=lambda v: (v.get("box") or "", v.get("position") or "", v["id"])),
            "boxes": [{"box": b, "slots": slots} for b, slots in sorted(boxes.items())],
            "stock": [{"cell_line": c, "passage": p, "vials": n} for (c, p), n in sorted(stock.items(), key=lambda x: (x[0][0], x[0][1] or 0))],
            "checks": checks}
