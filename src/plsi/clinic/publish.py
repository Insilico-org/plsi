"""What the physician's service account writes on the clinic shared drive (plsi.clinic.drive; skill panel/clinic).

`clinic setup` makes a patient's two folders, shared with nobody; `clinic share` invites the patient to them;
`clinic publish` puts a report the physician approved into the patient's shared folder. A patient's email is used
only for the share and never stored or returned.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from plsi import clock
from plsi.clinic import roster
from plsi.clinic.drive import Drive
from plsi.errors import ValidationError
from plsi.files import sha256_file
from plsi.paths import instance_dir, safe_join
from plsi.vocab import PatientAccess, SyncStatus

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_SAME_DAY = 99  # reports published to one patient on one day


def _manager() -> Drive:
    d = Drive()
    if not d.about()["manager"]:
        raise ValidationError("the service account is not a Manager of the shared drive", code="DRIVE_NOT_MANAGER",
                              hint=f"add {d.email} as Manager of the shared drive")
    return d


def setup(patient: str) -> dict[str, Any]:
    """Create `PLSI <label> inbox` and `PLSI <label> shared` on the shared drive, shared with nobody yet (only the
    drive's members, the physician, can open them); each id goes into the roster row as soon as it exists."""
    found = roster.rows()
    r = roster.patient_row(found, patient)
    if r.get("inbox") or r.get("shared_folder"):
        raise ValidationError(f"{patient} already has clinic folders", hint="plsi clinic check --drive")
    d = _manager()
    r["patient_access"] = PatientAccess.NONE.value
    for key, name in roster.NAMES.items():
        r[key] = d.folder(f"PLSI {patient} {name}")
        roster.save_rows(found)  # a folder made is never lost from the row, even when the next one fails
    return {"label": patient, "inbox": r["inbox"], "shared_folder": r["shared_folder"], "patient_access": PatientAccess.NONE.value}


def share(patient: str, email: str) -> dict[str, Any]:
    """Share both folders with the patient (inbox Editor, shared Viewer; Drive emails the invitation), check that the
    patient is the only person on each, and keep their permission id. The address is used here only, never kept."""
    if not EMAIL_RE.fullmatch(email):
        raise ValidationError("not an email address")
    found = roster.rows()
    r = roster.patient_row(found, patient)
    if not (r.get("inbox") and r.get("shared_folder")):
        raise ValidationError(f"{patient} has no clinic folders yet", hint=f"plsi clinic setup --patient {patient}")
    if r.get("patient_access") == PatientAccess.SHARED:
        raise ValidationError(f"{patient}'s folders are shared already", hint="plsi clinic check --drive")
    d = _manager()
    ids = {d.share(r[key], email, access) for key, access in roster.ACCESS.items()}
    if len(ids) != 1:
        raise ValidationError("Drive gave the two shares different people", code="DRIVE_SHARING",
                              hint="open both folders in Drive and check who they are shared with")
    r |= {"patient_access": PatientAccess.SHARED.value, "patient_id": ids.pop()}
    roster.save_rows(found)
    wrong = {key: roster.sharing_problems(d.direct_access(r[key]), key, r) for key in roster.ACCESS}
    if any(wrong.values()):
        raise ValidationError("the folders are shared beyond the patient: " + "; ".join(
            f"{k}: {', '.join(v)}" for k, v in wrong.items() if v), code="DRIVE_SHARING",
            hint="open the folder in Drive, remove everyone but the patient, then plsi clinic check --drive")
    return {"label": patient, "patient_access": PatientAccess.SHARED.value, "folders": roster.ACCESS}


def publish(patient: str, file: str, as_of: str) -> dict[str, Any]:
    """Upload one approved PDF report of `patient` (it must be in that patient's own reports folder, which is how a
    report for another patient is refused) to the patient's shared folder, never over an earlier file, and set the
    row's `reviewed` to the report's as-of date."""
    if not roster.DATE_RE.fullmatch(as_of):
        raise ValidationError("--as-of must be YYYY-MM-DD, the report's as-of date")
    found = roster.rows()
    row = roster.patient_row(found, patient)
    if not row.get("shared_folder") or row.get("patient_access") != PatientAccess.SHARED:
        raise ValidationError(f"{patient}'s shared folder is not shared with them yet", hint="plsi clinic share")
    path = Path(file).resolve()
    reports = safe_join(instance_dir(patient), "reports")
    if path.suffix.lower() != ".pdf" or path.parent != reports or not path.is_file():
        raise ValidationError(f"only a PDF from {patient}'s own reports folder can be published", code="NOT_THIS_PATIENT")
    d = Drive()
    taken = {c.get("name") for c in d.children(row["shared_folder"])}
    base = f"{patient} report {clock.now().date().isoformat()}"
    name = next((n for i in range(1, MAX_SAME_DAY + 1) if (n := base + (f" ({i})" if i > 1 else "") + ".pdf") not in taken),
                None)
    if name is None:
        raise ValidationError(f"{MAX_SAME_DAY} reports named {base} are in the shared folder already",
                              code="DRIVE_NAME_TAKEN", hint="move earlier reports out of the patient's shared folder")
    file_id = d.upload(row["shared_folder"], path, name)
    roster.record({"status": SyncStatus.PUBLISHED, "file": file_id, "label": patient, "sha256": sha256_file(path), "name": name})
    row["reviewed"] = as_of
    roster.save_rows(found)
    return {"label": patient, "name": name, "file": file_id, "reviewed": as_of}
