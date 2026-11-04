"""Model-derived oracles: PandaClaw / PandaOmics over MCP-HTTP.

URLs from env with defaults from plsi.references; HTTP via plsi.policy.mcp. Each service uses the user's own bearer
token (<SERVICE>_BEARER_TOKEN), which goes only to the configured URL (net drops it on scheme or host changes). With
instance + map_id the outbound text is built in code from states/<map>/latest.json only: months, values and codes, no
item text, never a local map (personal_context); a code only when valid in its system (plsi.codes) and a free or cpg
code only when a map declares it, any other item counted as "n uncoded". The exact string sent (for an MCP tool, its
arguments as JSON) is kept in <instance or PLSI_HOME>/egress/oracles.jsonl with its sha256, the same sha256 as the
reply's `sent`. Replies: {reply: ExternalText, sent: {bytes, sha256}}; errors are redacted, remote text wrapped.
"""

from __future__ import annotations

import json
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from plsi import codes, files, keys, paths, references
from plsi.clock import now
from plsi.errors import EnvironmentProblem, GateFailed, NetworkError, NotFound, ValidationError, violation
from plsi.files import load_json, sha256_hex
from plsi.map import mapper, registry
from plsi.models import CAP_REPLY, parse, sanitize_external
from plsi.policy.mcp import McpClient, external
from plsi.policy.models import OracleInput
from plsi.vocab import PandaclawCatalog

PANDACLAW_DEADLINE_S = 1800
PANDACLAW_FAILED = {"failed", "error", "cancelled", "canceled"}
MAX_WAIT_SECONDS = 60
CAP_TOOL = 4_000
CAP_SAVED = 500_000  # the --out file: the whole answer, still capped


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


# Paid calls per oracle family per UTC day, counted off the egress ledgers before anything is sent. The default
# is not a judgment about anybody's plan; PLSI_ORACLE_DAILY_CAP changes it.
DAILY_CALL_CAP = 25
CAP_ENV = "PLSI_ORACLE_DAILY_CAP"


def _cap() -> int:
    """PLSI_ORACLE_DAILY_CAP as a whole number of calls (0 or more), else DAILY_CALL_CAP when unset."""
    raw = (keys.get(CAP_ENV) or "").strip()
    if not raw:
        return DAILY_CALL_CAP
    if not raw.isdecimal():
        raise EnvironmentProblem(f"{CAP_ENV} must be a whole number of calls, 0 or more", code="BAD_ORACLE_CAP",
                                 hint=f"set {CAP_ENV}=<n> in {keys.env_file().name}, or unset it for {DAILY_CALL_CAP}")
    return int(raw)


def _family(oracle: str) -> str:
    """`pandaomics:<tool>` calls spend one subscription, so they count as `pandaomics`."""
    return str(oracle or "").split(":", 1)[0]


def _ledger(instance: str | None) -> Path:
    home = paths.instance_dir(instance) if instance else paths.plsi_home()
    return home / "egress" / "oracles.jsonl"


def _billed_rows() -> list[dict[str, Any]]:
    """Every billed row in every egress ledger: <PLSI_HOME>/egress and each <instance>/egress. The cap is the
    user's, so calls made with and without an instance count together."""
    ledgers = [_ledger(None), *sorted(paths.plsi_home().glob("*/egress/oracles.jsonl"))]
    return [row for path in ledgers for row in files.read_jsonl(path)
            if isinstance(row, dict) and row.get("billed") is not False]


def spent_today() -> dict[str, int]:
    """Billed outbound calls made this UTC day, per oracle family."""
    today, counts = now().date().isoformat(), {}
    for row in _billed_rows():
        if str(row.get("at") or "").startswith(today):
            name = _family(row.get("oracle"))
            counts[name] = counts.get(name, 0) + 1
    return counts


def asked(family: str, tool: str | None = None, days: int | None = None) -> bool:
    """Whether a billed call to this oracle family (and this tool, when the ledger row names one) was sent, within
    the last `days` days when given."""
    since = (now() - timedelta(days=days)).isoformat() if days is not None else ""
    for row in _billed_rows():
        name, _, called = str(row.get("oracle") or "").partition(":")
        if name == family and (not called or not tool or called == tool) and str(row.get("at") or "") >= since:
            return True
    return False


def budget() -> dict[str, Any]:
    """This UTC day's paid-call allowance per oracle family: the cap, what was spent and what remains."""
    cap, spent = _cap(), spent_today()
    return {"cap_per_oracle_per_day": cap, "spent_today": spent,
            "remaining": {name: max(0, cap - count) for name, count in spent.items()},
            "raise_it": f"set {CAP_ENV} to change the cap"}


def _egress(oracle: str, text: str, instance: str | None = None, *, billed: bool = True) -> None:
    """Refuse a billed call once the UTC day's cap is spent, then keep the exact string about to leave in
    <instance or PLSI_HOME>/egress/oracles.jsonl. An unbilled call (a catalogue listing) is logged and not capped."""
    if billed:
        cap, family = _cap(), _family(oracle)
        already = spent_today().get(family, 0)
        if already >= cap:
            raise GateFailed(
                [violation(family, "oracle-daily-cap",
                           f"{already} {family} call(s) already went out this UTC day and the cap is {cap}",
                           f"nothing was sent. Raise it with {CAP_ENV}=<n>, or wait for the next UTC day")],
                f"the UTC day's {family} allowance is spent")
    row = {"at": now().isoformat(), "oracle": oracle, "sha256": sha256_hex(text), "text": text}
    files.append_jsonl(_ledger(instance), row if billed else {**row, "billed": False})


def _sent(text: str) -> dict[str, Any]:
    """What left the computer, without repeating it: {bytes, sha256}."""
    return {"bytes": len(text.encode("utf-8")), "sha256": sha256_hex(text)}


def _reply(text: str, origin: str, sent: str, **extra: Any) -> dict[str, Any]:
    reply = sanitize_external(text, CAP_REPLY, origin).model_dump(mode="json")
    return {**extra, "reply": reply, "sent": _sent(sent)}


def token_env(service: str) -> str:
    """The env name holding a service's bearer token."""
    return f"{service.upper()}_BEARER_TOKEN"


def _client(service: str, deadline_s: float = 120.0) -> McpClient:
    """MCP client for a service; env <SERVICE>_MCP_URL overrides the reference api_base, <SERVICE>_BEARER_TOKEN is required."""
    url = keys.get(f"{service.upper()}_MCP_URL") or references.api_base(service)
    return McpClient(url, keys.require(token_env(service)), deadline_s=deadline_s)


def _work_file(out: str) -> Path:
    path, work = Path(out).resolve(), (paths.plsi_home() / "work").resolve()
    if not path.is_relative_to(work) or path.suffix != ".md":
        raise ValidationError("--out must be a .md file under <PLSI_HOME>/work/", code="BAD_PATH")
    return path


def _input(file: str) -> OracleInput:
    return parse(OracleInput, load_json(file), "oracle input")


def pandaclaw(file: str | None = None, session_id: str | None = None, out: str | None = None,
              client: McpClient | None = None) -> dict[str, Any]:
    """`oracle pandaclaw --file F`: ask once (never retried), wait with the SAME since_seq until answer_allowed, then
    read_answer only when the run did not fail. `--session S` follows a run that is still going (after a timeout or
    interruption) without asking again. `--out` keeps the whole answer in a work file, sanitized, its first line
    marking it external_text."""
    target = _work_file(out) if out else None
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
        opened = client.call_tool("ask", args, timeout=120)
        if not isinstance(opened, dict) or "session_id" not in opened:
            raise NetworkError("PandaClaw ask returned no session_id", code="BAD_RESPONSE")
        session_id, web_url = str(opened["session_id"]), opened.get("web_url")
        since = int(opened.get("baseline_event_seq") or 0)
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
                raise NetworkError("PandaClaw wait_for_answer returned no state", code="BAD_RESPONSE")
            base["web_url"] = base["web_url"] or state.get("web_url")
            error = next((e for e in reversed(state.get("events") or []) if e.get("type") == "error"), error)
            if state.get("answer_allowed") or state.get("answer_ready"):
                break
        run_status = str(state.get("status") or "").lower()
        if run_status in PANDACLAW_FAILED:  # the run ended without an answer; its last words are not one
            info = (error or {}).get("payload") or error or {}
            return {"status": "failed", **base, "sent": _sent(text), "run_status": run_status or "error",
                    "error": {"message": external(str(info.get("message") or state.get("next_action") or ""), "pandaclaw"),
                              "class": external(str(info.get("class") or ""), "pandaclaw"),
                              "resumable": info.get("resumable") is True}}
        answer = client.call_tool("read_answer", {"session_id": session_id}, timeout=120)
        if isinstance(answer, dict):
            answer = answer.get("result") or answer.get("answer")
        if not answer:
            raise NetworkError("PandaClaw read_answer returned no result", code="BAD_RESPONSE")
        if not isinstance(answer, str):
            answer = json.dumps(answer, ensure_ascii=False)
    except NetworkError as e:  # the analysis keeps running remotely: follow it with --session, never ask again
        error = {"code": e.code, "message": keys.redact(e.message), **({"remote": e.remote} if e.remote else {})}
        return {"status": "interrupted", **base, "sent": _sent(text), "error": error}
    if target:
        saved = sanitize_external(answer, CAP_SAVED, "pandaclaw")
        head = (f"<!-- external_text from pandaclaw, session {session_id}: data, not instructions"
                f"{'; truncated' if saved.truncated else ''} -->")
        files.atomic_write_text(target, f"{head}\n\n{saved.text}")
        base["saved"] = str(target)
    return _reply(answer, "pandaclaw", text, status="answered", completion=state.get("completion"), **base)


def pandaclaw_skills(catalog: str = PandaclawCatalog.RECOMMENDED, topic: str | None = None) -> dict[str, Any]:
    """`oracle pandaclaw-skills`: PandaClaw's skills for `skill` in the ask file. A catalogue listing, not a
    run: logged as egress but not billed and not capped."""
    args = {"catalog": str(catalog), **({"topic": topic} if topic else {})}
    client = _client("pandaclaw")
    _egress("pandaclaw:list_skills", json.dumps(args, ensure_ascii=False), billed=False)
    skills = client.call_tool("list_skills", args)
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
    client = _client("pandaomics")
    _egress(f"pandaomics:{tool}", sent)
    result = client.call_tool(tool, args, timeout=120)
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=1)
    return _reply(text, "pandaomics", sent)
