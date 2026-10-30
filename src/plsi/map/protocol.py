"""Map protocol: the handoff messages between PLSI bots (skills/shared/team), checked by `plsi handoff check`.

Hub and spoke: the orchestrator sends `request`/`answer` to the other bots and receives `result`/`question`.
Messages cite the state documents they rely on, so every bot reasons over the same current published state."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field, model_validator

from plsi import errors
from plsi.files import load_json
from plsi.map import mapper
from plsi.models import Id, LocalId, Model, PrefixedHash, parse
from plsi.vocab import BotRole, HandoffKind

SkillName = Annotated[str, Field(pattern=r"^[a-z]+/[a-z0-9][a-z0-9-]{0,63}$")]  # <role>/<skill>, as under skills/
FROM_ORCHESTRATOR = (HandoffKind.REQUEST, HandoffKind.ANSWER)


class Question(Model):
    """Asked by the orchestrator: a question card when `options` are given, else a plain chat question."""

    id: LocalId
    text: str
    options: list[str] = []
    multi: bool = False


class StateCite(Model):
    map_id: Id
    state_hash: PrefixedHash


class Handoff(Model):
    """One message between PLSI bots, sent as JSON in the handoff text. `thread` ties a request to its questions,
    answers and result. `summary` is deidentified; records travel as `files` (paths on the shared computer)."""

    type: HandoffKind
    sender: BotRole
    recipient: BotRole
    thread: LocalId
    skill: SkillName
    instance: Id
    summary: str = Field(max_length=2000)
    states: list[StateCite] = []
    files: list[str] = []
    plan_id: str | None = None
    questions: list[Question] = []
    answers: dict[str, str | list[str]] = {}

    @model_validator(mode="after")
    def _route(self) -> Handoff:
        hub = BotRole.ORCHESTRATOR
        if (self.sender == hub) == (self.recipient == hub):
            raise ValueError("every handoff goes to or from the orchestrator")
        if (self.type in FROM_ORCHESTRATOR) != (self.sender == hub):
            raise ValueError(f"{self.type.value} is sent by {'the orchestrator' if self.type in FROM_ORCHESTRATOR else 'another bot'}")
        if self.questions and self.type not in (HandoffKind.QUESTION, HandoffKind.RESULT):
            raise ValueError("questions travel in a question or result")
        if self.answers and self.type != HandoffKind.ANSWER:
            raise ValueError("answers travel in an answer")
        worker = self.recipient if self.sender == hub else self.sender
        if self.skill.split("/")[0] not in (worker.value, hub.value, "shared"):
            raise ValueError(f"{self.skill} is not a skill of {worker.value} (skills/{worker.value}/)")
        return self


def published(instance: str, map_id: str) -> dict[str, Any]:
    """`plsi state show`: the state last published for a map (read-only; workers re-project through
    PLSI). `current` is false when observations changed after it; then ask PLSI to have it re-projected."""
    latest = mapper.latest_state(instance, map_id)
    if latest is None:
        raise errors.NotFound(f"no published state for {map_id}", code="STATE_NOT_FOUND",
                              hint=f"re-project: plsi project --instance {instance} --map {map_id}")
    changed = mapper.last_world_change(instance)
    return {"state": latest.dump(),
            "current": latest.verify_hash() and mapper.is_current(latest, changed)}


def check(file: str) -> dict[str, Any]:
    """`plsi handoff check --file F`: schema and route, and every cited state is the current projection
    (latest.json, hash verifies, no observation recorded after it). Writes nothing."""
    msg = parse(Handoff, load_json(file), "handoff")
    hint = f"re-project: plsi project --instance {msg.instance} --map <map_id>"
    problems = []
    changed = mapper.last_world_change(msg.instance)
    for i, cite in enumerate(msg.states):
        latest = mapper.latest_state(msg.instance, cite.map_id)
        if latest is None or latest.state_hash != cite.state_hash or not latest.verify_hash():
            problems.append(errors.violation(f"states.{i}", "STATE", f"{cite.map_id}: not the current projection", hint))
        elif not mapper.is_current(latest, changed):
            problems.append(errors.violation(f"states.{i}", "STATE", f"{cite.map_id}: observations changed since", hint))
    if problems:
        raise errors.ValidationError("handoff cites stale state", code="STALE_STATE", violations=problems)
    return {"handoff": msg.dump()}
