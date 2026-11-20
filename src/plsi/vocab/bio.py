"""The vocabulary of `plsi bio`: step verdicts, freeze stages, dataset roles and decisions, pooling and null models,
and the rules it refuses or flags on."""

from __future__ import annotations

from enum import StrEnum


class AnalysisVerdict(StrEnum):
    """The verdicts an analysis step may end with, against the criterion frozen before the data were opened."""

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    INCONCLUSIVE = "inconclusive"


class FreezeStage(StrEnum):
    PROTOCOL = "protocol"  # procedures, before any held-out data
    DISCOVERY = "discovery"  # the outputs derived from discovery, before replication


class DatasetRole(StrEnum):
    """What a public dataset is for in the protocol; only a `replication` set decides a replication."""

    DISCOVERY = "discovery"
    REPLICATION = "replication"
    EXPLORATORY = "exploratory"
    FEASIBILITY = "feasibility"


class DatasetDecision(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    HOLD = "hold"  # eligibility not settled: a question is open on the metadata


class PoolModel(StrEnum):
    HKSJ = "hksj"  # Hartung-Knapp-Sidik-Jonkman random effects, modified max(1, q)
    DL = "dl"  # DerSimonian-Laird random effects


class NullModel(StrEnum):
    RANDOM = "random"  # gene sets of the same size drawn from the universe
    MATCHED = "matched"  # the same, matched on the gene's mean-expression decile


class StepRule(StrEnum):
    """The `rule` of a refused step file or eligibility row."""

    STEP_ID = "step_id"
    REQUIRED = "required"
    SHORT_METHODS = "short_methods"
    KEY_NUMBERS = "key_numbers"
    INTERVAL = "interval"
    FILE_IN_PROJECT = "file_in_project"
    SHORT_CRITERION = "short_criterion"
    VERDICT = "verdict"
    CRITERION_FROZEN = "criterion_frozen"
    SUPPORTED_EARNED = "supported_earned"
    VOCABULARY = "vocabulary"


class BioRule(StrEnum):
    """A `plsi bio` flag (warned, and in `flags`) or check violation."""

    MANIFEST_DRIFT = "manifest_drift"  # a frozen file changed or went missing
    ELIGIBILITY_INCOMPLETE = "eligibility_incomplete"  # an included dataset without the fields eligibility needs
    DUPLICATE_DATASET = "duplicate_dataset"  # one accession on two rows
    SHARED_ORIGIN = "shared_origin"  # a replication set shares its origin with discovery: not independent
    THIN_OVERLAP = "thin_overlap"  # too few genes shared to judge replication
    SPARSE_TABLE = "sparse_table"  # a 2x2 cell too small for the ratio to be stable
    CONTROL_MISSED = "control_missed"  # the frozen positive control is not a signal: the pipeline is wrong
    NULL_MISSPECIFIED = "null_misspecified"  # the permuted null keeps the gradient it was meant to remove
    NULL_AS_GOOD = "null_as_good"  # a random or matched set scores as well as the signature
    LIMIT_EXCEEDED = "limit_exceeded"  # a frozen composition limit was passed
    FEW_EVENTS = "few_events"  # a survival group with too few events to carry the comparison
    SET_SIZE_BIAS = "set_size_bias"  # enrichment ranks follow set size, not the gene list
    ORDER_UNSTABLE = "order_unstable"  # two orderings of the same cells disagree
    KO_NOT_PERTURBED = "ko_not_perturbed"  # a virtual knockout whose gene is not among its own top perturbed genes
    DIRECTION_UNIFORM = "direction_uniform"  # nearly all predicted directions agree: possibly the dominant program or depth
