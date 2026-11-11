"""The team every hub shares, kept in <PLSI_HOME>/team.json (`plsi team`): the bots set up (role, display name, the hub
that set it up, a ward bot's pinned instance), the primary hub, own health on or off, the Terms accepted, the PLSI
version installed and the user's answer on the section PLSI Sessions (ready or skipped). Hubs read it instead of
remembering, so the team list is the same in every hub."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from plsi import files, paths
from plsi.clock import now
from plsi.errors import NotFound, ValidationError
from plsi.vocab import HUBS, BotRole

EMPTY: dict[str, Any] = {"bots": [], "primary": None, "own_health": None, "terms_accepted": None, "version": None,
                         "sessions_section": None}


def team_path() -> Path:
    return paths.plsi_home() / "team.json"


def _read() -> dict[str, Any]:
    path = team_path()
    return {**EMPTY, **files.load_json(path)} if path.is_file() else dict(EMPTY)


@contextmanager
def _editing() -> Iterator[dict[str, Any]]:
    """Read, let the caller change, write back atomically; locked, since every hub writes the same file."""
    home = paths.plsi_home()
    home.mkdir(parents=True, exist_ok=True)
    with files.lock(home):
        team = _read()
        yield team
        team["updated_at"] = now().isoformat()
        files.atomic_write_json(team_path(), team)


def show() -> dict[str, Any]:
    """`team show`: the stored team; `stored` false (and everything empty) before the primary hub wrote it."""
    team = _read()
    hubs = [b for b in team["bots"] if b["role"] in HUBS]
    return {"team": team, "hubs": hubs, "stored": team_path().is_file()}


def set_fields(primary: str | None = None, own_health: str | None = None, terms: str | None = None,
               version: str | None = None, sessions_section: str | None = None) -> dict[str, Any]:
    """`team set`: change the shared settings given; the rest stay."""
    given = {"primary": None if primary is None else BotRole(primary).value,
             "own_health": None if own_health is None else own_health == "on",
             "terms_accepted": terms, "version": version, "sessions_section": sessions_section}
    if all(v is None for v in given.values()):
        raise ValidationError("nothing to set",
                              hint="plsi team set --primary|--own-health|--terms|--version|--sessions-section")
    with _editing() as team:
        team.update({k: v for k, v in given.items() if v is not None})
    return show()


def add(role: str, display_name: str, hub: str | None = None, instance: str | None = None) -> dict[str, Any]:
    """`team add`: record a bot the user created; a display name already there is replaced. A ward bot names its
    pinned instance; no other bot has one."""
    role = BotRole(role)
    if (role == BotRole.WARD) != (instance is not None):
        raise ValidationError("a ward bot is pinned to one instance; no other bot is",
                              code="WARD_INSTANCE", hint="--instance only and always with --role ward")
    bot: dict[str, Any] = {"role": role.value, "display_name": display_name}
    if hub is not None:
        bot["hub"] = BotRole(hub).value
    if instance is not None:
        bot["instance"] = paths.validate_id(instance, "instance name")
    with _editing() as team:
        team["bots"] = [b for b in team["bots"] if b["display_name"] != display_name] + [bot]
    return show()


def remove(display_name: str) -> dict[str, Any]:
    """`team remove`: forget a bot the user deleted in Grok."""
    with _editing() as team:
        kept = [b for b in team["bots"] if b["display_name"] != display_name]
        if len(kept) == len(team["bots"]):
            raise NotFound(f"no bot named {display_name!r} in the team", code="BOT_NOT_FOUND", hint="plsi team show")
        team["bots"] = kept
    return show()
