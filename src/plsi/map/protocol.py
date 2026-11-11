"""Map protocol: the handoff messages between PLSI bots (skills/shared/team), checked by `plsi handoff check`.

Hubs and spokes: a hub (vocab.HUBS) sends `request`/`answer` to a worker and receives `result`/`question`; the
workers are shared and reply to the hub that sent the request. Hub to hub, a `request` and its `result` hand a thread
over. Every handoff names its `instance`; a ward bot's is its pinned patient's (team.json). Messages cite the state
documents they rely on, so every bot reasons over the same current published state."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field, model_validator

from plsi import errors, team
from plsi.files import load_json
from plsi.map import mapper
from plsi.models import Id, LocalId, Model, PrefixedHash, parse
from plsi.vocab import HUBS, BotRole, HandoffKind

SkillName = Annotated[str, Field(pattern=r"^[a-z]+/[a-z0-9][a-z0-9-]{0,63}$")]  # <role>/<skill>, as under skills/
FROM_HUB = (HandoffKind.REQUEST, HandoffKind.ANSWER)
HUB_TO_HUB = (HandoffKind.REQUEST, HandoffKind.RESULT)


class Question(Model):
    """Asked by a hub: a question card when `options` are given, else a plain chat question."""

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
        sent, received = self.sender in HUBS, self.recipient in HUBS
        if not (sent or received):
            raise ValueError("every handoff goes to or from a hub")
        if self.sender == self.recipient:
            raise ValueError("a bot does not hand off to itself")
        if sent and received and self.type not in HUB_TO_HUB:
            raise ValueError(f"{self.type.value} goes between a hub and a worker, not hub to hub")
        if self.type in FROM_HUB and not sent:
            raise ValueError(f"{self.type.value} is sent by a hub")
        if self.type not in FROM_HUB and not received:
            raise ValueError(f"{self.type.value} is sent to a hub")
        if self.questions and self.type not in (HandoffKind.QUESTION, HandoffKind.RESULT):
            raise ValueError("questions travel in a question or result")
        if self.answers and self.type != HandoffKind.ANSWER:
            raise ValueError("answers travel in an answer")
        doer, hub = (self.recipient, self.sender) if self.type in FROM_HUB else (self.sender, self.recipient)
        if self.skill.split("/")[0] not in (doer.value, hub.value, BotRole.ORCHESTRATOR.value, "shared"):
            raise ValueError(f"{self.skill} is not a skill of {doer.value} (skills/{doer.value}/) or {hub.value}")
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
    (latest.json, hash verifies, no observation recorded after it), and a ward bot's handoff names its pinned
    instance. Writes nothing."""
    msg = parse(Handoff, load_json(file), "handoff")
    if BotRole.WARD in (msg.sender, msg.recipient) and msg.instance not in {
            b.get("instance") for b in team.show()["hubs"] if b["role"] == BotRole.WARD}:
        raise errors.ValidationError(f"no ward bot is pinned to {msg.instance}", code="WARD_INSTANCE",
                                     hint="a ward bot's handoffs name its own instance (plsi team show)")
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
