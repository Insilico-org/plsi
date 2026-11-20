"""`plsi journal page`: the whole lab journal as one self-contained HTML file. The template's style and script are
assembled from `journal/page/` in a fixed order; pictures are embedded as data: URIs within the caps of `tuning`."""

from __future__ import annotations

import base64
from importlib import resources
from typing import Any

from plsi.clock import now
from plsi.errors import warn
from plsi.files import atomic_write_text, read_jsonl
from plsi.journal import calc, cellbank, days, home, plasmid, store
from plsi.journal.models import EntryInput
from plsi.journal.tuning import PAGE, PAGE_IMAGE_BYTES, PAGE_IMAGES_BYTES, PAGE_RELOAD_SECONDS
from plsi.report import render_template

IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
# the page script, in load order: helpers first, the views, then the shell that routes to them
SCRIPT = ("core", "assays", "flow", "animals", "plasmid", "calc", "shell", "cells", "day", "entries", "app")


def _images(entry_id: str, names: list[str], budget: list[int]) -> list[dict[str, Any]]:
    out = []
    for name in names:
        f = home.entry_dir(entry_id) / "files" / name
        kind, size = IMAGE_TYPES.get(f.suffix.lower()), f.stat().st_size if f.is_file() else None
        if size is None:
            out.append({"name": name, "missing": True})
        elif kind is None or size > PAGE_IMAGE_BYTES or budget[0] + size > PAGE_IMAGES_BYTES:
            out.append({"name": name, "bytes": size})
        else:
            budget[0] += size
            out.append({"name": name, "src": f"data:{kind};base64," + base64.b64encode(f.read_bytes()).decode("ascii")})
    return out


def _entry(doc: dict[str, Any], e: EntryInput, budget: list[int]) -> dict[str, Any]:
    return {"entry": doc["entry"], "status": store.status_of(doc), "version": doc["version"], "saved_at": doc["saved_at"],
            "hash": doc["hash"], "signed": doc.get("signed"), "derived": store.derived(e.id, e.results),
            "history": read_jsonl(home.entry_dir(e.id) / "history.jsonl"), "files": _images(e.id, e.files, budget)}


def payload() -> dict[str, Any]:
    budget, found = [0], store.entries()
    entries = sorted((_entry(doc, e, budget) for doc, e in found), key=lambda x: (x["entry"]["date"], x["entry"]["id"]), reverse=True)
    plasmids = [{**{k: v for k, v in p.dump().items() if k != "sequence"}, "sites": plasmid.sites(p)} for p in plasmid.saved()]
    units = {"molar": calc.MOLAR, "mass_conc": calc.MASS_CONC, "volume": calc.VOLUME, "mass": calc.MASS,
             "wells": {k.value: {"area": a, "volume_ml": v} for k, (a, v) in calc.WELLS.items()}}
    return {"kind": "plsi_lab_journal", "schema_version": 1, "title": "Lab journal", "generated_at": now().isoformat(),
            "refresh_seconds": PAGE_RELOAD_SECONDS, "tuning": PAGE, "entries": entries, "plasmids": plasmids, "units": units,
            "days": days.plans()[-120:], "bank": cellbank.bank(found)}


def _parts() -> dict[str, str]:
    folder = resources.files("plsi.journal").joinpath("page")
    script = "\n".join(folder.joinpath(f"{name}.js").read_text(encoding="utf-8") for name in SCRIPT)
    return {"__PLSI_STYLE__": folder.joinpath("journal.css").read_text(encoding="utf-8"), "__PLSI_SCRIPT__": script}


def page() -> dict[str, Any]:
    """Rewrite the journal page in place; an open copy reloads itself."""
    doc = payload()
    path = home.page_path()
    atomic_write_text(path, render_template("journal/journal.html", doc, _parts()), private=True)
    return {"path": str(path), "uri": path.as_uri(), "entries": len(doc["entries"]), "plasmids": len(doc["plasmids"])}


def refresh_after(dry_run: bool = False) -> None:
    """After a command that changed the journal: rebuild an existing page, warning on failure."""
    if dry_run or not home.page_path().is_file():
        return
    try:
        page()
    except Exception as e:  # noqa: BLE001 - the command itself succeeded
        warn("JOURNAL_PAGE_STALE", f"the journal page was not rebuilt ({e}); run plsi journal page")
