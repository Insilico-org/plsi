"""Policy models: actions, screening, claims, predictions, plans, scores, verifications, oracle input."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from plsi.files import hash_json
from plsi.events import register_payload
from plsi.map.models import CareContext, CoordinateValue
from plsi.models import (
    Code,
    EventId,
    ExternalText,
    Id,
    LocalId,
    Model,
    PrefixedHash,
    RealId,
    SourceRef,
    UtcTime,
    coherence_errors,
)
from plsi.vocab import (
    ActionCategory,
    CodeSystem,
    Direction,
    EventType,
    EvidenceClass,
    PlanDecision,
    PlanState,
    PredictionTarget,
    ScoreStatus,
    Severity,
    SourceKind,
    SourceStatus,
)


class ActionInput(Model):
    local_id: LocalId
    description: str = Field(min_length=1, max_length=500)
    category: ActionCategory
    code: Code | None = None  # RxNorm ingredient
    dose: str | None = None
    schedule: str | None = None
    acknowledged: bool = False
    acknowledgement_note: str | None = None

    @model_validator(mode="after")
    def _structure(self) -> ActionInput:
        if self.code is not None and self.code.system != CodeSystem.RXNORM:
            raise ValueError("action code must be an RxNorm ingredient")
        if self.acknowledged and not (self.acknowledgement_note or "").strip():
            raise ValueError("acknowledged=true requires acknowledgement_note")
        return self

    def compute_action_hash(self) -> str:
        return hash_json(self.model_dump(mode="json", exclude_none=True, exclude={"local_id", "acknowledged", "acknowledgement_note"}))


class ScreeningContext(CareContext):
    co_action_ingredients: list[str] = []

    def compute_context_hash(self) -> str:
        return hash_json(self.dump())


class Finding(Model):
    severity: Severity
    summary: str
    source: SourceRef
    excerpt: ExternalText | None = None
    code: str | None = None  # e.g. SCREENING_UNAVAILABLE


class SourceConsulted(Model):
    source: str  # reference id (plsi refs)
    status: SourceStatus


class ScreeningRecord(Model):
    """Payload of a `screening` event; written ONLY by `plsi screen`."""

    action_hash: PrefixedHash
    context_hash: PrefixedHash
    context: ScreeningContext
    findings: list[Finding] = []
    outcome: Severity
    sources_consulted: list[SourceConsulted] = []
    screened_at: UtcTime

    @model_validator(mode="after")
    def _outcome(self) -> ScreeningRecord:
        expected = Severity.top(f.severity for f in self.findings)
        if self.outcome != expected:
            raise ValueError(f"outcome must be the maximum finding severity ({expected.value})")
        return self


class Effect(Model):
    coordinate: Id
    direction: Direction
    magnitude: float | None = None


class Unknown(Model):
    searched: list[str] = Field(min_length=1)


class ClaimInput(Model):
    local_id: LocalId
    statement: str = Field(min_length=1)
    evidence_class: EvidenceClass
    sources: list[SourceRef] = []
    supports: list[LocalId] = []
    effect: Effect | None = None
    unknown: Unknown | None = None

    @model_validator(mode="after")
    def _coherence(self) -> ClaimInput:
        errors = coherence_errors(self.evidence_class, self.sources)
        if self.evidence_class == EvidenceClass.UNKNOWN:
            if self.unknown is None:
                errors.append("unknown requires unknown.searched")
        elif not self.supports:
            errors.append("supports needs at least one action local_id unless evidence_class is unknown")
        if errors:
            raise ValueError("; ".join(errors))
        return self


class PredictionInput(Model):
    local_id: LocalId
    map_id: Id  # the map whose coordinate this predicts; a plan spans every map its predictions name
    coordinate: Id
    target: PredictionTarget
    horizon_days: int = Field(ge=1, le=730)
    expected: float
    low: float
    high: float
    interval_level: float = Field(default=0.8, ge=0.5, le=0.99)
    method: str = Field(min_length=1)
    evidence_class: EvidenceClass
    basis: list[SourceRef] = Field(min_length=1)
    driven_by: list[LocalId] = []  # empty = no-action control prediction

    @model_validator(mode="after")
    def _interval(self) -> PredictionInput:
        if not (self.low < self.high and self.low <= self.expected <= self.high):
            raise ValueError("requires low < high and low <= expected <= high")
        if errors := coherence_errors(self.evidence_class, self.basis):
            raise ValueError("; ".join(errors))
        return self


class RevisionRule(Model):
    review_after_days: int = Field(ge=1, le=730)
    continue_if: str
    modify_if: str
    stop_if: str


class PlanInput(Model):
    objective: str = Field(min_length=1)
    actions: list[ActionInput] = []
    claims: list[ClaimInput] = []
    predictions: list[PredictionInput] = Field(min_length=1)
    revision_rule: RevisionRule
    supersedes: RealId | None = None

    @model_validator(mode="after")
    def _references(self) -> PlanInput:
        local = [x.local_id for x in [*self.actions, *self.claims, *self.predictions]]
        if dupes := sorted({x for x in local if local.count(x) > 1}):
            raise ValueError(f"duplicate local_ids: {dupes}")
        actions = {a.local_id for a in self.actions}
        bad = [f"claim {c.local_id} supports {s}" for c in self.claims for s in c.supports if s not in actions]
        bad += [f"prediction {p.local_id} driven_by {d}" for p in self.predictions for d in p.driven_by if d not in actions]
        if bad:
            raise ValueError(f"unresolved action local_ids: {bad}")
        return self

    def compute_input_hash(self) -> str:
        return hash_json(self.dump())

    def map_ids(self) -> list[str]:
        """The maps the plan's predictions use, sorted."""
        return sorted({p.map_id for p in self.predictions})


class StateRef(Model):
    state_hash: PrefixedHash
    as_of: UtcTime


class Prediction(PredictionInput):
    id: RealId
    map_version: str
    map_hash: PrefixedHash
    state_ref: StateRef  # the projected state of map_id the prediction was made from
    baseline: CoordinateValue | None = None
    unit: str | None = None  # the coordinate's canonical unit


class Plan(PlanInput):
    """Stored plan (payload of a `plan` event)."""

    id: RealId
    subject_id: str
    input_hash: PrefixedHash
    ids: dict[str, RealId]  # every local_id (action, claim, prediction) -> real id
    predictions: list[Prediction] = []  # type: ignore[assignment]
    screening_event_ids: list[EventId] = []
    created_at: UtcTime


class ReviewInput(Model):
    decision: Literal[PlanDecision.CONTINUE, PlanDecision.MODIFY, PlanDecision.STOP, PlanDecision.COMPLETE]
    rationale: str = Field(min_length=1)
    replacement: PlanInput | None = None

    @model_validator(mode="after")
    def _replacement(self) -> ReviewInput:
        if (self.decision == PlanDecision.MODIFY) != (self.replacement is not None):
            raise ValueError("replacement is required for modify and forbidden otherwise")
        return self


class PlanStatusPayload(Model):
    plan_id: RealId
    decision: PlanDecision | None = None  # None for the initial proposed status
    state_after: PlanState
    at: UtcTime
    rationale: str | None = None
    start: date | None = None  # adoption: the day the plan starts
    horizons: dict[str, date] | None = None  # prediction_id -> horizon date
    review_at: date | None = None
    replacement_plan_id: RealId | None = None


class PredictionScore(Model):
    prediction_id: RealId
    status: ScoreStatus
    observed: CoordinateValue | None = None
    y: float | None = None
    error: float | None = None
    abs_error: float | None = None
    within_interval: bool | None = None
    direction_correct: bool | None = None
    beat_persistence: bool | None = None
    scored_at: UtcTime


class Verification(Model):
    """One line of <PLSI_HOME>/verifications.jsonl."""

    kind: SourceKind
    id: str
    ok: bool
    title: ExternalText | None = None
    canonical_url: str | None = None
    checked_at: UtcTime


class OracleInput(Model):
    """--file for `oracle pandaclaw` and `oracle l-llm`. With instance+map_id the outbound text is built from latest.json."""

    prompt: str = Field(min_length=1, max_length=20_000)
    instance: Id | None = None
    map_id: Id | None = None
    skill: str | None = Field(default=None, max_length=200)  # PandaClaw only: route to this skill (`oracle pandaclaw-skills`)

    @model_validator(mode="after")
    def _pair(self) -> OracleInput:
        if (self.instance is None) != (self.map_id is None):
            raise ValueError("instance and map_id go together")
        return self


register_payload(EventType.SCREENING, ScreeningRecord)
register_payload(EventType.PLAN, Plan)
register_payload(EventType.PLAN_STATUS, PlanStatusPayload)
register_payload(EventType.PREDICTION_SCORE, PredictionScore)
