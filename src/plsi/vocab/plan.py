"""The plan vocabulary: action categories, plan states and decisions, and the policy gates and skill-lint rules."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ActionCategory", "PlanState", "CLOSED_PLAN_STATES", "PlanDecision", "SkillRule", "GateId"]


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


CLOSED_PLAN_STATES = frozenset({PlanState.STOPPED, PlanState.SUPERSEDED})  # no longer live: past, never charted


class PlanDecision(StrEnum):
    ADOPT = "adopt"
    CONTINUE = "continue"
    MODIFY = "modify"
    STOP = "stop"
    COMPLETE = "complete"


class SkillRule(StrEnum):
    """`plsi skills lint`: the `rule` of a skill-page violation (plsi.skill_lint)."""

    BOT_LISTED = "bot_listed"  # the roster, BotRole and skills/<bot>/ name the same bots
    COMMAND_EXISTS = "command_exists"  # every `plsi ...` in the roster or a page is a real command
    FRONTMATTER = "frontmatter"  # a page opens with --- name, description ---
    NAME_MATCHES_FOLDER = "name_matches_folder"  # name: is the skill's folder name
    DESCRIPTION_OPENING = "description_opening"  # "Use as <Bot> ..." (own page) or "Use when ..." (shared)


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
