"""Every enum in PLSI. Nothing is enumerated inline elsewhere."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class EvidenceClass(StrEnum):
    # member order is significant: strongest first (rank 4 .. 0)
    EVIDENCE_BACKED = "evidence_backed"
    RULE_DERIVED = "rule_derived"
    MODEL_DERIVED = "model_derived"
    HYPOTHESIS_ONLY = "hypothesis_only"
    UNKNOWN = "unknown"

    @property
    def rank(self) -> int:
        members = list(EvidenceClass)
        return len(members) - 1 - members.index(self)

    @classmethod
    def top(cls, values: Iterable[EvidenceClass]) -> EvidenceClass | None:
        """The strongest of values (None when there are none)."""
        return max(values, key=lambda e: e.rank, default=None)


class CorrespondenceType(StrEnum):
    TERMINOLOGY = "terminology"
    EXPERT = "expert"
    STATISTICAL = "statistical"
    MECHANISTIC = "mechanistic"
    VALIDATED = "validated"
    UNMAPPED = "unmapped"


class ClaimLevel(StrEnum):
    DESIGNED = "designed"
    INSTANTIATED = "instantiated"
    EXERCISED = "exercised"


class BotRole(StrEnum):
    """The PLSI team on Grok Bot; the roster (slug -> display name, core vs opt-in specialists, skills) is skills/shared/team.
    Every handoff has the orchestrator (PLSI) on one end; only PLSI talks to the user."""

    ORCHESTRATOR = "orchestrator"
    PROCESSOR = "processor"
    CONSULTANT = "consultant"
    NOSTRADAMUS = "nostradamus"
    CHALLENGER = "challenger"
    REVIEWER = "reviewer"
    CONTROLLER = "controller"
    MEMORYHOLE = "memoryhole"
    VISUALIZER = "visualizer"
    WEARABLES = "wearables"
    NUTRITIONIST = "nutritionist"
    COACH = "coach"
    SLEEP = "sleep"
    BIOHACKER = "biohacker"
    RESEARCHER = "researcher"
    EXPLORER = "explorer"
    NAVIGATOR = "navigator"
    SCOUT = "scout"
    PHARMA = "pharma"
    ENGINEER = "engineer"
    WRITER = "writer"
    PANEL = "panel"  # physician section (PLSI Clinic)
    VISITPREP = "visitprep"
    CLINEV = "clinev"
    LIAISON = "liaison"
    TARGETS = "targets"  # researcher section (PLSI Lab)
    LANDSCAPE = "landscape"
    ANALYST = "analyst"
    GRANTS = "grants"


class UserRole(StrEnum):
    """Who the user is to PLSI (`plsi role set`); picks the sections of the team that are set up."""

    INDIVIDUAL = "individual"
    PHYSICIAN = "physician"
    RESEARCHER = "researcher"


class HandoffKind(StrEnum):
    REQUEST = "request"  # orchestrator -> another bot: run a skill
    RESULT = "result"  # another bot -> orchestrator
    QUESTION = "question"  # another bot -> orchestrator: for the user (only the orchestrator asks the user)
    ANSWER = "answer"  # orchestrator -> the asking bot: the user's answers


class EventType(StrEnum):
    OBSERVATION = "observation"
    RETRACTION = "retraction"
    SCREENING = "screening"
    PLAN = "plan"
    PLAN_STATUS = "plan_status"
    PREDICTION_SCORE = "prediction_score"


class ObservationKind(StrEnum):
    MEASUREMENT = "measurement"
    MEDICATION = "medication"
    CONDITION = "condition"
    ALLERGY = "allergy"
    INTERVENTION = "intervention"
    SYMPTOM = "symptom"
    LIFESTYLE = "lifestyle"
    ARTIFACT = "artifact"
    NOTE = "note"
    GOAL = "goal"  # what the user wants to reach, e.g. "run 10 km"; resolved when reached or dropped
    PREFERENCE = "preference"  # standing choices and constraints: diet, budget band, schedule


class ClinicalStatus(StrEnum):
    ACTIVE = "active"
    STOPPED = "stopped"
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class CodeSystem(StrEnum):
    LOINC = "loinc"
    RXNORM = "rxnorm"
    SNOMED = "snomed"
    ICD10CM = "icd10cm"
    CPG = "cpg"
    FREE = "free"


class OriginKind(StrEnum):
    USER_UPLOAD = "user_upload"
    FHIR = "fhir"
    CSV = "csv"
    GROK_EXTRACTION = "grok_extraction"
    DEVICE = "device"
    METHYLATION = "methylation"
    EXTENSION = "extension"  # produced by an importer extension


class ExtensionKind(StrEnum):
    IMPORTER = "importer"  # Life: a new input format -> observations
    DERIVER = "deriver"  # Map: a new derived value (derive engine extension)
    EVIDENCE_SOURCE = "evidence_source"  # Policy: a new place to search for evidence


class TimeBasis(StrEnum):
    DOCUMENT = "document"
    USER_STATED = "user_stated"
    ASSUMED = "assumed"


class Sex(StrEnum):
    M = "M"
    F = "F"
    X = "X"
    UNKNOWN = "unknown"


class Relation(StrEnum):
    """Who an instance is, relative to the user. Instance names are neutral labels (mother, sample-1), never names."""

    SELF = "self"
    FAMILY = "family"
    OTHER = "other"
    SAMPLE = "sample"  # a story or test person, not a real one


class CoordinateKind(StrEnum):
    MEASURED = "measured"
    DERIVED = "derived"
    SET = "set"


class ExportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"


class ReportFormat(StrEnum):
    HTML = "html"
    PDF = "pdf"


class ValueStatus(StrEnum):
    PRESENT = "present"
    STALE = "stale"
    MISSING = "missing"
    ERROR = "error"


class Severity(StrEnum):
    # member order is significant: mildest first (rank 0 .. 2)
    NONE = "none"
    CAUTION = "caution"
    BLOCK = "block"

    @property
    def rank(self) -> int:
        return list(Severity).index(self)

    @classmethod
    def top(cls, values: Iterable[Severity]) -> Severity:
        """The most severe of values (none when there are none)."""
        return max(values, key=lambda s: s.rank, default=cls.NONE)


class ActionCategory(StrEnum):
    DRUG = "drug"
    SUPPLEMENT = "supplement"
    DIET = "diet"
    EXERCISE = "exercise"
    SLEEP = "sleep"
    TEST = "test"
    OTHER = "other"


class PlanState(StrEnum):
    PROPOSED = "proposed"
    ADOPTED = "adopted"
    COMPLETED = "completed"
    STOPPED = "stopped"
    SUPERSEDED = "superseded"


class PlanDecision(StrEnum):
    ADOPT = "adopt"
    CONTINUE = "continue"
    MODIFY = "modify"
    STOP = "stop"
    COMPLETE = "complete"


class PredictionTarget(StrEnum):
    LEVEL = "level"
    CHANGE_FROM_BASELINE = "change_from_baseline"


class ScoreStatus(StrEnum):
    SCORED = "scored"
    MISSED = "missed"
    VOID = "void"


class SourceKind(StrEnum):
    PMID = "pmid"
    DOI = "doi"
    NCT = "nct"
    LABEL = "label"
    EVIPEDIA = "evipedia"
    MODEL = "model"
    RULE = "rule"


class BlockType(StrEnum):
    MARKDOWN = "markdown"
    KV = "kv"
    TABLE = "table"
    TIMESERIES = "timeseries"
    LIST = "list"
    TIMELINE = "timeline"


# Small enums the spec writes inline in section 3/4/8/9; kept here so there is one vocabulary.


class Comparator(StrEnum):
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="


class DeriveEngine(StrEnum):
    NATIVE = "native"  # built-in formulas (plsi.map.derive)
    EXPR = "expr"  # a safe formula written in the map (plsi.map.formula)
    EXTENSION = "extension"  # an installed deriver extension (plsi.extensions); model = extension id
    BIOLEARN = "biolearn"


class MatchKind(StrEnum):
    CODE = "code"
    DERIVED = "derived"


class Direction(StrEnum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


class SourceStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    ERROR = "error"


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


class SearchSource(StrEnum):
    PUBMED = "pubmed"
    EUROPEPMC = "europepmc"
    CTGOV = "ctgov"
    OPENFDA = "openfda"
    EVIPEDIA = "evipedia"


# Source kinds that make a claim evidence_backed (ClaimInput coherence).
LITERATURE_SOURCE_KINDS = frozenset(
    {SourceKind.PMID, SourceKind.DOI, SourceKind.NCT, SourceKind.LABEL, SourceKind.EVIPEDIA}
)


# ---------------------------------------------------------------- Policy gates, due states, Mothership messages


class GateId(StrEnum):
    """Plan gates; the `rule` of a plan violation."""

    G1 = "G1"  # map exists and its projected state is current
    G2 = "G2"  # a fresh screening event for every action and the current care context
    G3 = "G3"  # screening outcome: block drops the action, caution needs an acknowledgement
    G4 = "G4"  # claim coherence (a parse error of the plan contract)
    G5 = "G5"  # every cited source verified
    G6 = "G6"  # actions supported by claims of the map's minimum evidence class
    G7 = "G7"  # predictions on predictable coordinates with a usable baseline
    G8 = "G8"  # supersedes a live plan


class DueState(StrEnum):
    """`plsi due`: a prediction whose score window is open."""

    DUE = "due"  # an eligible observation exists; `plsi score` will score it
    MISSED = "missed"  # the window closed without one
    AWAITING = "awaiting"  # the window is open, no eligible observation yet


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
    """The `kind` of a file sent to the Longevity Mothership (plsi-mothership contracts/WIRE.md)."""

    CONTRIBUTION = "plsi_contribution"  # install token
    WITHDRAWAL = "plsi_withdrawal"  # install token
    RESEARCH_NOTE = "plsi_research_note"  # by email only (WIRE §7), never the relay
    REGISTRY_UPDATE = "plsi_registry_update"  # install token
    PREREGISTRATION = "plsi_preregistration"  # professional token
    FINDING = "plsi_finding"  # professional token


class NoteKind(StrEnum):
    """The `kind` of an Explorer contribution.json (`plsi mothership note`)."""

    RESEARCH_NOTE = "research_note"
    REGISTRY_UPDATE = "registry_update"


class RegistryItemKind(StrEnum):
    PHYSICIAN = "physician"
    METHOD = "method"


class ProfessionalScope(StrEnum):
    """Scopes of a Mothership professional token."""

    RELEASES_READ = "releases:read"
    FINDINGS_READ = "findings:read"
    FINDINGS_SUBMIT = "findings:submit"


class ResearchItemKind(StrEnum):
    """The `kind` of an item in the research graph (<PLSI_HOME>/research, `plsi research index`)."""

    PROJECT = "project"  # the project's own page: its question, why it matters, what done looks like
    QUESTION = "question"
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"  # one source or result read, with its identifier
    NOTE = "note"  # a research note in the researcher/research shape, the unit sent to the Mothership


class ResearchStatus(StrEnum):
    OPEN = "open"  # not worked on yet
    ACTIVE = "active"
    PARKED = "parked"  # waits for something named in the item
    SUPPORTED = "supported"
    REFUTED = "refuted"  # kept: a refuted idea is not tried again
    READY = "ready"  # a note complete enough for PLSI Challenger (Note mode)
    SUBMITTED = "submitted"  # emailed to the Mothership
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RETIRE = "retire"  # duplicate, off-topic or obsolete: PLSI Memory Hole removes it (`plsi research retire`)


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
