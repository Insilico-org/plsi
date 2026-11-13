"""`plsi doctor`: versions, extras, PLSI_HOME, keys (booleans + what each unlocks) and fixes; --online checks
that every reference's api_base answers. `plsi clocks install`: the clocks extra's packages only, never plsi itself."""

from __future__ import annotations

import importlib.metadata
import platform
import re
import subprocess
import sys
from typing import Any

from plsi import __version__, errors, keys, net, paths, references

REACH_TIMEOUT_S = 15  # per reference, for --online
PIP_TIMEOUT_S = 1800  # the clocks packages are large
_PY = f"{sys.version_info.major}.{sys.version_info.minor}"
# (pattern in pip's output, likely cause, next step), first match wins
CLOCKS_FAILURES = (
    (r"Python\.h|pyconfig\.h|python3(\.\d+)?-dev",
     "the Python headers needed to build a package are missing",
     f"install them (on Debian/Ubuntu: sudo apt-get install python{_PY}-dev; if apt reports a lock, wait for the "
     "other install to finish; if a mirror fails, retry later), then run plsi clocks install again"),
    (r"HTTP error 5\d\d|5\d\d Server Error|Could not fetch URL|Read timed out|Temporary failure in name resolution"
     r"|Failed to establish a new connection",
     "the package index could not be reached",
     "retry plsi clocks install later"),
    (r"No matching distribution|Could not find a version|Failed (to )?build|Could not build wheels"
     r"|subprocess-exited-with-error|requires a different Python",
     f"a clocks package has no ready-made build for Python {_PY} (e.g. ecos on 3.13)",
     "use PLSI from a Python 3.11 or 3.12 environment for methylation clocks"),
)


def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def _reachable(url: str) -> str:
    try:
        net.request("GET", url, timeout=REACH_TIMEOUT_S)
        return "ok"
    except errors.NetworkError as exc:
        return "ok" if exc.status is not None else "unreachable"


def doctor(online: bool = False) -> dict[str, Any]:
    versions = {"plsi": __version__, "python": platform.python_version(), "pydantic": _version("pydantic"),
                "pyyaml": _version("PyYAML"), "biolearn": _version("biolearn")}
    home = paths.plsi_home()
    fixes: list[str] = []
    if versions["biolearn"] is None:
        fixes.append(f"methylation clocks (optional): {errors.CLOCKS_EXTRA}")
    if not keys.env_file().is_file():
        fixes.append("optional keys: copy .env.example to .env and fill only what you use")
    try:
        refs = references.load()
    except errors.PlsiError as exc:
        refs = {}
        fixes.append(f"mothership/references/ is invalid: {exc.message}")
    status = keys.status()
    out: dict[str, Any] = {
        "versions": versions,
        "extras": {"clocks": versions["biolearn"] is not None},
        "plsi_home": str(home),
        "plsi_home_exists": home.is_dir(),
        "keys": {name: {"set": is_set, "unlocks": keys.UNLOCKS[name]} for name, is_set in status.items()},
        "references": len(refs),
        "maps": sorted(p.stem for p in paths.MAPS_DIR.glob("*.yaml")),
        "fixes": fixes,
    }
    if online:
        out["reachability"] = {ref.id: _reachable(ref.api_base) for ref in refs.values() if ref.api_base}
    return out


def clocks_requirements() -> list[str]:
    """The `clocks` extra's requirements, from plsi's own package metadata (pyproject's [clocks])."""
    try:
        reqs = importlib.metadata.requires("plsi") or []
    except importlib.metadata.PackageNotFoundError:
        raise errors.DependencyMissing("plsi is not installed as a package",
                                       hint="python -m pip install -e <repo>") from None
    out = [r.split(";")[0].strip() for r in reqs if re.search(r"""extra\s*==\s*["']clocks["']""", r)]
    if not out:
        raise errors.DependencyMissing("plsi's package metadata lists no clocks extra",
                                       hint="python -m pip install -e <repo>, then plsi clocks install")
    return out


def clocks_failure(output: str) -> tuple[str, str]:
    """The likely cause and next step for a failed clocks install, from pip's output. The headers check reads it
    all (the compiler prints outside pip's ERROR lines); the rest skip WARNING lines, where pip logs retries."""
    errors_only = "\n".join(line for line in output.splitlines() if not line.lstrip().startswith("WARNING"))
    for i, (pattern, cause, step) in enumerate(CLOCKS_FAILURES):
        if re.search(pattern, output if i == 0 else errors_only, re.IGNORECASE):
            return cause, step
    last = (output.strip().splitlines() or ["no output"])[-1][:200]
    return f"pip failed: {last}", "retry plsi clocks install later"


def _run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run([sys.executable, *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise errors.DependencyMissing("methylation clocks not installed: pip took too long (the package index may "
                                       "be slow); PLSI works without them",
                                       hint="retry plsi clocks install later") from None


def install_clocks() -> dict[str, Any]:
    """`plsi clocks install`: pip-install only the clocks packages (binary builds preferred), then check that plsi
    still imports and biolearn does. A failure leaves the extra off, with one cause and next step."""
    reqs = clocks_requirements()
    proc = _run(["-m", "pip", "install", "--prefer-binary", *reqs], PIP_TIMEOUT_S)
    if proc.returncode != 0:
        cause, step = clocks_failure(proc.stdout + proc.stderr)
        raise errors.DependencyMissing(f"methylation clocks not installed: {cause}; PLSI works without them",
                                       hint=step)
    if _run(["-c", "import plsi.cli"]).returncode != 0:
        raise errors.DependencyMissing("plsi no longer imports after the clocks install",
                                       hint="python -m pip install -e <repo>")
    check = _run(["-c", "import biolearn"])
    if check.returncode != 0:
        cause, step = clocks_failure(check.stderr)
        raise errors.DependencyMissing(f"biolearn is installed but does not import: {cause}", hint=step)
    return {"installed": reqs, "biolearn": _version("biolearn")}
