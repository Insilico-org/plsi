"""Journal entries on disk (`journal/entries/<id>/`: entry.json, history.jsonl, files/): every save is the next
version with its hash in the history; `sign` freezes an entry, and a correction is a new entry that `amends` it."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from plsi.clock import now
from plsi.errors import NotFound, PlsiError, ValidationError, warn
from plsi.files import append_jsonl, atomic_write_json, hash_json, load_json, lock, read_jsonl
from plsi.journal import analysis, cellbank, flow, home
from plsi.journal.models import EntryInput
from plsi.journal.results import Results
from plsi.journal.templates import starter
from plsi.journal.tuning import FCS_BYTES, FILE_BYTES
from plsi.models import parse
from plsi.paths import safe_join
from plsi.vocab.journal import EntryStatus, ExperimentKind

FILE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".csv", ".tsv", ".txt", ".xlsx", ".pdf", ".gb",
                 ".gbk", ".dna", ".fcs", ".czi", ".lif", ".nd2", ".json", ".md"}
SECRET_DIRS = {".ssh", ".gnupg", ".aws", ".azure", ".kube", ".docker", ".password-store"}  # never copied from


def _read(entry_id: str) -> dict[str, Any]:
    if not home.has_entry(entry_id):
        raise NotFound(f"no journal entry {entry_id!r}", code="ENTRY_NOT_FOUND", hint="plsi journal list")
    return load_json(home.entry_dir(entry_id) / "entry.json")


def entries() -> list[tuple[dict[str, Any], EntryInput]]:
    """Every stored entry with its parsed input; one that does not parse is a warning, never a failure."""
    out = []
    for p in sorted((home.root() / "entries").glob("*/entry.json")):
        doc = load_json(p)
        try:
            out.append((doc, parse(EntryInput, doc["entry"])))
        except PlsiError as e:
            warn("ENTRY_UNREADABLE", f"{p.parent.name}: {e.message}; save it again")
    return out


def status_of(doc: dict[str, Any]) -> str:
    return EntryStatus.SIGNED.value if doc.get("signed") else doc["entry"].get("status", EntryStatus.DONE.value)


def _summary(doc: dict[str, Any]) -> dict[str, Any]:
    e = doc["entry"]
    return {"id": e["id"], "title": e["title"], "kind": e["kind"], "date": e["date"], "project": e.get("project"),
            "status": status_of(doc), "version": doc["version"]}


def derived(entry_id: str, results: Results, strict: bool = False) -> dict[str, Any]:
    """Every number the results allow, the flow block from the entry's FCS files included (strict: refuse a wrong
    channel or file instead of reporting it)."""
    out = analysis.derive(results)
    if gated := flow.derive(home.entry_dir(entry_id), results, strict=strict):
        out["flow"] = gated
    return out


def _guard(entry: EntryInput, old: dict[str, Any] | None) -> None:
    """What a save refuses: a signed entry, amending a draft, links to entries or plasmids that do not exist."""
    if old and old.get("signed"):
        raise ValidationError(f"entry {entry.id!r} is signed and never changes", code="ENTRY_SIGNED",
                              hint=f'write a new entry with "amends": "{entry.id}"')
    if entry.amends and not _read(entry.amends).get("signed"):
        raise ValidationError(f"{entry.amends!r} is not signed: edit it instead of amending it", code="AMEND_UNSIGNED")
    if missing := [x for x in entry.related if x != entry.id and not home.has_entry(x)]:
        raise NotFound(f"related entries not in the journal: {', '.join(missing)}", code="ENTRY_NOT_FOUND", hint="plsi journal list")
    if entry.results.plasmid and not home.plasmid_path(entry.results.plasmid).is_file():
        raise NotFound(f"no plasmid {entry.results.plasmid!r}", code="PLASMID_NOT_FOUND", hint="plsi journal plasmid save")


def save(file: str) -> dict[str, Any]:
    """`journal save --file entry.json`: the first version, or the next one of an unsigned entry."""
    entry = parse(EntryInput, load_json(file))
    if found := entry.bookkeeping():
        raise ValidationError("; ".join(found), code="OBSERVATIONS_BOOKKEEPING",
                              hint="write what was seen at the bench in plain words; files, rows and fields go in record")
    folder = home.entry_dir(entry.id)
    folder.mkdir(parents=True, exist_ok=True)
    with lock(folder):
        old = load_json(folder / "entry.json") if (folder / "entry.json").is_file() else None
        _guard(entry, old)
        found = derived(entry.id, entry.results, strict=True)
        body = entry.dump()
        doc = {"entry": body, "version": old["version"] + 1 if old else 1, "saved_at": now().isoformat(), "hash": hash_json(body)}
        if old and old["hash"] == doc["hash"]:
            return {**_summary(old), "changed": False}
        atomic_write_json(folder / "entry.json", doc, private=True)
        append_jsonl(folder / "history.jsonl", {"version": doc["version"], "saved_at": doc["saved_at"],
                                                "status": entry.status.value, "hash": doc["hash"]})
    checks = analysis.checks(found)
    if entry.status == EntryStatus.RUNNING and entry.protocol and all(s.done for s in entry.protocol) and found:
        checks.append("every protocol step is done and results are in, yet the entry is running: is it done?")
    return {**_summary(doc), "changed": True, "checks": checks, "path": str(folder / "entry.json"),
            "files_missing": [f for f in entry.files if not (folder / "files" / f).is_file()]}


def show(entry: str) -> dict[str, Any]:
    doc = _read(entry)
    found = derived(entry, parse(EntryInput, doc["entry"]).results)
    if "flow" in found:  # the plots are for the page
        found["flow"] = {**found["flow"], "samples": [{k: v for k, v in s.items() if k != "plots"} for s in found["flow"]["samples"]]}
    return {**doc, "status": status_of(doc), "derived": found, "history": read_jsonl(home.entry_dir(entry) / "history.jsonl")}


def list_entries(project: str | None = None, kind: str | None = None) -> dict[str, Any]:
    rows = [r for r in (_summary(d) for d, _ in entries())
            if (project is None or r["project"] == project) and (kind is None or r["kind"] == kind)]
    return {"entries": sorted(rows, key=lambda r: (r["date"], r["id"]), reverse=True),
            "projects": sorted({r["project"] for r in rows if r["project"]})}


def sign(entry: str, by: str, witness: str | None = None) -> dict[str, Any]:
    """Freeze an entry: who signed, when, the hash of the signed version; a witness is optional."""
    if not by.strip():
        raise ValidationError("--by: the name of the person signing", code="SIGNER_MISSING")
    folder = home.entry_dir(entry)
    with lock(folder):
        doc = _read(entry)
        if doc.get("signed"):
            raise ValidationError(f"entry {entry!r} is already signed", code="ENTRY_SIGNED")
        doc["signed"] = {"by": by.strip(), "at": now().isoformat(), "hash": doc["hash"],
                         **({"witness": witness.strip()} if witness and witness.strip() else {})}
        atomic_write_json(folder / "entry.json", doc, private=True)
        append_jsonl(folder / "history.jsonl", {"version": doc["version"], "saved_at": doc["signed"]["at"],
                                                "status": EntryStatus.SIGNED.value, "hash": doc["hash"], "signed_by": by.strip()})
    return {**_summary(doc), "signed": doc["signed"]}


def attach(entry: str, file: str, name: str | None = None) -> dict[str, Any]:
    """Copy a gel photo, micrograph, plate export or trace into the entry's files/ (never moved, never overwritten)."""
    src = Path(file)
    doc = _read(entry)
    if doc.get("signed"):
        raise ValidationError(f"entry {entry!r} is signed: attach to the entry that amends it", code="ENTRY_SIGNED")
    if not src.is_file():
        raise NotFound(f"{file} is not a file", code="FILE_NOT_FOUND")
    if src.name.startswith(".") or SECRET_DIRS & set(src.resolve().parts):
        raise ValidationError(f"{file} is a hidden file or sits in a folder of keys: not kept with an entry", code="FILE_REFUSED")
    target = name or src.name
    if Path(target).suffix.lower() not in FILE_SUFFIXES:
        raise ValidationError(f"{target}: kept types are {', '.join(sorted(FILE_SUFFIXES))}", code="FILE_TYPE")
    cap = FCS_BYTES if target.lower().endswith(".fcs") else FILE_BYTES
    if src.stat().st_size > cap:
        raise ValidationError(f"{target} is over {cap // 2**20} MB", code="FILE_TOO_LARGE")
    dest = safe_join(home.entry_dir(entry) / "files", target)
    if dest.exists():
        raise ValidationError(f"{target} is already kept with {entry!r}", code="FILE_EXISTS", hint="give --name")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    listed = target in doc["entry"].get("files", [])
    return {"entry": entry, "file": target, "bytes": dest.stat().st_size, "listed": listed,
            "hint": "" if listed else "add it to the entry's files and save"}


def bank() -> dict[str, Any]:
    """`journal bank`: the cell bank across the journal."""
    return cellbank.bank(entries())


def template(kind: str) -> dict[str, Any]:
    """`journal template --kind K`: a starter entry for that kind, to fill in and save."""
    return starter(ExperimentKind(kind))
