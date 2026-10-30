"""Model-derived oracles: PandaClaw / PandaOmics over MCP-HTTP, L-LLM OpenAI-compatible.

URLs from env with defaults from plsi.references; HTTP only via plsi.net.post_json. The bearer token goes only to the
configured URL (net drops it on scheme or host changes); HF_TOKEN only to Hugging Face endpoints over https. With
instance + map_id the outbound text is built in code from states/<map>/latest.json only: months, values and codes, no
item text, never a local map (personal_context); a code only when valid in its system (plsi.codes) and a free or cpg
code only when a map declares it, any other item counted as "n uncoded". The exact string sent (for an MCP tool, its
arguments as JSON) is kept in <instance or PLSI_HOME>/egress/oracles.jsonl with its sha256, the same sha256 as the
reply's `sent`. Replies: {reply: ExternalText, sent: {bytes, sha256}}; errors are redacted, remote text wrapped.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from typing import Any

from plsi import codes, files, keys, net, paths, references
from plsi.clock import now
from plsi.errors import NetworkError, NotFound, ValidationError
from plsi.files import load_json, loads_json, sha256_hex
from plsi.map import mapper, registry
from plsi.models import CAP_REPLY, parse, sanitize_external
from plsi.policy.models import OracleInput

PANDACLAW_DEADLINE_S = 900
PANDACLAW_FAILED = {"failed", "error", "cancelled", "canceled"}
MAX_WAIT_SECONDS = 60
LLLM_MODES = {"local": "longevity_llm", "server": "longevity_llm_server"}  # PLSI_LLLM_MODE preset -> reference id
HF_HOSTS = (".huggingface.cloud", ".hf.space")  # where the HF_TOKEN fallback may go (https only)
CAP_ERROR = 500
CAP_TOOL = 4_000
LLLM_SYSTEM = (
    "You are a helpful assistant with expertise in aging biology. Ground every claim in established literature. "
    "If a gene symbol, CpG identifier or finding is not one you recognise from the literature, say so explicitly and do "
    "not speculate about its function. Never invent effect sizes. When given a personal state profile, stay within it "
    "and state uncertainty and missing data."
)


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
        return _external(text, net.strip_query(self.url))

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


def build_outbound(inp: OracleInput) -> str:
    """The prompt alone, or prompt + compact rendering of latest.json coordinates (value or item codes, unit, status,
    month). A local map (personal_context) never leaves; an item without a code that may leave is only counted."""
    prompt, instance, map_id = inp.prompt, inp.instance, inp.map_id
    if not (instance and map_id):
        return prompt
    if map_id in mapper.LOCAL_MAPS:
        raise ValidationError(f"map {map_id} stays on this computer", code="LOCAL_MAP",
                              hint="ask without instance and map_id, with the topic only")
    state = mapper.latest_state(instance, map_id)
    if state is None:
        raise NotFound(f"no projected state for map {map_id}", code="STATE_NOT_FOUND", hint=f"plsi project --instance {instance} --map {map_id}")
    if not state.verify_hash():
        raise ValidationError("latest.json state_hash does not verify", hint=f"plsi project --instance {instance} --map {map_id}")
    lines = [f"State map {state.map_id} v{state.map_version}, as of {state.as_of:%Y-%m}:"]
    declared = registry.declared_codes(instance)
    for cid, cv in sorted(state.coordinates.items()):
        if isinstance(cv.value, list):
            shown = [f"{i.code.system}:{i.code.code}" for i in cv.value
                     if i.code and codes.shareable(i.code.system.value, i.code.code, declared)]
            uncoded = [f"{len(cv.value) - len(shown)} uncoded"] if len(cv.value) > len(shown) else []
            value = "; ".join(shown + uncoded) or "none"
        else:
            value = "n/a" if cv.value is None else f"{cv.comparator or ''}{cv.value:g}{' ' + cv.unit if cv.unit else ''}"
        seen = f", observed {cv.observed_at:%Y-%m}" if cv.observed_at else ""
        lines.append(f"- {cid}: {value} ({cv.status.value}{seen})")
    return f"{prompt}\n\n" + "\n".join(lines)


def _external(text: str, origin: str) -> dict[str, Any]:
    return sanitize_external(keys.redact(text), CAP_ERROR, origin).model_dump(mode="json")


def _egress(oracle: str, text: str, instance: str | None = None) -> None:
    """Keep the exact string about to leave, so the user can see it: <instance or PLSI_HOME>/egress/oracles.jsonl."""
    home = paths.instance_dir(instance) if instance else paths.plsi_home()
    files.append_jsonl(home / "egress" / "oracles.jsonl",
                       {"at": now().isoformat(), "oracle": oracle, "sha256": sha256_hex(text), "text": text})


def _sent(text: str) -> dict[str, Any]:
    """What left the computer, without repeating it: {bytes, sha256}."""
    return {"bytes": len(text.encode("utf-8")), "sha256": sha256_hex(text)}


def _reply(text: str, origin: str, sent: str, **extra: Any) -> dict[str, Any]:
    reply = sanitize_external(text, CAP_REPLY, origin).model_dump(mode="json")
    return {**extra, "reply": reply, "sent": _sent(sent)}


def _client(service: str, deadline_s: float = 120.0) -> McpClient:
    """MCP client for a service; env <SERVICE>_MCP_URL overrides the reference api_base, <SERVICE>_BEARER_TOKEN is required."""
    prefix = service.upper()
    url = keys.get(f"{prefix}_MCP_URL") or references.api_base(service)
    return McpClient(url, keys.require(f"{prefix}_BEARER_TOKEN"), deadline_s=deadline_s)


def _input(file: str) -> OracleInput:
    return parse(OracleInput, load_json(file), "oracle input")


def pandaclaw(file: str | None = None, session_id: str | None = None, client: McpClient | None = None) -> dict[str, Any]:
    """`oracle pandaclaw --file F`: ask once (never retried), wait with the SAME since_seq until answer_allowed, then
    read_answer only when the run did not fail. `--session S` follows a run that is still going (after a timeout or
    interruption) without asking again."""
    args: dict[str, Any] = {"query": ""}
    instance = None
    if file:
        inp = _input(file)
        args, instance = {"query": build_outbound(inp), **({"skill": inp.skill} if inp.skill else {})}, inp.instance
    text = "" if session_id else json.dumps(args, ensure_ascii=False)  # the ask's arguments, as sent
    client = client or _client("pandaclaw", PANDACLAW_DEADLINE_S + 120)
    resuming, web_url, since = bool(session_id), None, 0
    if not resuming:
        _egress("pandaclaw", text, instance)
        asked = client.call_tool("ask", args, timeout=120)
        if not isinstance(asked, dict) or "session_id" not in asked:
            raise NetworkError("PandaClaw ask returned no session_id", code="BAD_RESPONSE")
        session_id, web_url, since = str(asked["session_id"]), asked.get("web_url"), int(asked.get("baseline_event_seq") or 0)
    base = {"session_id": session_id, "web_url": web_url, "resume": f"plsi oracle pandaclaw --session {session_id}"}
    deadline, error = time.monotonic() + PANDACLAW_DEADLINE_S, None
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {"status": "timeout", **base, "sent": _sent(text)}
            wait = max(1, min(MAX_WAIT_SECONDS, int(remaining)))
            state = client.call_tool("wait_for_answer", {"session_id": session_id, "since_seq": since, "max_wait_seconds": wait},
                                     timeout=wait + 30)
            if not isinstance(state, dict):
                continue
            base["web_url"] = base["web_url"] or state.get("web_url")
            error = next((e for e in reversed(state.get("events") or []) if e.get("type") == "error"), error)
            if state.get("answer_allowed") or state.get("answer_ready"):
                break
        run_status = str(state.get("status") or "").lower()
        if run_status in PANDACLAW_FAILED:  # the run ended without an answer; its last words are not one
            info = (error or {}).get("payload") or error or {}
            return {"status": "failed", **base, "sent": _sent(text), "run_status": run_status or "error",
                    "error": {"message": _external(str(info.get("message") or state.get("next_action") or ""), "pandaclaw"),
                              "class": _external(str(info.get("class") or ""), "pandaclaw"),
                              "resumable": info.get("resumable") is True}}
        answer = client.call_tool("read_answer", {"session_id": session_id}, timeout=120)
    except NetworkError as e:  # the analysis keeps running remotely: follow it with --session, never ask again
        error = {"code": e.code, "message": e.message, **({"remote": e.remote} if e.remote else {})}
        return {"status": "interrupted", **base, "sent": _sent(text), "error": error}
    if isinstance(answer, dict):
        answer = answer.get("result") or answer.get("answer") or json.dumps(answer, ensure_ascii=False)
    return _reply(str(answer), "pandaclaw", text, status="answered", completion=state.get("completion"), **base)


def pandaclaw_skills(catalog: str = "recommended", topic: str | None = None) -> dict[str, Any]:
    """`oracle pandaclaw-skills`: PandaClaw's skills for `skill` in the ask file (not a run, not billed)."""
    args = {"catalog": catalog, **({"topic": topic} if topic else {})}
    _egress("pandaclaw", json.dumps(args, ensure_ascii=False))
    skills = _client("pandaclaw").call_tool("list_skills", args)
    text = skills if isinstance(skills, str) else json.dumps(skills, ensure_ascii=False, indent=1)
    return {"skills": sanitize_external(text, CAP_REPLY, "pandaclaw").model_dump(mode="json")}


def pandaomics_tools() -> dict[str, Any]:
    """`oracle pandaomics tools` -> {tools: [{name, description, inputSchema}]}."""
    tools = _client("pandaomics").list_tools()
    return {"tools": [{"name": t.get("name"), "inputSchema": t.get("inputSchema"),
                       "description": sanitize_external(str(t.get("description") or ""), CAP_TOOL, "pandaomics")
                       .model_dump(mode="json")} for t in tools]}


def pandaomics_call(tool: str, file: str) -> dict[str, Any]:
    """`oracle pandaomics call --tool T --file args.json` -> {reply: ExternalText, sent}."""
    args = load_json(file)
    if not isinstance(args, dict):
        raise ValidationError("tool arguments must be a JSON object")
    sent = json.dumps(args, ensure_ascii=False)
    _egress(f"pandaomics:{tool}", sent)
    result = _client("pandaomics").call_tool(tool, args, timeout=120)
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=1)
    return _reply(text, "pandaomics", sent)


def l_llm(file: str) -> dict[str, Any]:
    """`oracle l-llm --file F`: OpenAI-compatible chat completion; everything up to `</think>` is stripped."""
    inp = _input(file)
    text = build_outbound(inp)
    mode = (keys.get("PLSI_LLLM_MODE") or "local").strip().lower()
    if not (base := keys.get("PLSI_LLLM_BASE_URL")):
        if mode not in LLLM_MODES:
            raise ValidationError(f"unknown PLSI_LLLM_MODE {mode!r}", hint="local | server, or set PLSI_LLLM_BASE_URL")
        base = references.api_base(LLLM_MODES[mode])
    thinking = (keys.get("PLSI_LLLM_ENABLE_THINKING") or "").strip().lower() in ("1", "true", "yes", "on")
    model = keys.get("PLSI_LLLM_MODEL") or "longevity-llm"
    body = {
        "model": model,
        "messages": [{"role": "system", "content": LLLM_SYSTEM}, {"role": "user", "content": text}],
        "temperature": 0, "top_p": 0.8, "top_k": 20, "repetition_penalty": 1.1,
        "max_tokens": 2200 if thinking else 700,
        "chat_template_kwargs": {"enable_thinking": thinking},  # must be nested; a top-level flag is ignored
    }
    key = keys.get("PLSI_LLLM_API_KEY") or (keys.get("HF_TOKEN") if _hugging_face(base) else None)
    _egress("l-llm", text, inp.instance)
    reply = net.post_json(f"{base.rstrip('/')}/chat/completions", body, token=key, timeout=300)
    try:
        content = reply.json()["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        raise NetworkError(f"unexpected L-LLM reply from {net.strip_query(base)}", code="BAD_RESPONSE") from None
    return _reply(content.split("</think>")[-1].strip(), "l-llm", text, model=model)


def _hugging_face(base: str) -> bool:
    """HF_TOKEN goes only to a Hugging Face endpoint over https (*.huggingface.cloud, *.hf.space)."""
    parts = urllib.parse.urlsplit(base)
    return parts.scheme == "https" and (parts.hostname or "").endswith(HF_HOSTS)
