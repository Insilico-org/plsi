"""The evidence vocabulary: the claim ladder and correspondence types, screening severity, and where a cited
source came from."""

from __future__ import annotations

from enum import StrEnum

from plsi.vocab.ranked import RankedEnum, nonmember

__all__ = [
    "EvidenceClass",
    "CorrespondenceType",
    "ClaimLevel",
    "Severity",
    "SourceKind",
    "SourceStatus",
    "SearchSource",
    "LITERATURE_SOURCE_KINDS",
]


class EvidenceClass(RankedEnum):
    # member order is significant: strongest first (rank 4 .. 0)
    _strongest_first = nonmember(True)

    EVIDENCE_BACKED = "evidence_backed"
    RULE_DERIVED = "rule_derived"
    MODEL_DERIVED = "model_derived"
    HYPOTHESIS_ONLY = "hypothesis_only"
    UNKNOWN = "unknown"


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


class Severity(RankedEnum):
    # member order is significant: mildest first (rank 0 .. 2)
    _empty = nonmember("none")

    NONE = "none"
    CAUTION = "caution"
    BLOCK = "block"


class SourceKind(StrEnum):
    PMID = "pmid"
    DOI = "doi"
    NCT = "nct"
    LABEL = "label"
    EVIPEDIA = "evipedia"
    MODEL = "model"
    RULE = "rule"


class SourceStatus(StrEnum):
    OK = "ok"
    NOT_FOUND = "not_found"
    ERROR = "error"


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
