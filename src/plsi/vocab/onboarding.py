"""The onboarding vocabulary: the setup feedback stages and marks, their severity, and the interview topics."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["FeedbackStage", "FeedbackMark", "FeedbackSeverity", "InterviewTopic"]


class FeedbackStage(StrEnum):
    """Setup stages of plsi.md, then use."""

    INSTALL = "install"
    TEAM = "team"
    CHOICES = "choices"
    INTERVIEW = "interview"
    SPECIALISTS = "specialists"
    CONNECTORS = "connectors"
    INSTANCE = "instance"
    ROUTINES = "routines"
    MOTHERSHIP = "mothership"
    WELCOME = "welcome"
    RECORDS = "records"
    PLANS = "plans"
    RESEARCH = "research"
    OTHER = "other"


class FeedbackMark(StrEnum):
    """A `feedback mark` that is not a stage."""

    DONE = "done"  # ends the last setup stage


class FeedbackSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InterviewTopic(StrEnum):
    """The onboarding interview's topics in the order asked (`orchestrator/talk`; `plsi interview save`)."""

    ROLE = "role"
    OWN_HEALTH = "own_health"  # physician or researcher only
    ABOUT = "about"  # birth year, sex, country, ethnicity
    HEALTH = "health"
    MEDICATIONS = "medications"
    LIFESTYLE = "lifestyle"
    GOALS = "goals"
    SPECIALISTS = "specialists"
    EXTRAS = "extras"
