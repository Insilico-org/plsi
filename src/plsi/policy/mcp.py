"""A minimal MCP streamable-HTTP JSON-RPC client (initialize, tools/list, tools/call), over plsi.net only."""

from __future__ import annotations

import json
import time
from typing import Any

from plsi import keys, net
from plsi.errors import NetworkError
from plsi.files import loads_json
from plsi.models import sanitize_external

CAP_ERROR = 500


def external(text: str, origin: str) -> dict[str, Any]:
    """Remote text, secrets redacted, as an ExternalText dict."""
    return sanitize_external(keys.redact(text), CAP_ERROR, origin).model_dump(mode="json")


class McpClient:
    """Minimal MCP streamable-HTTP JSON-RPC client: initialize, then tools/list and tools/call."""

    def __init__(self, url: str, token: str | None, *, deadline_s: float = 120.0) -> None:
        self.url, self._token = url, token
        self._deadline = time.monotonic() + deadline_s
        self._session: str | None = None
        self._next_id = 0
        self._ready = False

    def _post(self, payload: dict[str, Any], timeout: float) -> list[dict[str, Any]]:
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise NetworkError(f"MCP deadline exceeded for {net.strip_query(self.url)}", code="NETWORK_TIMEOUT")
        headers = {"mcp-session-id": self._session} if self._session else {}
        reply = net.post_json(self.url, payload, headers, token=self._token, timeout=min(timeout, remaining))
        self._session = reply.headers.get("mcp-session-id") or self._session
        text = reply.text.strip()
        try:
            if text.startswith("{"):
                return [loads_json(text)]
            return [loads_json(line[5:]) for line in text.splitlines() if line.startswith("data:") and line[5:].strip()]
        except ValueError:
            raise NetworkError(f"unparseable MCP reply from {net.strip_query(self.url)}", code="BAD_RESPONSE") from None

    def _rpc(self, method: str, params: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
        if not self._ready and method != "initialize":
            self._ready = True
            self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                     "clientInfo": {"name": "plsi", "version": "1"}})
            try:
                self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, 30.0)
            except NetworkError:
                pass  # some servers answer notifications with an error status; the session still works
        self._next_id += 1
        msgs = self._post({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}, timeout)
        msg = next((m for m in msgs if m.get("id") == self._next_id), msgs[0] if msgs else None)
        if msg is None:
            raise NetworkError(f"empty MCP reply to {method}", code="BAD_RESPONSE")
        if "error" in msg:
            raise NetworkError(f"MCP error on {method}", code="MCP_ERROR", remote=self._remote(json.dumps(msg["error"])))
        return msg.get("result") or {}

    def _remote(self, text: str) -> dict[str, Any]:
        return external(text, net.strip_query(self.url))

    def list_tools(self) -> list[dict[str, Any]]:
        tools, cursor = [], None
        while True:
            result = self._rpc("tools/list", {"cursor": cursor} if cursor else {})
            tools += result.get("tools", [])
            if not (cursor := result.get("nextCursor")):
                return tools

    def call_tool(self, name: str, arguments: dict[str, Any], *, timeout: float = 60.0) -> Any:
        """structuredContent if present, else parsed content text JSON, else the text."""
        result = self._rpc("tools/call", {"name": name, "arguments": arguments}, timeout)
        texts = "\n".join(p.get("text", "") for p in result.get("content") or [] if p.get("type") == "text").strip()
        if result.get("isError"):
            raise NetworkError(f"tool {name} failed", code="MCP_TOOL_ERROR", remote=self._remote(texts))
        sc = result.get("structuredContent")
        if sc is not None:
            return sc["result"] if isinstance(sc, dict) and set(sc) == {"result"} else sc
        try:
            return json.loads(texts)
        except ValueError:
            return texts
