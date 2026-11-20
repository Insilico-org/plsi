"""The physician's clinic (skill panel/clinic): each patient on the panel has two Drive folders, an inbox the patient
uploads to and a shared folder the patient reads. Both ids live in the patient's roster row. `clinic sync` routes
downloaded files to the right patient by folder id, never by file contents, and skips files already taken in; Drive
itself is read with the service account (plsi.clinic.drive: `clinic check --drive`, `clinic sync` without `--file`) or
by the agent's own connector (`--file`, `clinic link`, `clinic sharing`). Every outcome is a line of
<PLSI_HOME>/work/panel/synced.jsonl. A patient's email is never stored: the row keeps `patient_id`, the opaque Drive
permission id of the person invited, so a later check knows them.

The roster rows and their checks live in `records`; routing synced files and the ledger live in `routing`. This
module re-exports the clinic commands and the names other clinic modules read.
"""

from __future__ import annotations

from plsi.clinic.records import (
    ACCESS,
    DATE_RE,
    HANDLE_MAX,
    NAMES,
    checked_rows,
    link,
    panel_dir,
    patient_row,
    problems,
    rows,
    save_rows,
    sharing,
    sharing_problems,
    shown,
)
from plsi.clinic.routing import (
    SUFFIX_RE,
    audit,
    check,
    ledger,
    pull,
    record,
    sync,
    waiting,
)

__all__ = [
    "ACCESS",
    "DATE_RE",
    "HANDLE_MAX",
    "NAMES",
    "SUFFIX_RE",
    "audit",
    "check",
    "checked_rows",
    "ledger",
    "link",
    "panel_dir",
    "patient_row",
    "problems",
    "pull",
    "record",
    "rows",
    "save_rows",
    "sharing",
    "sharing_problems",
    "shown",
    "sync",
    "waiting",
]
