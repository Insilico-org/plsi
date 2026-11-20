"""The clinic vocabulary: patient folders and their sharing, the panel roster, and the sync ledger."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["PatientAccess", "RosterStatus", "ClinicFolder", "SyncStatus"]


class PatientAccess(StrEnum):
    """Whether a patient's clinic folders are shared with the patient yet (roster row `patient_access`)."""

    NONE = "none"  # the physician's own folders so far: nobody else may open them
    SHARED = "shared"  # exactly the invited patient, inbox Editor and shared folder Viewer


class RosterStatus(StrEnum):
    """A patient's row on the physician's panel (<PLSI_HOME>/work/panel/roster.json, skill panel/roster)."""

    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class ClinicFolder(StrEnum):
    """A patient's clinic folder by the last word of its name, `PLSI <label> <name>` (`clinic sharing --folder`)."""

    INBOX = "inbox"  # roster key `inbox`: the patient uploads
    SHARED = "shared"  # roster key `shared_folder`: the patient reads


class SyncStatus(StrEnum):
    """A line of the clinic ledger, <PLSI_HOME>/work/panel/synced.jsonl."""

    NEW = "new"
    DUPLICATE = "duplicate"
    HELD = "held"
    UNROUTED = "unrouted"
    FAILED = "failed"
    PUBLISHED = "published"
