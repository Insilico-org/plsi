"""The user's role (individual, physician or researcher), kept in <PLSI_HOME>/role.json so skills and code can read it;
it picks the sections of the team that are set up (skills/shared/team)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files, paths
from plsi.clock import now
from plsi.vocab import UserRole


def role_path() -> Path:
    return paths.plsi_home() / "role.json"


def show() -> dict[str, Any]:
    """`role show`: the stored role; `individual` with stored false when none was set."""
    path = role_path()
    if not path.is_file():
        return {"role": UserRole.INDIVIDUAL.value, "stored": False}
    found = files.load_json(path)
    return {"role": UserRole(found["role"]).value, "stored": True, "set_at": found.get("set_at")}


def set_role(role: str) -> dict[str, Any]:
    """`role set`: store the user's role."""
    files.atomic_write_json(role_path(), {"role": UserRole(role).value, "set_at": now().isoformat()})
    return show()
