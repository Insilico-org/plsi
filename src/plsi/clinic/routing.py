"""Routing downloaded Drive files to the right patient and the sync ledger. `clinic sync` routes each file by its
inbox folder id, never by contents, and only while that patient is active; it skips files already taken in and moves
the rest into <PLSI_HOME>/inbox/<label>/. Every outcome is a line of <PLSI_HOME>/work/panel/synced.jsonl. `clinic
check` reports, for every patient with folders, the sharing each needs and the files still waiting for intake, plus
every roster problem; with `--drive` it also asks Drive who can open each folder (service account).
"""

from __future__ import annotations

import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from plsi import clock
from plsi.clinic.drive import DRIVE_ID, FOLDER, Drive
from plsi.clinic.records import ACCESS, checked_rows, panel_dir, problems, rows, sharing_problems, shown
from plsi.errors import NetworkError, ValidationError
from plsi.files import append_jsonl, load_json, read_jsonl, sha256_file
from plsi.life.store import EventStore
from plsi.paths import is_valid_id, plsi_home, safe_join
from plsi.vocab import PatientAccess, RosterStatus, SyncStatus

SUFFIX_RE = re.compile(r"^\.[a-z0-9]{1,10}$")


def ledger() -> list[dict[str, Any]]:
    return read_jsonl(panel_dir() / "synced.jsonl")


def record(entry: dict[str, Any]) -> dict[str, Any]:
    entry = {**entry, "at": clock.now().isoformat()}
    append_jsonl(panel_dir() / "synced.jsonl", entry)
    return entry


def waiting(label: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Files taken in for `label` that are still in its inbox and that no recorded observation came from."""
    recorded = {e.payload.origin.file_sha256 for e in EventStore(label).observations()}
    folder = plsi_home() / "inbox" / label
    out: dict[str, dict[str, Any]] = {}  # by file name: a return to an earlier version points at the same file
    for e in entries:
        if e.get("status") == SyncStatus.NEW and e["label"] == label and e["sha256"] not in recorded and (folder / e["path_name"]).is_file():
            out[e["path_name"]] = {"file": e["file"], "at": e["at"], "path": str(folder / e["path_name"])}
    return list(out.values())


def check(drive: bool = False) -> dict[str, Any]:
    """Every patient with Drive folders, the sharing each folder needs, the files still waiting for intake, and every
    roster problem; `drive` also asks Drive who can open each folder (service account)."""
    found, entries = rows(), ledger()
    fatal, held = problems(found)
    patients = []
    for r in found:
        if not (r.get("inbox") or r.get("shared_folder")):
            continue
        label = r.get("label")
        patients.append({"label": label, "shown": shown(r), "status": r.get("status"),
                         "patient_access": r.get("patient_access", PatientAccess.NONE.value),
                         "sharing": [{"folder": r[k], "role": k, "patient_access": a}
                                     for k, a in ACCESS.items() if r.get(k)],
                         "waiting": [] if label in held or not is_valid_id(str(label)) else waiting(label, entries)})
    out: dict[str, Any] = {"patients": patients, "problems": fatal + [f"{k}: {v}" for k, v in held.items()]}
    if drive:
        out["drive"] = audit(found)
        out["problems"] += out["drive"].pop("problems")
    return out


def audit(found: list[dict[str, Any]]) -> dict[str, Any]:
    """Who can open each patient folder besides the drive's members, against the row: nobody before the patient is
    invited, then exactly that person with the folder's role."""
    d = Drive()
    out = {"service_account": d.email, **d.about(), "problems": []}
    for r in found:
        for key in ACCESS:
            if not r.get(key):
                continue
            try:
                wrong = sharing_problems(d.direct_access(r[key]), key, r)
            except NetworkError as exc:
                wrong = [f"cannot be read ({exc.status or exc.code})"]
            except ValidationError:
                continue  # not a Drive id: `clinic check` lists it among the roster problems
            out["problems"] += [f"{r['label']} {key}: {w}" for w in wrong]
    return out


def pull(found: list[dict[str, Any]], held: dict[str, str], entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Download every file not handled before from each active patient's inbox. A file is skipped when the ledger
    already has its id with the same checksum or modified time. Returns (listing items, failures)."""
    d = Drive()
    known = {(e["file"], v) for e in entries if e.get("status") in (SyncStatus.NEW, SyncStatus.DUPLICATE)
             for v in (e.get("md5"), e.get("modified")) if v}
    work = panel_dir() / "download"
    items, failed = [], []
    for r in found:
        if r.get("status") != RosterStatus.ACTIVE or not r.get("inbox") or r.get("label") in held:
            continue
        try:
            children = d.children(r["inbox"])
        except NetworkError as exc:
            failed.append({"label": r["label"], "why": f"inbox cannot be listed ({exc.status or exc.code}); re-share it"})
            continue
        for f in children:
            if f.get("mimeType") == FOLDER:
                continue
            if (f["id"], f.get("md5Checksum")) in known or (f["id"], f.get("modifiedTime")) in known:
                continue
            try:
                path = d.download(f, work)
            except (NetworkError, ValidationError) as exc:
                failed.append({"label": r["label"], "file": f["id"], "why": f"cannot be downloaded ({exc.code}); the physician downloads it by hand"})
                continue
            items.append({"folder": r["inbox"], "file": f["id"], "path": str(path),
                          "md5": f.get("md5Checksum"), "modified": f.get("modifiedTime")})
    return items, failed


def sync(file: str | None = None) -> dict[str, Any]:
    """Route downloaded Drive files into <PLSI_HOME>/inbox/<label>/: from `file` ([{folder, file, path}], the agent's
    connector) or, without it, pulled from every active inbox with the service account.

    Returns {new: [{label, path, document, revised}], duplicate, held, unrouted, failed, notice}; `notice` has one
    line per patient with new or failed files (handle and label, counts only), for the physician. A file is routed
    only from a patient's own inbox and only while that patient is active. The same version again, or the same content under
    another file id, is a duplicate; a known file id with other content (also a return to an earlier version) is
    `revised` (feed it to `plsi revise --document <file id>`).
    """
    found, held = checked_rows()
    entries = ledger()
    out: dict[str, list[Any]] = {s: [] for s in SyncStatus if s != SyncStatus.PUBLISHED}
    if file is None:
        items, failed = pull(found, held, entries)
        out[SyncStatus.FAILED] += [record({"status": SyncStatus.FAILED, **f}) for f in failed]
    else:
        items = load_json(file)
        if not isinstance(items, list):
            raise ValidationError("the listing must be a list of {folder, file, path}")
    inbox = {r["inbox"]: r for r in found if r.get("inbox")}
    shared = {r["shared_folder"] for r in found if r.get("shared_folder")}
    last: dict[str, str] = {}
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in entries:
        if e.get("status") == SyncStatus.NEW:
            last[e["file"]] = e["sha256"]
            seen[(e["label"], e["sha256"])].add(e["file"])
    for item in items:
        status, entry = _route(item, inbox, shared, held, last, seen)
        out[status].append(entry)
    new = Counter(e["label"] for e in out[SyncStatus.NEW])
    failed = Counter(e.get("label", "unknown") for e in out[SyncStatus.FAILED])
    by_label = {r.get("label"): r for r in found}
    out["notice"] = []
    for label in sorted(set(new) | set(failed)):
        counts = [f"{new[label]} new file(s)"] * bool(new[label]) + [f"{failed[label]} failed"] * bool(failed[label])
        out["notice"].append(f"{shown(by_label.get(label, {'label': label}))}: {', '.join(counts)}")
    return out


def _route(item: Any, inbox: dict[str, dict[str, Any]], shared: set[str], held: dict[str, str],
           last: dict[str, str], seen: dict[tuple[str, str], set[str]]) -> tuple[SyncStatus, dict[str, Any]]:
    folder, file_id, path = (item.get(k) for k in ("folder", "file", "path")) if isinstance(item, dict) else (None,) * 3
    drive_meta = {k: item[k] for k in ("md5", "modified") if isinstance(item, dict) and item.get(k)}
    if not (isinstance(file_id, str) and DRIVE_ID.fullmatch(file_id) and isinstance(path, str) and Path(path).is_file()):
        return SyncStatus.FAILED, record({"status": SyncStatus.FAILED, "file": file_id if isinstance(file_id, str) else None,
                                 "why": "needs a Drive file id and the path of the downloaded file"})
    row = inbox.get(folder)
    size = item.get("size")  # Drive's size, when the agent passes it: a damaged download is never taken in
    if size is not None and str(size) != str(Path(path).stat().st_size):
        return SyncStatus.FAILED, record({"status": SyncStatus.FAILED, "file": file_id, **({"label": row["label"]} if row else {}),
                                 "why": "the download's size differs from Drive's; download it again"})
    if row is None:
        why = "a patient's shared folder is for the physician's files only" if folder in shared else "not a patient inbox"
        return SyncStatus.UNROUTED, record({"status": SyncStatus.UNROUTED, "file": file_id, "why": why, **drive_meta})
    label = row["label"]
    if label in held or row["status"] != RosterStatus.ACTIVE:
        return SyncStatus.HELD, record({"status": SyncStatus.HELD, "file": file_id, "label": label, "why": held.get(label, row["status"]), **drive_meta})
    sha = sha256_file(Path(path))
    if sha == last.get(file_id) or seen[(label, sha)] - {file_id}:
        return SyncStatus.DUPLICATE, record({"status": SyncStatus.DUPLICATE, "file": file_id, "label": label, "sha256": sha, **drive_meta})
    suffix = Path(path).suffix.lower()
    name = sha[:12] + (suffix if SUFFIX_RE.match(suffix) else "")
    dest = safe_join(plsi_home(), "inbox", label, name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():  # back to a version taken in before: the same bytes are already there
        Path(path).unlink()
    else:
        shutil.move(path, dest)
    revised = file_id in last
    last[file_id] = sha
    seen[(label, sha)].add(file_id)
    record({"status": SyncStatus.NEW, "file": file_id, "label": label, "sha256": sha, "path_name": name, **drive_meta})
    return SyncStatus.NEW, {"label": label, "path": str(dest), "document": file_id, "revised": revised}
