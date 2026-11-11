"""Hevy, the user's workout log (`plsi refs show hevy`): the connection check, recent workouts, exercise templates,
and new routines PLSI planned, in a folder of their own. The only calls to Hevy."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from pydantic import Field

from plsi import files, keys, net, references
from plsi.errors import KeyMissing, NetworkError, ValidationError
from plsi.models import Model, external_str, parse
from plsi.mothership import gate, scan
from plsi.vocab import HevySetType

KEY = "HEVY_API_KEY"
FOLDER = "PLSI"
TITLE_PREFIX = "PLSI · "
PAGE = 10  # workouts, routines and folders per page (Hevy's maximum)
TEMPLATE_PAGE = 100
MAX_WORKOUTS = 100
MAX_TEMPLATES = 5000  # the whole exercise library
MAX_FOLDERS = 1000


class SessionSet(Model):
    type: HevySetType = HevySetType.NORMAL
    reps: int | None = Field(default=None, ge=1, le=100)
    weight_kg: float | None = Field(default=None, ge=0, le=500)
    duration_seconds: int | None = Field(default=None, ge=1, le=7200)
    distance_meters: int | None = Field(default=None, ge=1, le=100_000)


class SessionExercise(Model):
    exercise_template_id: str = Field(pattern=r"^[A-Za-z0-9-]{1,64}$")
    rest_seconds: int | None = Field(default=None, ge=0, le=600)
    notes: str | None = Field(default=None, max_length=200)
    sets: list[SessionSet] = Field(min_length=1, max_length=10)


class Session(Model):
    """One training session for the user's Hevy account (`coach/exercise`); text is about the exercises only."""

    title: str = Field(min_length=1, max_length=60)
    notes: str | None = Field(default=None, max_length=300)
    exercises: list[SessionExercise] = Field(min_length=1, max_length=15)


def _call(method: str, path: str, params: dict[str, Any] | None = None, body: Any = None) -> Any:
    headers = {"api-key": keys.require(KEY)}
    url = f"{references.api_base('hevy')}{path}"
    try:
        return net.get_json(url, params, headers) if method == "GET" else net.post_json(url, body, headers).json()
    except NetworkError as e:
        if e.status == 403 and path == "/v1/routines":
            raise ValidationError("Hevy's routine limit is reached", code="HEVY_ROUTINE_LIMIT",
                                  hint="delete old PLSI routines in the Hevy app") from None
        if e.status in (401, 403):
            raise KeyMissing("Hevy refused the key", code="HEVY_KEY_REFUSED",
                             hint="a Hevy Pro account and a current key from hevy.com/settings?developer") from None
        raise


def _pages(path: str, field: str, size: int, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page = 1
    while len(out) < limit:
        reply = _call("GET", path, {"page": page, "pageSize": size}) or {}
        out += reply.get(field) or []
        if page >= (reply.get("page_count") or 0):
            break
        page += 1
    return out[:limit]


def check() -> dict[str, Any]:
    """`plsi hevy check`: the key works; the workout count and whether the PLSI folder exists."""
    count = (_call("GET", "/v1/workouts/count") or {}).get("workout_count", 0)
    folder = _folder_id(create=False)
    return {"connected": True, "workouts": count, "plsi_folder": folder is not None}


def workouts(since: date | None = None, limit: int = 20) -> dict[str, Any]:
    """`plsi hevy workouts [--since D] [--limit N]`: the newest workouts, each exercise with its sets."""
    if not 1 <= limit <= MAX_WORKOUTS:
        raise ValidationError(f"--limit is 1 to {MAX_WORKOUTS}")
    found = []
    for w in _pages("/v1/workouts", "workouts", PAGE, limit):
        start = str(w.get("start_time") or "")
        if since and start[:10] < since.isoformat():
            break
        found.append({"title": external_str(w.get("title")), "start": start, "end": w.get("end_time"),
                      "exercises": [{"title": external_str(x.get("title")), "template_id": x.get("exercise_template_id"),
                                     "sets": [{k: s[k] for k in ("type", "weight_kg", "reps", "duration_seconds",
                                                                 "distance_meters", "rpe") if s.get(k) is not None}
                                              for s in x.get("sets") or []]}
                                    for x in w.get("exercises") or []]})
    return {"workouts": found, "external_text": True}


def templates(muscle: str | None = None, search: str | None = None) -> dict[str, Any]:
    """`plsi hevy templates [--muscle M] [--search TEXT]`: exercises a routine can use, with their ids."""
    found = []
    for t in _pages("/v1/exercise_templates", "exercise_templates", TEMPLATE_PAGE, MAX_TEMPLATES):
        muscles = {t.get("primary_muscle_group"), *(t.get("secondary_muscle_groups") or [])}
        if muscle and muscle.lower() not in {str(m).lower() for m in muscles if m}:
            continue
        if search and search.lower() not in str(t.get("title", "")).lower():
            continue
        found.append({"id": t.get("id"), "title": external_str(t.get("title")), "type": external_str(t.get("type")),
                      "primary": external_str(t.get("primary_muscle_group")),
                      "equipment": external_str(t.get("equipment"))})
    return {"templates": found, "external_text": True}


def _folder_id(create: bool) -> int | None:
    for f in _pages("/v1/routine_folders", "routine_folders", PAGE, MAX_FOLDERS):
        if f.get("title") == FOLDER:
            return f.get("id")
    if not create:
        return None
    reply = _call("POST", "/v1/routine_folders", body={"routine_folder": {"title": FOLDER}})
    return (reply.get("routine_folder") or reply).get("id")


def routine(file: str, expected: str | None = None) -> dict[str, Any]:
    """`plsi hevy routine --file F`: check a session (every exercise id exists in Hevy) and give its hash;
    with `--hash` (the approved file's), create it as a new routine in the PLSI folder."""
    raw = Path(file).read_bytes()  # read once: the hash is of the bytes parsed and sent
    session = parse(Session, files.parse_input_json(raw.decode("utf-8")))
    digest = files.sha256_hex(raw)
    texts = [session.title, session.notes or "", *(x.notes or "" for x in session.exercises)]
    names = gate.instance_names(None)
    found = {r for t in texts for r in scan.PATTERNS if scan.hit(r, scan.normal(t))}
    found |= {"instance_name"} if any(scan.named(scan.normal(t), names) for t in texts) else set()
    if found:  # the session's text is about exercises only: no date, number, address, link or name of a person
        raise ValidationError(f"the session's text holds {', '.join(sorted(found))}", code="HEVY_TEXT_REFUSED",
                              hint="title and notes name exercises and form cues only; write a ladder as 50, 60, 70 kg")
    known = {t["id"] for t in templates()["templates"]}
    if unknown := sorted({x.exercise_template_id for x in session.exercises} - known):
        raise ValidationError(f"not a Hevy exercise id: {', '.join(unknown)}", code="HEVY_UNKNOWN_EXERCISE",
                              hint="plsi hevy templates --search <name>")
    if expected is None:
        return {"checked": True, "session_hash": digest, "exercises": len(session.exercises),
                "sets": sum(len(x.sets) for x in session.exercises)}
    if expected != digest:
        raise ValidationError("the file is not the one approved", code="HASH_MISMATCH", hint="check it again and ask again")
    body = {"routine": {"title": TITLE_PREFIX + session.title, "folder_id": _folder_id(create=True),
                        "notes": session.notes, "exercises": [x.model_dump(mode="json") for x in session.exercises]}}
    made = (_call("POST", "/v1/routines", body=body) or {}).get("routine")
    made = made[0] if isinstance(made, list) else made or {}
    return {"created": True, "routine_id": made.get("id"), "title": body["routine"]["title"], "folder": FOLDER}
