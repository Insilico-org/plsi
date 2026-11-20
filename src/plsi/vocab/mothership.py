"""The Mothership vocabulary: reference kinds, what an enrolled user contributes, enrollment and receipt states,
the messages and project actions sent to the relay, publication status, professional scopes and analyses."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ReferenceKind",
    "ContributionKind",
    "PandaclawCatalog",
    "EnrollmentStatus",
    "ReceiptState",
    "MothershipMessage",
    "ProjectAction",
    "DraftKind",
    "PublicationStatus",
    "RegistryItemKind",
    "ProfessionalScope",
    "AnalysisOp",
    "HypothesisDirection",
    "WithdrawalRequest",
]


class ReferenceKind(StrEnum):
    CODE_SYSTEM = "code_system"
    TERMINOLOGY_API = "terminology_api"
    EVIDENCE_SOURCE = "evidence_source"
    LABEL_SOURCE = "label_source"
    CLOCK_LIBRARY = "clock_library"
    MODEL = "model"
    ORACLE = "oracle"
    PAPER = "paper"
    DATASET = "dataset"
    JOURNAL = "journal"
    DIGEST = "digest"  # curated paper digests, event calendars, industry reports
    BASE_RATE = "base_rate"  # population mortality, incidence and prevalence tables: absolute risks for predictions
    EDUCATION = "education"
    DEVICE_DATA = "device_data"  # wearable and device data platforms (wearables/import)
    CONTACT = "contact"  # where PLSI may send data (the Longevity Mothership relay)
    DIRECTORY = "directory"  # public practitioner directories and licence registers (navigator/physicians)


class ContributionKind(StrEnum):
    """What an enrolled user shares with the Longevity Mothership (plsi mothership join)."""

    STATES = "states"  # published state documents, values kept, dates to the month
    LIFE_EVENTS = "life_events"  # recorded life events (conditions, treatments, lifestyle, symptoms), dates to the year
    SCORES = "scores"  # calibration of scored predictions, cells of at least 5 scores


class PandaclawCatalog(StrEnum):
    """Which PandaClaw skill list `plsi oracle pandaclaw-skills` reads."""

    RECOMMENDED = "recommended"
    ALL = "all"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"


class ReceiptState(StrEnum):
    STORED = "stored"
    DELETED = "deleted"
    REFUSED = "refused"
    PENDING = "pending"
    NEVER_CONFIRMED = "never_confirmed"
    BEFORE_RECEIPTS = "before_receipts"


class MothershipMessage(StrEnum):
    """The `kind` of a file sent to the Longevity Mothership."""

    CONTRIBUTION = "plsi_contribution"  # install token
    WITHDRAWAL = "plsi_withdrawal"  # install token
    RESEARCH_NOTE = "plsi_research_note"  # by email only, never the relay
    REGISTRY_UPDATE = "plsi_registry_update"  # install token
    PREREGISTRATION = "plsi_preregistration"  # professional token
    FINDING = "plsi_finding"  # professional token
    FEEDBACK = "plsi_feedback"  # by email only, never the relay
    PROJECT_INVITE = "plsi_project_invite"  # by email only; the project owner grants collaborators Drive writer


class ProjectAction(StrEnum):
    """What a plsi_project_invite asks the Mother to do with the named collaborators on projects/<uuid>/."""

    INVITE = "invite"  # grant Drive writer and add to the registry invitees[]
    REVOKE = "revoke"  # remove Drive writer and drop from the registry invitees[]


class DraftKind(StrEnum):
    """A `mothership mine` draft that is not a project access change: a research note, settled by its own
    package_hash rather than by the collaborators it names."""

    NOTE = "note"


class PublicationStatus(StrEnum):
    """Where an owner's Mothership research project stands in `mothership mine`."""

    # member order is significant: `mine` sorts projects by it
    PUBLISHED = "published"  # the public projects table lists it
    AWAITING = "awaiting"  # a note for it was sent; the table, read just now, does not list it yet
    SENT = "sent"  # a note for it was sent; the table could not be read, so whether it is published is unknown
    DRAFTED = "drafted"  # a note or invite was drafted here; nothing for it is recorded as sent


class RegistryItemKind(StrEnum):
    PHYSICIAN = "physician"
    METHOD = "method"


class ProfessionalScope(StrEnum):
    """Scopes of a Mothership professional token."""

    RELEASES_READ = "releases:read"
    FINDINGS_READ = "findings:read"  # also gates /public/projects (the researcher table)
    FINDINGS_SUBMIT = "findings:submit"


class AnalysisOp(StrEnum):
    """Analyses of a Mothership data release (`plsi mothership analyze`)."""

    COMPARE_GROUPS = "compare_groups"  # Welch's t-test between two pooled groups of cells
    AGE_TREND = "age_trend"  # weighted least squares of cell means on the age-band midpoint


class HypothesisDirection(StrEnum):
    """The direction a preregistered effect is expected to take."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    TWO_SIDED = "two_sided"


class WithdrawalRequest(StrEnum):
    DELETE_ALL = "delete_all"
    STOP = "stop"
