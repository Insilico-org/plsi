"""The prediction vocabulary: what a prediction targets, how a score turned out, and when one comes due."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["PredictionTarget", "ScoreStatus", "DueState"]


class PredictionTarget(StrEnum):
    LEVEL = "level"
    CHANGE_FROM_BASELINE = "change_from_baseline"


class ScoreStatus(StrEnum):
    SCORED = "scored"
    MISSED = "missed"
    VOID = "void"


class DueState(StrEnum):
    """`plsi due`: a prediction whose score window is open."""

    DUE = "due"  # an eligible observation exists; `plsi score` will score it
    MISSED = "missed"  # the window closed without one
    AWAITING = "awaiting"  # the window is open, no eligible observation yet
