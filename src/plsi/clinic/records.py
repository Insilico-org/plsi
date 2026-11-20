"""Roster rows and their checks: each patient on the panel has a row in <PLSI_HOME>/work/panel/roster.json with the
ids of the patient's two Drive folders, the opaque Drive permission id of the person invited (`patient_id`, so a
later check knows them without an email ever being stored) and the physician's own handle for the patient. The row
is read first by every clinic command, validated (`problems`), and the folder sharing a row expects is checked
against Drive's answer (`sharing_problems`).
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from plsi import role
from plsi.clinic.drive import DRIVE_ID
from plsi.errors import NotFound, ValidationError
from plsi.files import atomic_write_json, load_json
from plsi.paths import is_valid_id, plsi_home
from plsi.vocab import ClinicFolder, PatientAccess, RosterStatus

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ACCESS = {"inbox": "writer", "shared_folder": "reader"}  # roster key -> the patient's access once shared
NAMES = {"inbox": ClinicFolder.INBOX, "shared_folder": ClinicFolder.SHARED}  # roster key -> `PLSI <label> <name>`
HANDLE_MAX = 40  # the physician's own name for a patient, shown only to the physician


def _key(name: Any) -> str:
    """A label or handle as compared for collisions: case, spaces and dots ignored ("J.D." is "jd")."""
    return re.sub(r"[\s.]+", "", name).casefold() if isinstance(name, str) else ""


def shown(r: dict[str, Any]) -> str:
    """How the physician sees a patient: their handle with the label, or the label alone."""
    handle = r.get("handle")
    return f"{handle} ({r['label']})" if handle else str(r.get("label"))


def panel_dir() -> Path:
    return plsi_home() / "work" / "panel"


def rows() -> list[dict[str, Any]]:
    """The roster's rows; every clinic command reads them first, so a steward's account is refused here."""
    role.not_a_steward()
    path = panel_dir() / "roster.json"
    if not path.is_file():
        raise NotFound("no panel roster yet", code="ROSTER_NOT_FOUND", hint="add a patient first (skill panel/roster)")
    data = load_json(path)
    found = data.get("patients") if isinstance(data, dict) else data
    if not isinstance(found, list) or not all(isinstance(r, dict) for r in found):
        raise ValidationError("roster.json must be a list of patient rows")
    return found


def save_rows(updated: list[dict[str, Any]]) -> None:
    path = panel_dir() / "roster.json"
    data = load_json(path)
    atomic_write_json(path, {**data, "patients": updated} if isinstance(data, dict) else updated, private=True)


def checked_rows() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """(rows, {label: why} for patients whose files are held); ROSTER_INVALID when two patients could be confused."""
    found = rows()
    fatal, held = problems(found)
    if fatal:
        raise ValidationError("the roster has problems: " + "; ".join(fatal), code="ROSTER_INVALID", hint="plsi clinic check")
    return found, held


def patient_row(found: list[dict[str, Any]], patient: str, active: bool = True) -> dict[str, Any]:
    found_row = next((r for r in found if r.get("label") == patient), None)
    if found_row is None:
        raise NotFound(f"{patient} is not on the roster", code="NOT_ON_ROSTER", hint="skill panel/roster")
    if active and found_row.get("status") != RosterStatus.ACTIVE:
        raise ValidationError(f"{patient} is {found_row.get('status')}, not active")
    return found_row


def sharing_problems(grants: list[dict[str, Any]], key: str, r: dict[str, Any]) -> list[str]:
    """What is wrong with one patient folder's own grants ([{type, role, id?}]), given its row: never a link, domain
    or group share; nobody before the patient is invited; then exactly that person with the folder's role. The
    physician's own grant (owner, on the connector route) is theirs. Names no address."""
    out = [f"a {g.get('type')} share" for g in grants if g.get("type") in ("anyone", "domain", "group")]
    users = [g for g in grants if g.get("type") == "user" and g.get("role") != "owner"]
    if r.get("patient_access", PatientAccess.NONE) == PatientAccess.NONE:
        return out + [f"{len(users)} person(s) can open it, but the patient is not invited yet"] * bool(users)
    if len(users) != 1:
        return out + [f"{len(users)} people can open it; only the patient may"]
    if users[0].get("role") != ACCESS[key]:
        out.append(f"the patient is {users[0].get('role')}, not {ACCESS[key]}")
    if r.get("patient_id") and users[0].get("id") != r["patient_id"]:
        out.append("it is shared with someone other than the person invited")
    return out


def link(patient: str, inbox: str | None = None, shared: str | None = None, patient_id: str | None = None,
         reviewed: str | None = None) -> dict[str, Any]:
    """`clinic link` (connector or by hand): write a patient's folder ids, the invited person's Drive permission id
    (which marks the folders shared) and the as-of date of the last report the patient received into their row."""
    found = rows()
    r = patient_row(found, patient, active=False)
    for key, value in (("inbox", inbox), ("shared_folder", shared), ("patient_id", patient_id)):
        if value is None:
            continue
        if not DRIVE_ID.fullmatch(value):
            raise ValidationError(f"{key} is not a Drive id",
                                  hint="copy it from the folder's URL or the connector's answer")
        if key != "patient_id" and any(o is not r and value in (o.get("inbox"), o.get("shared_folder")) for o in found):
            raise ValidationError("that folder is another patient's; every patient folder is that patient's alone",
                                  code="FOLDER_TAKEN")
        r[key] = value
    if patient_id:
        r["patient_access"] = PatientAccess.SHARED.value
    r.setdefault("patient_access", PatientAccess.NONE.value)
    if reviewed is not None:
        if not DATE_RE.fullmatch(reviewed):
            raise ValidationError("reviewed must be YYYY-MM-DD, the report's as-of date")
        r["reviewed"] = reviewed
    save_rows(found)
    return {"label": patient, **{k: r.get(k) for k in ("inbox", "shared_folder", "patient_access", "reviewed")}}


def sharing(patient: str, folder: str, file: str = "-") -> dict[str, Any]:
    """`clinic sharing` (connector): check one folder's permissions as the connector returned them (Drive's
    `permissions` list, on stdin by default and never kept) against the patient's row."""
    key = {name: k for k, name in NAMES.items()}[ClinicFolder(folder)]
    r = patient_row(rows(), patient, active=False)
    data = load_json(file)
    found = data.get("permissions", data) if isinstance(data, dict) else data
    if not isinstance(found, list) or not all(isinstance(g, dict) for g in found):
        raise ValidationError("give Drive's permissions list: [{type, role, id}]")
    if r.get("patient_access") == PatientAccess.SHARED and not r.get("patient_id"):
        raise ValidationError(f"{patient}'s row has no patient_id",
                              hint="plsi clinic link --patient-id <permission id>")
    problems_found = sharing_problems(found, key, r)
    return {"label": patient, "folder": folder, "ok": not problems_found, "problems": problems_found}


def problems(found: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    """(roster-wide problems that stop a sync, {label: why} for patients whose files are held)."""
    fatal, held = [], {}
    uses = Counter(r.get(k) for r in found for k in ("inbox", "shared_folder") if r.get(k))
    names = Counter(n for r in found for n in {_key(r.get("label")), _key(r.get("handle"))} if n)
    for r in found:
        label = r.get("label")
        if not isinstance(label, str) or not is_valid_id(label):
            fatal.append(f"invalid label {label!r}")
            continue
        if not (plsi_home() / label / "subject.json").is_file():
            held[label] = f"no instance (plsi init --instance {label} --relation other)"
        elif r.get("status") not in {s.value for s in RosterStatus}:
            held[label] = f"status must be one of {', '.join(s.value for s in RosterStatus)}"
        if names[_key(label)] > 1:
            fatal.append(f"{label}: the label is used twice, or is another patient's handle")
        handle = r.get("handle")
        if isinstance(handle, str) and names[_key(handle)] > 1:
            fatal.append(f"{label}: handle {handle!r} is another patient's handle or label; each must name one patient")
        if handle is not None and not (isinstance(handle, str) and handle.isprintable()
                                       and 0 < len(handle) <= HANDLE_MAX):
            fatal.append(f"{label}: handle must be one line of at most {HANDLE_MAX} characters")
        if r.get("patient_access", PatientAccess.NONE) not in {a.value for a in PatientAccess}:
            fatal.append(f"{label}: patient_access must be one of {', '.join(a.value for a in PatientAccess)}")
        for key in ("inbox", "shared_folder"):
            folder = r.get(key)
            if folder is not None and (not isinstance(folder, str) or not DRIVE_ID.fullmatch(folder)):
                fatal.append(f"{label}: {key} is not a Drive folder id")
            elif folder is not None and uses[folder] > 1:
                fatal.append(f"{label}: {key} folder is used twice; every patient folder is that patient's alone")
    return fatal, held
