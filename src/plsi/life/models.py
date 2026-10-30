"""Life models: observations and the deidentified subject."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from plsi.events import register_payload
from plsi.life.deid import AGE_GROUP_90, PROFILE
from plsi.models import Code, EventId, Model, Sha256Hex, UtcTime
from plsi.vocab import ClinicalStatus, Comparator, EventType, ObservationKind, OriginKind, Relation, Sex, TimeBasis


class Origin(Model):
    """Provenance of an observation. Never a path or filename (deid profile plsi-limited-v1)."""

    kind: OriginKind
    file_sha256: Sha256Hex | None = None
    page: int | None = Field(default=None, ge=1)
    record_id: str | None = Field(default=None, max_length=128)


ORIGINAL_TEXT_MAX = 200


class ObservationInput(Model):
    kind: ObservationKind
    code: Code | None = None
    original_text: str = Field(min_length=1, max_length=ORIGINAL_TEXT_MAX)
    value_quantity: float | None = None
    value_text: str | None = None
    value_bool: bool | None = None
    value_comparator: Comparator | None = None
    unit: str | None = Field(default=None, max_length=64)
    effective_at: UtcTime
    effective_basis: TimeBasis = TimeBasis.DOCUMENT
    effective_end: UtcTime | None = None
    specimen: str | None = Field(default=None, max_length=64)
    clinical_status: ClinicalStatus | None = None
    dose: str | None = Field(default=None, max_length=200)  # as written; never leaves
    dose_quantity: float | None = Field(default=None, gt=0)  # structured dose, with dose_unit (UCUM); may be shared
    dose_unit: str | None = Field(default=None, min_length=1, max_length=64)
    fasting: bool | None = None
    repeat: bool = False
    origin: Origin

    @model_validator(mode="after")
    def _structure(self) -> ObservationInput:
        values = [self.value_quantity, self.value_text, self.value_bool]
        if sum(v is not None for v in values) != 1:
            raise ValueError("exactly one of value_quantity, value_text, value_bool is required")
        if self.value_comparator is not None and self.value_quantity is None:
            raise ValueError("value_comparator requires value_quantity")
        if (self.dose_quantity is None) != (self.dose_unit is None):
            raise ValueError("dose_quantity and dose_unit go together")
        if self.effective_end is not None and self.effective_end < self.effective_at:
            raise ValueError("effective_end is before effective_at")
        return self


class Observation(ObservationInput):
    """Stored observation: `unit` is UCUM-syntax-normalized, `unit_original` as reported. Values never converted."""

    unit_original: str | None = None


class RetractionInput(Model):
    reason: str = Field(min_length=1, max_length=500)


class Retraction(Model):
    target_event_id: EventId
    reason: str = Field(min_length=1, max_length=500)
    replacement_event_id: EventId | None = None


class Subject(Model):
    subject_id: Annotated[str, Field(pattern=r"^s_[0-9a-f]{12}$")]
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    age_group: Literal[AGE_GROUP_90] | None = None
    sex: Sex = Sex.UNKNOWN
    relation: Relation | None = None  # to the user; None when not given
    country: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None  # ISO 3166 alpha-3 of residence: life tables, base rates
    deid_profile: Literal[PROFILE] = PROFILE
    created_at: UtcTime

    @model_validator(mode="after")
    def _age(self) -> Subject:
        if self.age_group and self.birth_year is not None:
            raise ValueError("age_group 90+ requires birth_year null")
        return self


register_payload(EventType.OBSERVATION, Observation)
register_payload(EventType.RETRACTION, Retraction)
