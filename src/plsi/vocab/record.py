"""The record vocabulary: events and observations, their codes and origins, the person's own facts, and the
map coordinates and comparisons derived from them."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "EventType",
    "ObservationKind",
    "ClinicalStatus",
    "CodeSystem",
    "OriginKind",
    "ExtensionKind",
    "TimeBasis",
    "Sex",
    "Ethnicity",
    "LabFlag",
    "Relation",
    "CoordinateKind",
    "ValueStatus",
    "Comparator",
    "DeriveEngine",
    "MatchKind",
    "Direction",
    "HevySetType",
]


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


class Ethnicity(StrEnum):
    EUROPEAN = "european"
    AFRICAN = "african"
    MIDDLE_EASTERN = "middle_eastern"
    SOUTH_ASIAN = "south_asian"
    EAST_ASIAN = "east_asian"
    SOUTHEAST_ASIAN = "southeast_asian"
    LATIN_AMERICAN = "latin_american"
    OTHER = "other"


class LabFlag(StrEnum):
    """The lab's own mark on a result, as printed (H, L, HH/LL or critical, A or *)."""

    HIGH = "high"
    LOW = "low"
    CRITICAL = "critical"
    ABNORMAL = "abnormal"


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


class ValueStatus(StrEnum):
    PRESENT = "present"
    STALE = "stale"
    MISSING = "missing"
    ERROR = "error"


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


class HevySetType(StrEnum):
    """A set in a Hevy routine, in Hevy's words."""

    WARMUP = "warmup"
    NORMAL = "normal"
    FAILURE = "failure"
    DROPSET = "dropset"
