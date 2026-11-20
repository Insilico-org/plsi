"""The team vocabulary: the bot roster, who the user is, and the kinds of handoff between bots."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["BotRole", "HUBS", "PRIMARY_HUBS", "UserRole", "HandoffKind"]


class BotRole(StrEnum):
    """The PLSI team on Grok Bot; the roster (slug -> display name, core vs opt-in specialists, skills) is skills/shared/team.
    The hubs (HUBS) talk to the user; the workers are shared by all hubs. Every handoff has a hub on at least one end."""

    ORCHESTRATOR = "orchestrator"  # PLSI · Health Orchestrator: the user's own health
    LAB = "lab"  # PLSI · Research Orchestrator: runs the research moves itself
    CLINIC = "clinic"  # PLSI · Clinic Orchestrator: panel, intake, roster
    WARD = "ward"  # one per roster patient, pinned to that patient's instance
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
    BIOINFO = "bioinfo"  # public omics and reports analyses, step by step


HUBS = frozenset({BotRole.ORCHESTRATOR, BotRole.LAB, BotRole.CLINIC, BotRole.WARD})  # the bots that talk to the user
PRIMARY_HUBS = tuple(sorted(h.value for h in HUBS - {BotRole.WARD}))  # the hub that ran plsi.md; never a ward bot


class UserRole(StrEnum):
    """Who the user is to PLSI (`plsi role set`); picks the sections of the team that are set up."""

    INDIVIDUAL = "individual"
    PHYSICIAN = "physician"
    RESEARCHER = "researcher"


class HandoffKind(StrEnum):
    REQUEST = "request"  # hub -> worker or hub: run a skill
    RESULT = "result"  # worker or hub -> the hub that sent the request
    QUESTION = "question"  # worker -> hub: for the user (only a hub asks the user)
    ANSWER = "answer"  # hub -> the asking worker: the user's answers
