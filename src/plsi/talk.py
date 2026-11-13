"""The onboarding interview so far, kept in <PLSI_HOME>/interview.json as each topic is answered, so a dropped call,
a new chat or a later offer to restart onboarding asks only the topics still missing (`orchestrator/talk`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files, paths, role, team
from plsi.clock import now
from plsi.errors import ValidationError
from plsi.vocab import InterviewTopic, UserRole

PERSONAL = (InterviewTopic.ABOUT, InterviewTopic.HEALTH, InterviewTopic.MEDICATIONS, InterviewTopic.LIFESTYLE,
            InterviewTopic.GOALS)


def interview_path() -> Path:
    return paths.plsi_home() / "interview.json"


def _answered() -> dict[str, Any]:
    path = interview_path()
    return files.load_json(path) if path.is_file() else {}


def _needed() -> list[InterviewTopic]:
    """Every topic, less own health for an individual and the personal topics when own health is off."""
    stored = role.show()
    skip = {InterviewTopic.OWN_HEALTH} if stored["stored"] and stored["role"] == UserRole.INDIVIDUAL else set()
    if team.show()["team"]["own_health"] is False:
        skip.update(PERSONAL)
    return [t for t in InterviewTopic if t not in skip]


def show() -> dict[str, Any]:
    """`interview show`: each answered topic in the user's words, and the topics still to ask, in order."""
    answered = _answered()
    missing = [t.value for t in _needed() if t not in answered]
    return {"answered": answered, "missing": missing, "complete": not missing}


def save(topic: str, answer: str) -> dict[str, Any]:
    """`interview save`: keep one answered topic; saving it again replaces it (a correction)."""
    if not answer.strip():
        raise ValidationError("the answer is empty", hint='a declined topic is saved as said, e.g. --answer "rather not say"')
    answered = _answered()
    answered[InterviewTopic(topic).value] = {"answer": answer.strip(), "at": now().isoformat(timespec="seconds")}
    files.atomic_write_json(interview_path(), answered, private=True)
    return show()
