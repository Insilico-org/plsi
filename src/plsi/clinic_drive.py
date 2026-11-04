"""The clinic folders on the physician's shared drive, through the service account (plsi.drive; skill panel/clinic).

`clinic setup` makes a patient's two folders, shared with nobody; `clinic share` invites the patient to them;
`clinic sync` pulls what patients uploaded; `clinic publish` puts a report the physician approved into the patient's
shared folder. A patient's email is used only for the share and never stored or returned.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from plsi import clinic
from plsi.drive import Drive
from plsi.errors import NetworkError, ValidationError
from plsi.files import sha256_file
from plsi.paths import instance_dir, safe_join
from plsi.vocab import PatientAccess, RosterStatus

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def drive_info() -> dict[str, Any]:
    d = Drive()
    return {"service_account": d.email, **d.about()}


def _manager() -> Drive:
    d = Drive()
    if not d.about()["manager"]:
        raise ValidationError("the service account is not a Manager of the shared drive", code="DRIVE_NOT_MANAGER",
                              hint=f"add {d.email} as Manager of the shared drive")
    return d


def setup(patient: str) -> dict[str, Any]:
    """Create `PLSI <label> inbox` and `PLSI <label> shared` on the shared drive, shared with nobody yet (only the
    drive's members, the physician, can open them); each id goes into the roster row as soon as it exists."""
    found = clinic.rows()
    r = clinic.patient_row(found, patient)
    if r.get("inbox") or r.get("shared_folder"):
        raise ValidationError(f"{patient} already has clinic folders", hint="plsi clinic check --drive")
    d = _manager()
    r["patient_access"] = PatientAccess.NONE.value
    for key, name in clinic.NAMES.items():
        r[key] = d.folder(f"PLSI {patient} {name}")
        clinic.save_rows(found)  # a folder made is never lost from the row, even when the next one fails
    return {"label": patient, "inbox": r["inbox"], "shared_folder": r["shared_folder"], "patient_access": "none"}


def share(patient: str, email: str) -> dict[str, Any]:
    """Share both folders with the patient (inbox Editor, shared Viewer; Drive emails the invitation), check that the
    patient is the only person on each, and keep their permission id. The address is used here only, never kept."""
    if not EMAIL_RE.match(email):
        raise ValidationError("not an email address")
    found = clinic.rows()
    r = clinic.patient_row(found, patient)
    if not (r.get("inbox") and r.get("shared_folder")):
        raise ValidationError(f"{patient} has no clinic folders yet", hint=f"plsi clinic setup --patient {patient}")
    if r.get("patient_access") == PatientAccess.SHARED:
        raise ValidationError(f"{patient}'s folders are shared already", hint="plsi clinic check --drive")
    d = _manager()
    ids = {d.share(r[key], email, access) for key, access in clinic.ACCESS.items()}
    if len(ids) != 1:
        raise ValidationError("Drive gave the two shares different people", code="DRIVE_SHARING",
                              hint="open both folders in Drive and check who they are shared with")
    r |= {"patient_access": PatientAccess.SHARED.value, "patient_id": ids.pop()}
    clinic.save_rows(found)
    wrong = {key: clinic.sharing_problems(d.direct_access(r[key]), key, r) for key in clinic.ACCESS}
    if any(wrong.values()):
        raise ValidationError("the folders are shared beyond the patient: " + "; ".join(
            f"{k}: {', '.join(v)}" for k, v in wrong.items() if v), code="DRIVE_SHARING",
            hint="open the folder in Drive, remove everyone but the patient, then plsi clinic check --drive")
    return {"label": patient, "patient_access": "shared", "folders": clinic.ACCESS}


def audit(found: list[dict[str, Any]]) -> dict[str, Any]:
    """Who can open each patient folder besides the drive's members, against the row: nobody before the patient is
    invited, then exactly that person with the folder's role."""
    out = {**drive_info(), "problems": []}
    d = Drive()
    for r in found:
        for key in clinic.ACCESS:
            if not r.get(key):
                continue
            try:
                wrong = clinic.sharing_problems(d.direct_access(r[key]), key, r)
            except NetworkError as exc:
                wrong = [f"cannot be read ({exc.status or exc.code})"]
            out["problems"] += [f"{r['label']} {key}: {w}" for w in wrong]
    return out


def pull(found: list[dict[str, Any]], held: dict[str, str], entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Download every file not handled before from each active patient's inbox. A file is skipped when the ledger
    already has its id with the same checksum or modified time. Returns (listing items, failures)."""
    d = Drive()
    known = {(e["file"], v) for e in entries if e.get("status") in ("new", "duplicate")
             for v in (e.get("md5"), e.get("modified")) if v}
    work = clinic.panel_dir() / "download"
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
            if f.get("mimeType") == "application/vnd.google-apps.folder":
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


def publish(patient: str, file: str, as_of: str) -> dict[str, Any]:
    """Upload one approved PDF report of `patient` (it must be in that patient's own reports folder, which is how a
    report for another patient is refused) to the patient's shared folder, never over an earlier file, and set the
    row's `reviewed` to the report's as-of date."""
    if not clinic.DATE_RE.match(as_of):
        raise ValidationError("--as-of must be YYYY-MM-DD, the report's as-of date")
    found = clinic.rows()
    row = clinic.patient_row(found, patient)
    if not row.get("shared_folder") or row.get("patient_access") != PatientAccess.SHARED:
        raise ValidationError(f"{patient}'s shared folder is not shared with them yet", hint="plsi clinic share")
    path = Path(file).resolve()
    reports = safe_join(instance_dir(patient), "reports")
    if path.suffix.lower() != ".pdf" or path.parent != reports or not path.is_file():
        raise ValidationError(f"only a PDF from {patient}'s own reports folder can be published", code="NOT_THIS_PATIENT")
    d = Drive()
    names = {c.get("name") for c in d.children(row["shared_folder"])}
    base = f"{patient} report {date.today().isoformat()}"
    name = next(n for i in range(1, 100) if (n := base + (f" ({i})" if i > 1 else "") + ".pdf") not in names)
    file_id = d.upload(row["shared_folder"], path, name)
    clinic.record({"status": "published", "file": file_id, "label": patient, "sha256": sha256_file(path), "name": name})
    row["reviewed"] = as_of
    clinic.save_rows(found)
    return {"label": patient, "name": name, "file": file_id, "reviewed": as_of}
