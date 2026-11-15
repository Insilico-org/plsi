"""Instance storage: subject.json and the append-only events.jsonl (never edited in place)."""

from __future__ import annotations

import re
import secrets
import shutil
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any

import pydantic
from pydantic import BaseModel

from plsi.clock import now
from plsi.errors import NotFound, ValidationError
from plsi.files import append_jsonl_many, atomic_write_json, load_json, lock, read_jsonl
from plsi.events import Event, NewEvent, PAYLOAD_TYPES
from plsi.life.deid import deid_subject_fields
from plsi.life.models import Retraction, Subject
from plsi.paths import instance_dir, new_id, plsi_home, validate_id
from plsi.vocab import Ethnicity, EventType, Relation, Sex


def _retracted(events: Iterable[Event]) -> set[str]:
    return {e.payload.target_event_id for e in events if e.type == EventType.RETRACTION}  # type: ignore[union-attr]


def _dump(event: Event) -> dict[str, Any]:
    payload = event.payload
    data = event.model_dump(mode="json", exclude_none=True, exclude={"payload"})
    data["payload"] = payload.model_dump(mode="json", exclude_none=True) if isinstance(payload, BaseModel) else payload
    return data


class EventStore:
    def __init__(self, instance: str) -> None:
        self.instance = instance
        self.dir = instance_dir(instance)
        self.path = self.dir / "events.jsonl"

    @property
    def subject(self) -> Subject:
        return Subject.model_validate(load_json(self.dir / "subject.json"))

    # -------------------------------------------------------------- writing

    def append(self, type: EventType, payload: BaseModel, *, dedupe_key: str | None = None, dedupe: bool = False) -> tuple[str, bool]:
        """Append one event under the instance lock -> (event_id, created). created=False means a dedupe hit."""
        return self.append_many([NewEvent(type, payload, dedupe_key, dedupe)])[0]

    @contextmanager
    def locked(self) -> Iterator[list[Event]]:
        """Hold the instance lock and read the whole log once under it (retracted events included): a command that
        checks the log and then appends reads it only this once, and passes it to `append_locked`."""
        with lock(self.dir):
            yield self.events(active=False)

    def append_many(self, items: Iterable[NewEvent]) -> list[tuple[str, bool]]:
        """Append events in order under ONE lock; ids and recorded_at are tool-set. Payloads are re-validated."""
        with lock(self.dir):
            return self.append_locked(self.events(active=False), items)

    def retract(self, targets: list[str], reason: str, replacement: tuple[BaseModel, str] | None = None) -> list[dict[str, str]]:
        """Retract every id in `targets` with one read of the log and one append, all under ONE lock (so two
        processes cannot retract the same event twice). replacement: (Observation, dedupe_key) appended first, for
        a single target; its id goes into replacement_event_id. Every id is checked before anything is written.
        -> [{target_event_id, retraction_event_id, replacement_event_id?}] in the order given."""
        if len(set(targets)) != len(targets):
            raise ValidationError("an event id is listed twice", code="DUPLICATE_TARGET")
        if replacement is not None and len(targets) != 1:
            raise ValidationError("a replacement goes with exactly one retracted event", code="REPLACEMENT_NEEDS_ONE")
        with lock(self.dir):
            events = self.events(active=False)
            by_id = {e.id: e for e in events}
            gone = _retracted(events)
            for event_id in targets:
                target = by_id.get(event_id)
                if target is None:
                    raise NotFound(f"event {event_id!r} not found", code="EVENT_NOT_FOUND")
                if target.type == EventType.RETRACTION:
                    raise ValidationError(f"{event_id} is a retraction; retraction events cannot be retracted",
                                          code="CANNOT_RETRACT_RETRACTION")
                if event_id in gone:
                    raise ValidationError(f"event {event_id} is already retracted", code="ALREADY_RETRACTED")
            if replacement is not None:  # never deduped: it may equal the target
                (new_id_, _), = self.append_locked(events, [NewEvent(EventType.OBSERVATION, replacement[0], dedupe_key=replacement[1])])
                payload = Retraction(target_event_id=targets[0], reason=reason, replacement_event_id=new_id_)
                (rid, _), = self.append_locked(events, [NewEvent(EventType.RETRACTION, payload)])
                return [{"target_event_id": targets[0], "replacement_event_id": new_id_, "retraction_event_id": rid}]
            written = self.append_locked(events, [NewEvent(EventType.RETRACTION, Retraction(target_event_id=t, reason=reason))
                                                   for t in targets])
        return [{"target_event_id": t, "retraction_event_id": rid} for t, (rid, _) in zip(targets, written, strict=True)]

    def append_locked(self, events: list[Event], items: Iterable[NewEvent]) -> list[tuple[str, bool]]:
        """Append under a lock the caller holds (`locked`), deduping against the log it read under it."""
        out: list[tuple[str, bool]] = []
        new: list[dict[str, Any]] = []
        gone = _retracted(events)
        active_keys = {e.dedupe_key: e.id for e in events if e.dedupe_key and e.id not in gone}
        subject_id = self.subject.subject_id
        for item in items:
            if item.dedupe and item.dedupe_key in active_keys:
                out.append((active_keys[item.dedupe_key], False))
                continue
            event_type = EventType(item.type)
            payload = PAYLOAD_TYPES[event_type].model_validate(item.payload.model_dump(mode="json"))
            event = Event(id=new_id("evt"), type=event_type, recorded_at=now(), subject_id=subject_id,
                          dedupe_key=item.dedupe_key, payload=payload)
            new.append(_dump(event))
            if item.dedupe_key:
                active_keys[item.dedupe_key] = event.id
            out.append((event.id, True))
        append_jsonl_many(self.path, new)
        return out

    # -------------------------------------------------------------- reading

    def events(self, type: EventType | str | None = None, *, active: bool = True) -> list[Event]:
        """Events in log order from one read; active=True drops those targeted by a retraction (retraction events
        themselves stay listed). Invalid lines raise ValidationError."""
        events = []
        for n, raw in enumerate(read_jsonl(self.path), 1):
            try:
                event = Event.model_validate(raw)
                if payload_type := PAYLOAD_TYPES.get(event.type):
                    event.payload = payload_type.model_validate(event.payload)
            except pydantic.ValidationError as exc:  # refuse rather than silently skip a real event
                raise ValidationError(f"events.jsonl record {n} is not a valid event: {exc.errors()[0]['msg']}", code="CORRUPT_EVENT") from None
            events.append(event)
        gone = _retracted(events) if active else set()
        wanted = EventType(type) if type is not None else None
        return [e for e in events if e.id not in gone and (wanted is None or e.type == wanted)]

    def get(self, event_id: str) -> Event:
        for event in self.events(active=False):
            if event.id == event_id:
                return event
        raise NotFound(f"event {event_id!r} not found", code="EVENT_NOT_FOUND")

    def log(self) -> tuple[list[Event], set[str]]:
        """Every event in log order, retracted ones included, and the ids a retraction targets."""
        events = self.events(active=False)
        return events, _retracted(events)

    def observations(self) -> list[Event]:
        return self.events(EventType.OBSERVATION)

    # -------------------------------------------------------------- subject

    def update_subject(self, *, birth_year: int | None = None, sex: Sex | str | None = None, relation: Relation | str | None = None,
                       country: str | None = None, ethnicity: Ethnicity | str | None = None,
                       update: bool = False) -> tuple[Subject, list[str]]:
        """Fill unset subject fields; change existing values only with update=True. Applies the 90+ rule. -> (subject, changed fields)."""
        with lock(self.dir):
            subject = self.subject
            fields = deid_subject_fields(birth_year, sex)
            changed: dict[str, Any] = {}
            if birth_year is not None and (update or (subject.birth_year is None and subject.age_group is None)):
                changed |= {"birth_year": fields["birth_year"], "age_group": fields["age_group"]}
            if sex is not None and (update or subject.sex == Sex.UNKNOWN):
                changed["sex"] = fields["sex"]
            if relation is not None and (update or subject.relation is None):
                changed["relation"] = Relation(relation)
            if country is not None and (update or subject.country is None):
                changed["country"] = _country(country)
            if ethnicity is not None and (update or subject.ethnicity is None):
                changed["ethnicity"] = Ethnicity(ethnicity)
            changed = {k: v for k, v in changed.items() if getattr(subject, k) != v}
            if changed:
                subject = Subject.model_validate({**subject.model_dump(mode="json"), **changed})
                atomic_write_json(self.dir / "subject.json", subject.dump())
            return subject, sorted(changed)


def _country(value: str | None) -> str | None:
    """ISO 3166 alpha-3, upper-cased; anything else is refused before any file is written."""
    if value is None:
        return None
    if not re.fullmatch(r"[A-Za-z]{3}", value):
        raise ValidationError(f"country must be an ISO 3166 alpha-3 code (e.g. FRA), not {value!r}")
    return value.upper()


def init_instance(instance: str, birth_year: int | None = None, sex: Sex | str | None = None, relation: Relation | str | None = None,
                  country: str | None = None, ethnicity: Ethnicity | str | None = None, update: bool = False) -> dict[str, Any]:
    """Create <PLSI_HOME>/<instance>/ with subject.json and an empty events.jsonl. Existing -> created False (+ subject update).
    One instance per person; `relation` says who it is to the user."""
    validate_id(instance, "instance name")
    country = _country(country)
    path = instance_dir(instance, must_exist=False)
    created = not (path / "subject.json").exists()
    if created:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        with lock(path):
            fields = deid_subject_fields(birth_year, sex)
            subject = Subject(subject_id=f"s_{secrets.token_hex(6)}", created_at=now(), relation=relation,
                              country=country, ethnicity=ethnicity, **fields)
            atomic_write_json(path / "subject.json", subject.dump())
            (path / "events.jsonl").touch()
        changed: list[str] = []
    else:
        subject, changed = EventStore(instance).update_subject(birth_year=birth_year, sex=sex, relation=relation,
                                                               country=country, ethnicity=ethnicity, update=update)
    return {"instance": instance, "created": created, "path": str(path), "subject": subject.dump(), "updated_fields": changed}


def list_instances() -> list[dict[str, Any]]:
    """`plsi instances list`: every instance under PLSI_HOME with its subject, relation and activity, sorted by name."""
    out = []
    for path in sorted(plsi_home().glob("*/subject.json")):
        store = EventStore(path.parent.name)
        counts = event_counts(store.instance)
        out.append({"instance": store.instance, "subject": store.subject.dump(),
                    "active_observations": counts["active_observations"], "last_recorded_at": counts["last_recorded_at"],
                    "states": sorted(p.parent.name for p in (store.dir / "states").glob("*/latest.json"))})
    return out


def delete_instance(instance: str, confirm: str) -> dict[str, Any]:
    """`instances delete`: remove <PLSI_HOME>/<instance>/ (log, states, plans) for good; confirm must repeat the name."""
    path = instance_dir(instance)
    if confirm != instance:
        raise ValidationError(f"refusing to delete {instance!r}: --confirm must repeat the instance name", code="CONFIRM_MISMATCH",
                              hint=f"plsi export --instance {instance} --out <PLSI_HOME>/exports/{instance} first (outside the instance folder), then plsi instances delete --instance {instance} --confirm {instance}")
    counts = event_counts(instance)
    with lock(path):  # the held .lock file goes last, with the folder, once the lock is released
        removed = sorted(p.relative_to(path).as_posix() for p in path.rglob("*") if p.is_file() and p.name != ".lock")
        for child in path.iterdir():
            if child.name != ".lock":
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    shutil.rmtree(path, ignore_errors=True)
    return {"instance": instance, "deleted": not path.exists(), "path": str(path), "files_removed": removed,
            "events_removed": sum(counts["by_type"].values())}


def list_events(instance: str, type: EventType | str | None = None, kind: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """`events list`: newest last; optional event type, observation kind and limit (last N)."""
    events, gone = EventStore(instance).log()
    wanted = EventType(type) if type is not None else None
    events = [
        {**_dump(e), "retracted": e.id in gone}
        for e in events
        if (wanted is None or e.type == wanted)
        and (kind is None or (e.type == EventType.OBSERVATION and e.payload.kind == kind))  # type: ignore[union-attr]
    ]
    if limit is not None:
        events = events[-limit:] if limit > 0 else []
    return {"count": len(events), "events": events}


def event_counts(instance: str) -> dict[str, Any]:
    events, gone = EventStore(instance).log()
    return {
        "by_type": dict(Counter(e.type for e in events)),
        "retracted": len(gone),
        "active_observations": sum(1 for e in events if e.type == EventType.OBSERVATION and e.id not in gone),
        "last_recorded_at": events[-1].recorded_at.isoformat() if events else None,
    }

