"""The user's role (individual, physician or researcher), kept in <PLSI_HOME>/role.json so skills and code can read it;
it picks the sections of the team that are set up (skills/shared/team)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files, keys, paths
from plsi.clock import now
from plsi.errors import ValidationError
from plsi.vocab import UserRole


# only a Mothership steward's machine or the Mother's own box holds these
STEWARD_KEYS = ("MOTHER_RELAY_ADMIN_KEY", "MOTHER_RELAY_INTAKE_KEY", "MOTHER_DRIVE_CREDENTIALS", "MOTHER_STORE")


def not_a_steward() -> None:
    """A steward (or the Mother) never works as a physician or researcher on the same account, so steward keys never
    sit next to patients' uploads or a researcher's sources. Raises STEWARD_ACCOUNT, naming the variables only."""
    if held := keys.present(STEWARD_KEYS):
        raise ValidationError(f"this account holds Mothership steward keys or settings ({', '.join(held)}); "
                              "a steward never works as a physician or researcher on the same account",
                              code="STEWARD_ACCOUNT",
                              hint="use a separate Grok account for professional work")


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
    """`role set`: store the user's role; a professional role is refused on a steward's account."""
    if UserRole(role) != UserRole.INDIVIDUAL:
        not_a_steward()
    files.atomic_write_json(role_path(), {"role": UserRole(role).value, "set_at": now().isoformat()})
    return show()
