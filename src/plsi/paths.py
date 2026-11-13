"""Ids, instance directories and safe path joining (Windows-aware)."""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path, PurePosixPath, PureWindowsPath

from plsi.errors import EnvironmentProblem, NotFound, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPS_DIR = REPO_ROOT / "maps"  # the shipped State Maps
# repo data the package reads from its folder; a non-editable (wheel) install leaves them behind
REPO_DATA = ("maps", "mothership/consent.md", "mothership/references")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {f"{p}{i}" for p in ("com", "lpt") for i in range(1, 10)}
# <PLSI_HOME> folders that are not instances: never an instance name
HOME_DIRS = frozenset({"egress", "extensions", "feedback", "inbox", "mothership", "research", "targets", "work"})


def is_reserved(name: str) -> bool:
    return name.split(".")[0].lower() in _WINDOWS_RESERVED


def is_valid_id(value: str) -> bool:
    return bool(ID_RE.fullmatch(value)) and not is_reserved(value)


def validate_id(value: str, what: str = "id") -> str:
    if not isinstance(value, str) or not is_valid_id(value):
        raise ValidationError(f"invalid {what}: {value!r}", hint=f"must match {ID_RE.pattern} and not be a Windows reserved name")
    return value


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def require_repo_data() -> None:
    """REPO_ROOT holds the shipped maps, consent and references, else one clear error (exit 3)."""
    if missing := [rel for rel in REPO_DATA if not (REPO_ROOT / rel).exists()]:
        raise EnvironmentProblem("PLSI must be installed from its folder: python -m pip install -e <repo>",
                                 code="NOT_INSTALLED_FROM_REPO",
                                 hint=f"<repo> is the PLSI folder; {', '.join(missing)} not found under {REPO_ROOT}")


def plsi_home() -> Path:
    return Path(os.environ.get("PLSI_HOME") or REPO_ROOT / "instances")


def instance_dir(name: str, *, must_exist: bool = True) -> Path:
    if validate_id(name, "instance name") in HOME_DIRS:
        raise ValidationError(f"{name!r} is a PLSI_HOME folder, not an instance", code="INSTANCE_NAME_RESERVED")
    path = safe_join(plsi_home(), name)
    if must_exist and not (path / "subject.json").is_file():
        raise NotFound(f"instance {name!r} does not exist", code="INSTANCE_NOT_FOUND",
                       hint=f"not created yet: plsi init --instance {name}; a worker not asked to create it replies "
                            "'blocked: the record is not created yet' and waits to be sent it again")
    return path


def safe_join(base: Path | str, *parts: str) -> Path:
    """Join relative parts under base; reject absolute, drive-relative, '..', ':' and escapes."""
    base_path = Path(base).resolve()
    for part in parts:
        p = str(part)
        if not p or ":" in p or "\x00" in p or PureWindowsPath(p).anchor or PurePosixPath(p).is_absolute():
            raise ValidationError(f"unsafe path component: {p!r}")
        segs = re.split(r"[\\/]", p)
        if ".." in segs:
            raise ValidationError(f"unsafe path component: {p!r}")
        if any(is_reserved(s) for s in segs if s):
            raise ValidationError(f"reserved name in path: {p!r}")
    joined = base_path.joinpath(*parts).resolve()
    if joined != base_path and base_path not in joined.parents:
        raise ValidationError(f"path escapes base: {'/'.join(parts)!r}")
    return joined
