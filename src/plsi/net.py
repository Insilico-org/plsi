"""Plain HTTP client. The only module that opens network connections.

- 10 s connect / per-read timeout, 60 s total, 10 MB response cap.
- GET retries once on a connection error or 5xx; POST is never retried.
- Authorization is dropped on any redirect that changes scheme or host; a POST is never redirected to another scheme
  or host, and no request follows an https -> http downgrade.
- Non-2xx -> NetworkError(status=..., body=...) so callers can treat e.g. 404 as "not found".
- openFDA 404 NOT_FOUND counts as an empty result.
- Error messages are redacted and carry URLs without query strings.
"""

from __future__ import annotations

import http.client
import json
import os
import ssl
import time
import urllib.parse
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from plsi import __version__
from plsi.keys import redact
from plsi.errors import NetworkError
from plsi.files import loads_json

CONNECT_TIMEOUT_S = 10.0
TOTAL_TIMEOUT_S = 60.0
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 5
USER_AGENT = f"plsi/{__version__}"


@dataclass(frozen=True)
class Reply:
    status: int
    headers: dict[str, str] = field(default_factory=dict)  # lower-cased names
    text: str = ""
    url: str = ""

    def json(self) -> Any:
        return loads_json(self.text)


def strip_query(url: str) -> str:
    """URL without query string or fragment (URLs are stored and reported this way)."""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


@lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    try:
        return ssl.create_default_context()
    except ssl.SSLError:  # a malformed OS cert store entry breaks load_default_certs; use a CA bundle file instead
        cafile = ssl.get_default_verify_paths().cafile
        if not cafile or not os.path.isfile(cafile):
            import certifi  # type: ignore[import-not-found]

            cafile = certifi.where()
        return ssl.create_default_context(cafile=cafile)


def _with_params(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
    return f"{url}{'&' if '?' in url else '?'}{query}"


def request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = TOTAL_TIMEOUT_S,
) -> Reply:
    """One HTTP exchange with the rules above. Returns Reply for 2xx, raises NetworkError otherwise."""
    full = _with_params(url, params)
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    attempts = 2 if method == "GET" else 1
    for attempt in range(attempts):
        retry = attempt + 1 < attempts
        try:
            return _once(method, full, hdrs, body, timeout)
        except NetworkError as exc:
            if retry and exc.code == "NETWORK_ERROR" and (exc.status is None or exc.status >= 500):
                time.sleep(0.5)
                continue
            raise
    raise AssertionError("unreachable")


def _once(method: str, url: str, headers: dict[str, str], body: bytes | None, timeout: float) -> Reply:
    deadline = time.monotonic() + timeout
    for _ in range(MAX_REDIRECTS + 1):
        parts = urllib.parse.urlsplit(url)
        shown = strip_query(url)
        if parts.scheme not in ("http", "https"):
            raise NetworkError(f"unsupported URL scheme: {shown}")
        conn = _connection(parts, shown)
        try:
            conn.connect()
            conn.sock.settimeout(max(0.1, deadline - time.monotonic()))  # connect 10 s, then the total budget
            target = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
            conn.request(method, target, body=body, headers=headers)
            resp = conn.getresponse()
            data = _read_capped(resp, deadline, shown)
        except (OSError, http.client.HTTPException) as exc:
            raise NetworkError(redact(f"{method} {shown} failed: {exc}")) from None
        finally:
            conn.close()
        location = resp.getheader("Location")
        if resp.status in (301, 302, 303, 307, 308) and location:
            new = urllib.parse.urljoin(url, location)
            target_parts = urllib.parse.urlsplit(new)
            if parts.scheme == "https" and target_parts.scheme == "http":
                raise NetworkError(f"refused a redirect of {shown} from https to http", code="REDIRECT_REFUSED")
            if method == "POST" and (target_parts.scheme, target_parts.netloc) != (parts.scheme, parts.netloc):
                raise NetworkError(f"refused a redirect of POST {shown} to another scheme or host", code="REDIRECT_REFUSED")
            if (target_parts.scheme, target_parts.netloc) != (parts.scheme, parts.netloc):
                headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
            if resp.status == 303 or (resp.status in (301, 302) and method == "POST"):
                method, body = "GET", None
            url = new
            continue
        text = data.decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
        if 200 <= resp.status < 300:
            return Reply(resp.status, {k.lower(): v for k, v in resp.getheaders()}, text, url)
        raise NetworkError(redact(f"HTTP {resp.status} from {shown}"), status=resp.status, body=redact(text[:2000]))
    raise NetworkError(f"too many redirects from {strip_query(url)}")


def _connection(parts: urllib.parse.SplitResult, shown: str) -> http.client.HTTPConnection:
    if parts.scheme == "http":
        return http.client.HTTPConnection(parts.hostname or "", parts.port, timeout=CONNECT_TIMEOUT_S)
    try:
        context = _ssl_context()
    except (OSError, ImportError) as exc:
        raise NetworkError(f"no usable TLS trust store for {shown}: {exc}") from None
    return http.client.HTTPSConnection(parts.hostname or "", parts.port, timeout=CONNECT_TIMEOUT_S, context=context)


def _read_capped(resp: Any, deadline: float, shown: str) -> bytes:
    chunks, size = [], 0
    while chunk := resp.read(65536):
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise NetworkError(f"response from {shown} exceeds {MAX_RESPONSE_BYTES} bytes", code="RESPONSE_TOO_LARGE")
        if time.monotonic() > deadline:
            raise NetworkError(f"{shown} exceeded its deadline", code="NETWORK_TIMEOUT")
        chunks.append(chunk)
    return b"".join(chunks)


def get_text(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> str:
    return request("GET", url, params=params, headers=headers).text


def get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    """GET and parse JSON (NaN rejected). openFDA 404 NOT_FOUND -> {"meta":{"results":{"total":0}},"results":[]}."""
    try:
        reply = request("GET", url, params=params, headers={"Accept": "application/json", **(headers or {})})
    except NetworkError as exc:
        if exc.status == 404 and urllib.parse.urlsplit(url).netloc == "api.fda.gov" and "NOT_FOUND" in exc.body:
            return {"meta": {"results": {"total": 0}}, "results": []}
        raise
    try:
        return reply.json()
    except ValueError:
        raise NetworkError(f"invalid JSON from {strip_query(url)}", code="BAD_RESPONSE") from None


def post_json(url: str, body: Any, headers: dict[str, str] | None = None, *, token: str | None = None,
              timeout: float = TOTAL_TIMEOUT_S) -> Reply:
    """POST a JSON body once (never retried); `token` is sent as a Bearer Authorization header.
    Returns the raw Reply: callers parse JSON or SSE and read headers."""
    data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **(headers or {})}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    return request("POST", url, headers=hdrs, body=data, timeout=timeout)
