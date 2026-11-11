"""A professional's Mothership identity: the steward-minted token from MOTHERSHIP_PROFESSIONAL_TOKEN (plsi.keys),
decoded locally (only the relay checks its signature), and the preregistrations and findings built with it into
<PLSI_HOME>/mothership/outbox, never an instance's folder and never with a contributor id."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from plsi import files, keys, paths, role
from plsi.clock import now
from plsi.errors import NotFound, ValidationError
from plsi.mothership import gate, stats
from plsi.mothership.relay import header
from plsi.vocab import HypothesisDirection, MothershipMessage, ProfessionalScope

TOKEN_ENV = "MOTHERSHIP_PROFESSIONAL_TOKEN"
PREREG_FIELDS = ("hypothesis", "release", "analysis", "outcome", "alpha", "direction")


def folder() -> Path:
    return paths.plsi_home() / "mothership"


def token() -> str | None:
    """The professional token; every professional command reads it, so a steward's account is refused here."""
    value = keys.get(TOKEN_ENV)
    if value is not None:
        role.not_a_steward()
    return value


def _payload(value: str) -> dict[str, Any]:
    parts = value.split(".")
    try:
        if len(parts) != 3 or parts[0] != "plsp1":
            raise ValueError("not a plsp1 token")
        found = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)).decode("utf-8"))
        if not isinstance(found, dict) or not {"pid", "role", "scopes", "exp"} <= set(found):
            raise ValueError("payload fields missing")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError(f"{TOKEN_ENV} is not a Mothership professional token ({exc})", code="BAD_TOKEN",
                              hint="paste the plsp1. token the Mothership steward sent, unchanged") from None
    return found


def _required() -> str:
    value = token()
    if value is None:
        raise NotFound("no Mothership professional token is set", code="NOT_REGISTERED",
                       hint=f"after the steward's review, set {TOKEN_ENV} with the Grok secret card (see .env.example)")
    return value


def payload(scope: ProfessionalScope | None = None) -> dict[str, Any]:
    """The decoded token payload {pid, role, scopes, exp}; raises when missing, expired or lacking `scope`."""
    found = _payload(_required())
    if found["exp"] <= now().timestamp():
        raise ValidationError("the Mothership professional token has expired", code="TOKEN_EXPIRED",
                              hint="ask the Mothership steward to renew it")
    if scope and scope not in found["scopes"]:
        raise ValidationError(f"the professional token lacks the {scope} scope", code="SCOPE_MISSING",
                              hint="ask the Mothership steward for that scope")
    return found


def whoami() -> dict[str, Any]:
    """`mothership whoami`: role, scopes and expiry of the professional token; the professional id masked."""
    found = _payload(_required())
    exp = datetime.fromtimestamp(found["exp"], UTC)
    return {"role": found["role"], "scopes": found["scopes"], "expires_at": exp.isoformat(),
            "expired": exp <= now(), "pid": f"{str(found['pid'])[:4]}…"}


def _write(doc: dict[str, Any], pid: str, name: str) -> dict[str, Any]:
    gate.require(doc, pid=pid)
    path = folder() / "outbox" / f"{name}.json"
    files.atomic_write_json(path, doc)
    return {"file": str(path), "kind": doc["kind"], "package_hash": files.hash_json(doc)}


def prereg(spec: str) -> dict[str, Any]:
    """`mothership prereg`: a preregistration (hypothesis, release, §5 analysis, outcome, alpha, direction, parents)
    with a new pr_ id, gate-checked into the professional outbox; nothing is sent."""
    pid = payload(ProfessionalScope.FINDINGS_SUBMIT)["pid"]
    given = files.load_json(spec)
    if not isinstance(given, dict):
        raise ValidationError("the preregistration is not a JSON object", code="BAD_SPEC")
    if missing := [k for k in PREREG_FIELDS if k not in given]:
        raise ValidationError(f"the preregistration lacks {', '.join(missing)}", code="BAD_SPEC")
    if not isinstance(given["alpha"], (int, float)) or not 0 < given["alpha"] < 1:
        raise ValidationError("alpha must be a number between 0 and 1", code="BAD_SPEC")
    if given["direction"] not in tuple(HypothesisDirection):
        raise ValidationError(f"direction must be one of {', '.join(HypothesisDirection)}", code="BAD_SPEC")
    stats.check_spec(given["analysis"])
    doc = header(MothershipMessage.PREREGISTRATION) | {"professional_id": pid,
           "preregistration_id": paths.new_id("pr"), **{k: given[k] for k in PREREG_FIELDS},
           "parents": given.get("parents", [])}  # anything but a list of f_ ids is refused by the gate
    return _write(doc, pid, f"preregistration-{doc['preregistration_id']}") | {"preregistration_id": doc["preregistration_id"]}


def finding(prereg: str, release: str, summary: str) -> dict[str, Any]:
    """`mothership finding`: run the preregistered analysis on the release and build the finding (new f_ id)."""
    pid = payload(ProfessionalScope.FINDINGS_SUBMIT)["pid"]
    registered = files.load_json(prereg)
    if not isinstance(registered, dict) or registered.get("kind") != MothershipMessage.PREREGISTRATION \
            or registered.get("professional_id") != pid or not {"preregistration_id", "release", "analysis"} <= set(registered):
        raise ValidationError("--prereg is not a preregistration of this professional", code="BAD_PREREGISTRATION")
    data = files.load_json(release)
    version = data.get("version") if isinstance(data, dict) else None
    if version != registered["release"]:
        raise ValidationError(f"the release is {version!r}, the preregistration names {registered['release']!r}",
                              code="RELEASE_MISMATCH", hint=f"plsi mothership release --version {registered['release']}")
    doc = header(MothershipMessage.FINDING) | {"professional_id": pid,
           "finding_id": paths.new_id("f"), "preregistration_id": registered["preregistration_id"],
           "release": registered["release"], "analysis": registered["analysis"],
           "result": stats.analyze_release(data, registered["analysis"]), "summary": summary}
    return _write(doc, pid, f"finding-{doc['finding_id']}") | {"finding_id": doc["finding_id"], "result": doc["result"]}
