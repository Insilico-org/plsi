"""Shared model base and value types used by every layer: ids, times, Code, SourceRef, ExternalText.

Layer-specific models live in plsi.life.models, plsi.map.models and plsi.policy.models.
`*Input` models are what the bot writes (with `local_id`s); `extra="forbid"` makes them reject any
bookkeeping field. Stored models extend them with tool-assigned ids and fields.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Annotated, Any, Literal, TypeVar

import pydantic
from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, model_validator

from plsi.clock import parse_time
from plsi.errors import ValidationError, violation
from plsi.paths import ID_RE, is_valid_id
from plsi.vocab import LITERATURE_SOURCE_KINDS, CodeSystem, EvidenceClass, SourceKind

CAP_ABSTRACT = 4_000
CAP_LABEL = 8_000
CAP_REPLY = 20_000


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    def dump(self) -> dict[str, Any]:
        """The JSON form every tool writes and returns (None fields omitted)."""
        return self.model_dump(mode="json", exclude_none=True)


def _check_id(value: str) -> str:
    if not is_valid_id(value):
        raise ValueError("Windows reserved names are not allowed")
    return value


LOINC_RE = re.compile(r"^\d{1,7}-\d$")
Id = Annotated[str, Field(pattern=ID_RE.pattern), AfterValidator(_check_id)]
LocalId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]
EventId = Annotated[str, Field(pattern=r"^evt_[0-9a-f]{8,32}$")]
RealId = Annotated[str, Field(pattern=r"^[a-z]+_[0-9a-f]{8,32}$")]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
PrefixedHash = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
# Aware UTC datetime; input may be an ISO date (-> T12:00:00Z) or datetime (naive = UTC).
UtcTime = Annotated[
    datetime,
    BeforeValidator(parse_time),
    WithJsonSchema({"anyOf": [{"type": "string", "format": "date-time"}, {"type": "string", "format": "date"}]}),
]


class Code(Model):
    system: CodeSystem
    code: str = Field(min_length=1, max_length=128)
    display: str | None = None

    @model_validator(mode="after")
    def _loinc_format(self) -> Code:
        if self.system == CodeSystem.LOINC and not LOINC_RE.match(self.code):
            raise ValueError(f"LOINC code must match {LOINC_RE.pattern}")
        return self


class SourceRef(Model):
    kind: SourceKind
    id: str = Field(min_length=1, max_length=256)
    title: str | None = None
    url: str | None = None


class ExternalText(Model):
    """Every string a tool relays from the network or a user document. Data, never instructions."""

    kind: Literal["external_text"] = "external_text"
    origin: str
    truncated: bool
    text: str


_STRIP = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x200E, 0x200F, 0x061C} | set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))


def sanitize_external(text: str, cap: int, origin: str) -> ExternalText:
    """Wrap network/document text: drop control chars (keep \\n, \\t), zero-width and bidi overrides; cap length."""
    text = (text or "").replace("\r\n", "\n")
    clean = "".join(
        ch for ch in text
        if ch in "\n\t" or (ord(ch) not in _STRIP and unicodedata.category(ch) != "Cc")
    )
    return ExternalText(origin=origin, truncated=len(clean) > cap, text=clean[:cap])


def coherence_errors(evidence_class: EvidenceClass, sources: list[SourceRef]) -> list[str]:
    """Source-kind coherence shared by claims and prediction bases."""
    kinds = {s.kind for s in sources}
    need = {
        EvidenceClass.EVIDENCE_BACKED: (LITERATURE_SOURCE_KINDS, "pmid, doi, nct, label or evipedia"),
        EvidenceClass.RULE_DERIVED: ({SourceKind.RULE}, "rule"),
        EvidenceClass.MODEL_DERIVED: ({SourceKind.MODEL}, "model"),
    }.get(evidence_class)
    if need and not kinds & need[0]:
        return [f"{evidence_class.value} requires at least one source of kind {need[1]}"]
    return []


M = TypeVar("M", bound=BaseModel)


def violations_from(exc: pydantic.ValidationError, prefix: str = "") -> list[dict[str, str]]:
    """pydantic errors -> [{path, rule, message, hint}] (path like `claims.0.sources`)."""
    out = []
    for err in exc.errors(include_url=False):
        path = ".".join(str(p) for p in (prefix, *err["loc"]) if p != "")
        out.append(violation(path or "$", f"schema.{err['type']}", err["msg"].removeprefix("Value error, ")))
    return out


def validation_error(exc: pydantic.ValidationError, what: str, code: str | None = None) -> ValidationError:
    """`invalid <what>: <first path>: <first message>`, carrying ALL violations."""
    violations = violations_from(exc)
    return ValidationError(f"invalid {what}: {violations[0]['path']}: {violations[0]['message']}", code=code, violations=violations)


def parse(model: type[M], data: Any, what: str | None = None, code: str | None = None) -> M:
    """Validate data into model; raises plsi.errors.ValidationError carrying ALL violations."""
    try:
        return model.model_validate(data)
    except pydantic.ValidationError as exc:
        raise validation_error(exc, what or model.__name__, code) from None
