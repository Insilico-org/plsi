"""The Mothership relay client: its base URL (mothership/references/contact.yaml), one POST or GET with an
install or professional token, and the refusal reasons it passes back. Tokens travel only in the Authorization header.
A 429 (the relay's rate limit, {error: rate_limited, retry_after}) becomes RATE_LIMITED with the local time to retry."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from plsi import net, references
from plsi.clock import now
from plsi.errors import NetworkError

REFERENCE = "longevity_mothership"
SCHEMA_VERSION = 4  # the wire version every message carries
NOT_LOGGED = "nothing was logged as sent; try again at the next run"
TOKEN_ERRORS = frozenset({"unauthorized", "token_revoked", "token_expired"})


def address() -> str:
    """The relay base URL; /join (codes for the user), /enroll, /relay and /public live under it."""
    return references.api_base(REFERENCE)


def _parsed(text: str) -> Any:
    try:
        return json.loads(text) if text.strip() else {}
    except ValueError:
        return {"text": text[:500]}


def post(path: str, body: Any, token: str | None = None) -> Any:
    """POST to the relay; the reply as JSON (text when it is not JSON). Never retried."""
    return _parsed(net.post_json(f"{address()}{path}", body, token=token, timeout=60).text)


def get(path: str, token: str | None = None) -> Any:
    """GET a relay JSON document, with the professional token when given."""
    try:
        return net.get_json(f"{address()}{path}", headers={"Authorization": f"Bearer {token}"} if token else None)
    except NetworkError as exc:
        if exc.code == "BAD_RESPONSE":  # a web page instead of JSON: the deployed relay predates this route
            raise NetworkError(f"the Mothership relay does not serve {path} yet", code="NOT_SERVED",
                               hint="the relay may still run an older version; try again after it is updated") from None
        raise refused(exc, "document") from None


def _reply(exc: NetworkError) -> dict[str, Any]:
    try:
        body = json.loads(exc.body)
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def relay_error(exc: NetworkError) -> str:
    """The refusal reason: the relay's {"error"}."""
    body = _reply(exc)
    return str(body.get("error") or exc.message)


def rate_limited(exc: NetworkError) -> NetworkError:
    """RATE_LIMITED for a 429: when to try again, in local time (now + retry_after), else in an hour."""
    wait = _reply(exc).get("retry_after")
    known = isinstance(wait, (int, float)) and not isinstance(wait, bool) and 0 < wait <= 7 * 86400
    when = f"after {(now() + timedelta(seconds=wait)).astimezone():%H:%M}" if known else "in an hour"
    return NetworkError("the Mothership is limiting requests right now", status=429, code="RATE_LIMITED",
                        hint=f"nothing was sent or logged; try again {when}")


def refused(exc: NetworkError, what: str) -> NetworkError:
    """The error to raise for a refused relay call: RATE_LIMITED for a 429, TOKEN_REJECTED when the relay itself
    refused the token, else RELAY_REFUSED."""
    if exc.status == 429:
        return rate_limited(exc)
    reason = relay_error(exc)
    if exc.status == 401 and reason in TOKEN_ERRORS:
        return NetworkError(f"the Mothership relay rejected the token: {reason}", status=401, code="TOKEN_REJECTED",
                            hint=f"contributors: get a new code at {address()}/join and re-join with --code; "
                                 "professionals: ask the Mothership steward for a new professional token")
    where = "relay" if exc.status is None else "Mothership (via the relay)"
    return NetworkError(f"the {where} did not accept the {what}: HTTP {exc.status}: {reason}", status=exc.status,
                        code="RELAY_REFUSED", hint=NOT_LOGGED)
