"""A physician's or researcher's Mothership identity: the professional token the relay steward mints, read
from MOTHERSHIP_PROFESSIONAL_TOKEN via plsi.keys and decoded locally (only the relay checks its signature); and the
preregistrations and findings built from it into <PLSI_HOME>/mothership/outbox. A professional message never carries
a contributor id, and the professional folder is never an instance's."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from plsi import files, keys, paths
from plsi.clock import now
from plsi.errors import NotFound, ValidationError
from plsi.mothership import gate, stats
from plsi.mothership.relay import SCHEMA_VERSION
from plsi.vocab import HypothesisDirection, MothershipMessage, ProfessionalScope

TOKEN_ENV = "MOTHERSHIP_PROFESSIONAL_TOKEN"
PREREG_FIELDS = ("hypothesis", "release", "analysis", "outcome", "alpha", "direction")


def folder() -> Path:
    return paths.plsi_home() / "mothership"


def token() -> str | None:
    return keys.get(TOKEN_ENV)


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


def payload(scope: ProfessionalScope | None = None) -> dict[str, Any]:
    """The decoded token payload {pid, role, scopes, exp}; raises when missing, expired or lacking `scope`."""
    value = token()
    if value is None:
        raise NotFound("no Mothership professional token is set", code="NOT_REGISTERED",
                       hint=f"after the steward's review, set {TOKEN_ENV} with the Grok secret card (see .env.example)")
    found = _payload(value)
    if found["exp"] <= now().timestamp():
        raise ValidationError("the Mothership professional token has expired", code="TOKEN_EXPIRED",
                              hint="ask the Mothership steward to renew it")
    if scope and scope not in found["scopes"]:
        raise ValidationError(f"the professional token lacks the {scope} scope", code="SCOPE_MISSING",
                              hint="ask the Mothership steward for that scope")
    return found


def whoami() -> dict[str, Any]:
    """`mothership whoami`: role, scopes and expiry of the professional token; the professional id masked."""
    value = token()
    if value is None:
        payload()  # raises NOT_REGISTERED
    found = _payload(value)
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
    if missing := [k for k in PREREG_FIELDS if k not in given]:
        raise ValidationError(f"the preregistration lacks {', '.join(missing)}", code="BAD_SPEC")
    if not isinstance(given["alpha"], (int, float)) or not 0 < given["alpha"] < 1:
        raise ValidationError("alpha must be a number between 0 and 1", code="BAD_SPEC")
    stats.check_spec(given["analysis"])
    doc = {"kind": MothershipMessage.PREREGISTRATION.value, "schema_version": SCHEMA_VERSION, "professional_id": pid,
           "preregistration_id": paths.new_id("pr"), **{k: given[k] for k in PREREG_FIELDS},
           "parents": list(given.get("parents", []))}
    doc["direction"] = HypothesisDirection(doc["direction"]).value
    return _write(doc, pid, f"preregistration-{doc['preregistration_id']}") | {"preregistration_id": doc["preregistration_id"]}


def finding(prereg: str, release: str, summary: str) -> dict[str, Any]:  # noqa: A002
    """`mothership finding`: run the preregistered analysis on the release and build the finding (new f_ id)."""
    pid = payload(ProfessionalScope.FINDINGS_SUBMIT)["pid"]
    registered = files.load_json(prereg)
    if registered.get("kind") != MothershipMessage.PREREGISTRATION or registered.get("professional_id") != pid:
        raise ValidationError("--prereg is not a preregistration of this professional", code="BAD_PREREGISTRATION")
    data = files.load_json(release)
    if data.get("version") != registered["release"]:
        raise ValidationError(f"the release is {data.get('version')!r}, the preregistration names {registered['release']!r}",
                              code="RELEASE_MISMATCH", hint=f"plsi mothership release --version {registered['release']}")
    doc = {"kind": MothershipMessage.FINDING.value, "schema_version": SCHEMA_VERSION, "professional_id": pid,
           "finding_id": paths.new_id("f"), "preregistration_id": registered["preregistration_id"],
           "release": registered["release"], "analysis": registered["analysis"],
           "result": stats.analyze_release(data, registered["analysis"]), "summary": summary}
    return _write(doc, pid, f"finding-{doc['finding_id']}") | {"finding_id": doc["finding_id"], "result": doc["result"]}
