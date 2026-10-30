"""Error types (CLI exit codes), gate violations, and warnings collected into the CLI envelope."""

from __future__ import annotations

from typing import Any


class PlsiError(Exception):
    """Base error. `code` goes into the envelope; `exit_code` 1 = refused, 2 = usage, 3 = environment."""

    code = "ERROR"
    exit_code = 1

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        hint: str | None = None,
        violations: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or type(self).code
        self.hint = hint
        self.violations = violations


class ValidationError(PlsiError):
    code = "VALIDATION_ERROR"


class GateFailed(PlsiError):
    """Raised with ALL violations: [{path, rule}] from the Mothership gate, [{path, rule, message, hint}] elsewhere."""

    code = "GATE_FAILED"

    def __init__(self, violations: list[dict[str, str]], message: str = "gate check failed") -> None:
        super().__init__(f"{message} ({len(violations)} violation(s))", violations=violations)


class NotFound(PlsiError):
    code = "NOT_FOUND"


class UsageError(PlsiError):
    code = "USAGE"
    exit_code = 2


class EnvironmentProblem(PlsiError):
    exit_code = 3


class NetworkError(EnvironmentProblem):
    """`status` is the HTTP status when the server answered (e.g. 404), else None; `remote` the server's own words,
    wrapped as ExternalText (models.sanitize_external) by the caller, never part of `message`."""

    code = "NETWORK_ERROR"

    def __init__(self, message: str, *, status: int | None = None, body: str = "", remote: dict[str, Any] | None = None,
                 **kw: Any) -> None:
        super().__init__(message, **kw)
        self.status = status
        self.body = body
        self.remote = remote


class KeyMissing(EnvironmentProblem):
    code = "KEY_MISSING"


class DependencyMissing(EnvironmentProblem):
    code = "DEPENDENCY_MISSING"


class InstanceLocked(EnvironmentProblem):
    code = "INSTANCE_LOCKED"


def violation(path: str, rule: str, message: str, hint: str = "") -> dict[str, str]:
    return {"path": path, "rule": rule, "message": message, "hint": hint}


_WARNINGS: list[dict[str, str]] = []


def warn(code: str, message: str) -> None:
    _WARNINGS.append({"code": code, "message": message})


def drain_warnings() -> list[dict[str, str]]:
    out = list(_WARNINGS)
    _WARNINGS.clear()
    return out
