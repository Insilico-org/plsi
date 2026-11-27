"""`plsi journal import`: a Lab Journal kept outside PLSI (skill or plugin layout); existing records are never touched."""

from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from plsi.errors import NotFound, PlsiError
from plsi.files import atomic_write_json, hash_json, load_json
from plsi.journal import days, home, plasmid, store
from plsi.journal.models import INTERNAL, EntryInput
from plsi.journal.results import Results
from plsi.models import parse
from plsi.paths import is_valid_id
from plsi.vocab.journal import EntryStatus, ExperimentKind

KINDS = {k.value for k in ExperimentKind}
STATUSES = {EntryStatus.PLANNED.value, EntryStatus.RUNNING.value, EntryStatus.DONE.value}
VERSION = re.compile(r"^v\d+\.json$")
PLATES = {"6", "12", "24", "48", "96", "384"}


def _why(err: Exception) -> str:
    return getattr(err, "message", None) or str(err)[:300]


def _plain(p: Path) -> bool:
    """A regular file, not a link: an unpacked archive's link could point anywhere on this computer."""
    return p.is_file() and not p.is_symlink()


def _no_links(folder: str, names: list[str]) -> list[str]:
    return [n for n in names if (Path(folder) / n).is_symlink()]


def _version(p: Path) -> int:
    return int(p.stem[1:]) if p.stem[1:].isdigit() else -1


def _text(v: Any) -> str | None:
    if v is None or v == "" or v == []:
        return None
    return " · ".join(str(x) for x in v) if isinstance(v, list) else str(v)


def _steps(raw: Any) -> list[dict[str, Any]]:
    out = []
    for s in raw or []:
        s = {"text": s} if isinstance(s, str) else dict(s)
        text = s.get("text") or s.get("step") or s.get("name")
        if text:
            out.append({"text": str(text), "done": bool(s.get("done", False))})
    return out


def _reagents(raw: Any) -> list[dict[str, Any]]:
    out = []
    for r in raw or []:
        r = {"name": r} if isinstance(r, str) else dict(r)
        name = r.get("name") or r.get("reagent")
        if not name:
            continue
        row = {"name": str(name)[:200]}
        for k in ("supplier", "catalog", "lot", "stock", "amount"):
            if r.get(k) not in (None, ""):
                row[k] = str(r[k])
        if r.get("conc") not in (None, "") and "stock" not in row:
            row["stock"] = str(r["conc"])
        out.append(row)
    return out


def _results(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    """Results PLSI's model reads (unknown row fields dropped), the qPCR plate, and the keys left out."""
    fields = Results.model_fields
    kept: dict[str, Any] = {}
    left: list[str] = []
    plate = None
    for key, val in raw.items():
        if key == "plate":
            continue
        if key not in fields:
            left.append(key)
            continue
        row_model = getattr(fields[key].annotation, "__args__", (None,))[0]
        if isinstance(val, list) and val and isinstance(val[0], dict) and hasattr(row_model, "model_fields"):
            val = [{k: v for k, v in r.items() if k in row_model.model_fields} for r in val]
        try:
            TypeAdapter(fields[key].annotation).validate_python(val)
            kept[key] = val
        except Exception:  # noqa: BLE001 - a part that does not fit stays in the original file
            left.append(key)
    wells = [{"well": r["well"], "sample": r.get("sample"), "group": r.get("group")}
             for r in raw.get("cts") or [] if isinstance(r, dict) and r.get("well")]
    if wells:
        fmt = "".join(ch for ch in str(raw.get("plate", "96")) if ch.isdigit())
        unique = list({w["well"]: w for w in wells}.values())
        plate = {"format": fmt if fmt in PLATES else "96", "wells": unique}
    return kept, plate, left


def _entry(raw: dict[str, Any], related_ok: set[str]) -> tuple[dict[str, Any], list[str]]:
    results, plate, left = _results(raw.get("results") or {})
    kind = str(raw.get("kind", "other")).lower()
    status = str(raw.get("status", "done")).lower()
    e: dict[str, Any] = {
        "id": raw["id"], "title": str(raw.get("title") or raw["id"])[:200],
        "kind": kind if kind in KINDS else "other", "date": raw["date"],
        "status": status if status in STATUSES else "done",
        "aim": _text(raw.get("aim")), "protocol": _steps(raw.get("protocol")),
        "reagents": _reagents(raw.get("materials") or raw.get("reagents")), "results": results,
        "observations": _text(raw.get("observations")), "conclusion": _text(raw.get("conclusion")),
        "next_steps": _text(raw.get("next_steps")), "project": raw.get("project"),
        "related": [r for r in raw.get("related") or [] if r in related_ok],
        "tags": [str(t)[:40] for t in raw.get("tags") or []][:12],
    }
    if plate:
        e["plate"] = plate
    if raw.get("amends") in related_ok:
        e["amends"] = raw["amends"]
    if kind not in KINDS:
        left.append(f"kind {kind!r} (now other)")
    left += [k for k in ("plasmid", "flags") if raw.get(k)]
    return {k: v for k, v in e.items() if v not in (None, [], {})} | {"results": results}, left


def _bookkeeping_free(e: dict[str, Any]) -> list[str]:
    """Moves text the save would refuse as bookkeeping out of the entry, for its record."""
    return [f"{f}: {e.pop(f)}" for f in ("observations", "conclusion", "next_steps") if e.get(f) and INTERNAL.search(e[f])]


def run(source: str, dry_run: bool = False) -> dict[str, Any]:
    """Import every entry under `<source>/journal/` and the day plans under `<source>/days/`."""
    src = Path(source).expanduser()
    jdir = src / "journal" if (src / "journal").is_dir() else src
    if (jdir / "entries").is_dir():
        return _native(src, jdir, dry_run)
    folders = sorted(p for p in jdir.iterdir() if p.is_dir() and any(p.glob("v*.json"))) if jdir.is_dir() else []
    if not folders:
        raise NotFound(f"no Lab Journal entries under {src}", code="IMPORT_EMPTY",
                       hint="give the Lab Journal's home folder (the one holding journal/ and days/)")
    latest = {f.name: max(f.glob("v*.json"), key=_version) for f in folders}
    docs = {eid: load_json(p) for eid, p in latest.items()}
    imported, skipped, failed = [], [], []
    for eid in [e for e in docs if not is_valid_id(e)]:
        failed.append({"id": eid, "why": "not a PLSI entry id (lower case letters, digits, - and _)"})
        docs.pop(eid)
    ids = set(docs)
    done: set[str] = {eid for eid in ids if home.has_entry(eid)}
    skipped += [{"id": eid, "why": "already in the journal"} for eid in sorted(done)]
    pending = [eid for eid in sorted(ids) if eid not in done]
    while pending:  # an entry goes after the entries it names (related, amends)
        ready = [eid for eid in pending
                 if all(r in done or r not in ids for r in [*(docs[eid].get("related") or []), docs[eid].get("amends")] if r and r != eid)]
        if not ready:
            failed += [{"id": eid, "why": "its related entries form a loop"} for eid in pending]
            break
        for eid in ready:
            pending.remove(eid)
            row = _one(eid, docs[eid], jdir / eid, done, dry_run)
            ok = row.pop("ok")
            (imported if ok else failed).append(row)
            if ok:
                done.add(eid)
    plans = _days(src / "days", done, dry_run)
    return {"source": str(src), "dry_run": dry_run, "imported": imported, "skipped": skipped, "failed": failed,
            "days": plans, "next": "plsi journal list" if imported and not dry_run else None}


def _one(eid: str, raw: dict[str, Any], folder: Path, done: set[str], dry_run: bool) -> dict[str, Any]:
    versions = sorted(folder.glob("v*.json"), key=_version)
    try:
        e, left = _entry(raw, done | ({raw["amends"]} if raw.get("amends") in done else set()))
        moved = _bookkeeping_free(e)
        signed = raw.get("signed") if isinstance(raw.get("signed"), dict) else None
        originals = [f"lab-journal-{v.name}" for v in versions] + (["lab-journal-history.jsonl"] if (folder / "history.jsonl").is_file() else [])
        kept = [f.name for f in folder.iterdir() if _plain(f) and f.suffix.lower() in store.FILE_SUFFIXES
                and not f.name.startswith(".") and f.name != "history.jsonl" and not VERSION.match(f.name)]
        files_dir = folder / "files"
        kept += [f.name for f in files_dir.iterdir() if _plain(f) and f.suffix.lower() in store.FILE_SUFFIXES] if files_dir.is_dir() else []
        e["files"] = sorted(set(originals + kept))
        record = [f"Imported from the Lab Journal ({len(versions)} version{'s' * (len(versions) != 1)}; originals kept as "
                  f"{', '.join(originals)}). Numbers are derived again by PLSI."]
        if raw.get("code_sha256"):
            record.append(f"Lab Journal code {raw['code_sha256']}.")
        if signed:
            record.append(f"Signed in the Lab Journal by {signed.get('by')} at {signed.get('at')}; not signed in "
                          f"PLSI until the researcher signs it here.")
        if left:
            record.append(f"Kept only in the original files: {', '.join(left)}.")
        record += [f"Moved from {m}" for m in moved]
        e["record"] = " ".join(record)[:4000]
        parse(EntryInput, e)
        if dry_run:
            return {"ok": True, "id": eid, "signed_elsewhere": bool(signed), "left_out": left}
        dest = home.entry_dir(eid) / "files"
        dest.mkdir(parents=True, exist_ok=True)
        for v in versions:
            shutil.copyfile(v, dest / f"lab-journal-{v.name}")
        if (folder / "history.jsonl").is_file():
            shutil.copyfile(folder / "history.jsonl", dest / "lab-journal-history.jsonl")
        for name in kept:
            src = folder / name if (folder / name).is_file() else files_dir / name
            if not (dest / name).exists():
                shutil.copyfile(src, dest / name)
        tmp = home.entry_dir(eid) / "import.json"
        atomic_write_json(tmp, e)
        try:
            out = store.save(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)
        return {"ok": True, "id": eid, "version": out["version"], "signed_elsewhere": bool(signed), "left_out": left,
                "checks": out.get("checks", [])}
    except (PlsiError, KeyError, ValueError) as err:
        if not dry_run and not home.has_entry(eid) and home.entry_dir(eid).is_dir():
            shutil.rmtree(home.entry_dir(eid))
        return {"ok": False, "id": eid, "why": _why(err)}


def _days(ddir: Path, entries: set[str], dry_run: bool) -> list[dict[str, Any]]:
    out = []
    for p in sorted(ddir.glob("*.json")) if ddir.is_dir() else []:
        try:
            plan = load_json(p)
            day = dt.date.fromisoformat(plan["date"])
            if home.day_path(day).is_file():
                out.append({"date": plan["date"], "imported": False, "why": "a plan for that day exists"})
                continue
            items = [{k: v for k, v in i.items() if k in days.DayItem.model_fields}
                     for i in plan.get("items", [])]
            for i in items:
                if i.get("entry") and i["entry"] not in entries:
                    i.pop("entry")
            body = {"date": plan["date"], "items": items, **({"note": plan["note"]} if plan.get("note") else {})}
            if not dry_run:
                tmp = home.root() / f".import-day-{p.name}"
                atomic_write_json(tmp, body)
                try:
                    days.save(str(tmp))
                finally:
                    tmp.unlink(missing_ok=True)
            out.append({"date": plan["date"], "imported": True, "items": len(items)})
        except (PlsiError, KeyError, ValueError) as err:
            out.append({"date": p.stem, "imported": False, "why": _why(err)})
    return out


def _native(src: Path, jdir: Path, dry_run: bool) -> dict[str, Any]:
    """PLSI's own layout: new entries, plasmids and day plans copied byte for byte after the hash check."""
    imported, skipped, failed = [], [], []
    for folder in sorted(p for p in (jdir / "entries").iterdir() if p.is_dir()):
        eid = folder.name
        try:
            if not is_valid_id(eid) or not (folder / "entry.json").is_file():
                raise ValueError("not an entry folder (entry.json and a lower-case id)")
            doc = load_json(folder / "entry.json")
            parse(EntryInput, doc["entry"])
            if doc["entry"].get("id") != eid or doc.get("hash") != hash_json(doc["entry"]):
                raise ValueError("entry.json does not match its stored hash or id: changed outside the journal")
            if doc.get("signed") and doc["signed"].get("hash") != doc["hash"]:
                raise ValueError("the signature does not match the entry")
            if home.has_entry(eid):
                skipped.append({"id": eid, "why": "already in the journal"})
                continue
            if not dry_run:
                shutil.copytree(folder, home.entry_dir(eid),
                                ignore=lambda d, n: [*shutil.ignore_patterns(".*")(d, n), *_no_links(d, n)])
            imported.append({"id": eid, "version": doc.get("version"), "signed": bool(doc.get("signed"))})
        except (PlsiError, KeyError, ValueError) as err:
            failed.append({"id": eid, "why": _why(err)})
    extra = {}
    for sub in ("plasmids", "days"):
        rows = []
        for p in sorted((jdir / sub).glob("*.json")) if (jdir / sub).is_dir() else []:
            dest = home.root() / sub / p.name
            name_ok = is_valid_id(p.stem) if sub == "plasmids" else re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)
            if not name_ok or not _plain(p):
                rows.append({"file": p.name, "imported": False, "why": "not a journal file name"})
                continue
            try:  # checked as the journal reads it, so a malformed file cannot break `journal today` or the page
                doc = load_json(p)
                if sub == "days":  # a stored plan carries the time it was saved
                    doc = {k: v for k, v in doc.items() if k != "saved_at"} if isinstance(doc, dict) else doc
                parse(plasmid.Plasmid if sub == "plasmids" else days.DayPlan, doc)
            except (PlsiError, ValueError) as err:
                rows.append({"file": p.name, "imported": False, "why": _why(err)})
                continue
            if dest.exists():
                rows.append({"file": p.name, "imported": False, "why": "already here"})
                continue
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, dest)
            rows.append({"file": p.name, "imported": True})
        extra[sub] = rows
    return {"source": str(src), "layout": "plsi", "dry_run": dry_run, "imported": imported, "skipped": skipped,
            "failed": failed, **extra, "next": "plsi journal list" if imported and not dry_run else None}
