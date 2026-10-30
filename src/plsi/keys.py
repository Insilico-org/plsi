"""The ONE key mechanism: env vars, with a repo-root `.env` as fallback.

Process env overrides `.env`. A key may also come from a secret the user already has under another name: the bot
maps it once (`plsi keys map`), and only the two names are stored, in <PLSI_HOME>/keys-map.json. Values are never
printed, logged or stored; `redact()` masks them.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from plsi import files
from plsi.errors import KeyMissing, NotFound, ValidationError
from plsi.paths import REPO_ROOT, plsi_home

# Every variable in .env.example and what it unlocks (doctor / keys status).
UNLOCKS: dict[str, str] = {
    "PANDACLAW_MCP_URL": "PandaClaw MCP endpoint override",
    "PANDACLAW_BEARER_TOKEN": "plsi oracle pandaclaw",
    "PANDAOMICS_MCP_URL": "PandaOmics MCP endpoint override",
    "PANDAOMICS_BEARER_TOKEN": "plsi oracle pandaomics",
    "PLSI_LLLM_MODE": "L-LLM endpoint preset (local | server)",
    "PLSI_LLLM_BASE_URL": "plsi oracle l-llm (explicit endpoint)",
    "PLSI_LLLM_MODEL": "L-LLM model name",
    "PLSI_LLLM_API_KEY": "L-LLM endpoint auth",
    "HF_TOKEN": "L-LLM endpoint auth fallback (Hugging Face)",
    "PLSI_LLLM_ENABLE_THINKING": "L-LLM thinking mode",
    "LOINC_USERNAME": "optional fhir.loinc.org enrichment (unused by default)",
    "LOINC_PASSWORD": "optional fhir.loinc.org enrichment (unused by default)",
    "NCBI_API_KEY": "PubMed E-utilities at 10 req/s",
    "NCBI_EMAIL": "PubMed E-utilities contact (NCBI policy)",
    "OPENFDA_API_KEY": "openFDA 120,000 req/day",
    "OPEN_WEARABLES_API_URL": "Open Wearables server for wearables/import (default http://localhost:8000)",
    "OPEN_WEARABLES_API_KEY": "Open Wearables API key for wearables/import (MCP server config)",
    "GOOGLE_HEALTH_CLIENT_ID": "Google Health OAuth client for wearables/google-health and nutritionist/food-log",
    "GOOGLE_HEALTH_CLIENT_SECRET": "Google Health OAuth client secret (wearables/google-health, nutritionist/food-log)",
    "GOOGLE_HEALTH_REFRESH_TOKEN": "Google Health read-only access (expires in about 7 days while the OAuth app is in Testing)",
    "FATSECRET_CONSUMER_KEY": "FatSecret Platform OAuth 1.0 consumer key for nutritionist/food-log",
    "FATSECRET_CONSUMER_SECRET": "FatSecret Platform OAuth 1.0 shared secret for nutritionist/food-log",
    "FATSECRET_ACCESS_TOKEN": "FatSecret member diary access token (3-legged OAuth 1.0) for nutritionist/food-log",
    "FATSECRET_ACCESS_SECRET": "FatSecret member diary access token secret for nutritionist/food-log",
    "MOTHERSHIP_PROFESSIONAL_TOKEN": "plsi mothership whoami, release, findings, prereg, finding and professional send",
    "PLSI_HOME": "instance directory (default <repo>/instances)",
    "PLSI_DEBUG": "redacted tracebacks on stderr when 1",
    "PLSI_ENV_FILE": "alternative .env path",
}

_SECRET_NAME = re.compile(r"KEY|TOKEN|PASSWORD|USERNAME|SECRET|EMAIL")
_CANDIDATE = re.compile(_SECRET_NAME.pattern + r"|CLIENT|BEARER|_URL$")  # names worth showing in scan
_seen: set[str] = set()
_QUERY_SECRET = re.compile(r"(?i)([?&](?:api_key|key|token|password)=)[^&\s#\"']+")
_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")


def env_file() -> Path:
    return Path(os.environ.get("PLSI_ENV_FILE") or REPO_ROOT / ".env")


def _remember(name: str, value: str) -> None:
    # Only secret-like names are recorded so paths/URLs in messages stay readable.
    if _SECRET_NAME.search(name):
        hide(value)


def hide(value: str) -> None:
    """Mask a secret that does not come from the environment (e.g. a relay install token) in every redacted message."""
    if len(value) >= 6:
        _seen.add(value)


def load_env_file(path: Path | None = None) -> dict[str, str]:
    """Parse KEY=VALUE lines (optional `export `, quotes, # comments). Missing file -> {}."""
    path = path or env_file()
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.removeprefix("export ").partition("=")
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        if name:
            values[name] = value
            _remember(name, value)
    return values


def map_file() -> Path:
    return plsi_home() / "keys-map.json"


def aliases() -> dict[str, str]:
    """Known variable -> the name of the user's existing secret it is read from (names only)."""
    path = map_file()
    return files.load_json(path) if path.is_file() else {}


def _value(name: str, file_values: dict[str, str]) -> str | None:
    """Process env first, then .env; empty strings count as unset."""
    return os.environ.get(name) or file_values.get(name) or None


def get(name: str, default: str | None = None) -> str | None:
    """The variable itself, else the secret it is mapped to (`plsi keys map`)."""
    file_values = load_env_file()
    value = _value(name, file_values)
    if value is None and (source := aliases().get(name)):
        value = _value(source, file_values)
    if value is None:
        return default
    _remember(name, value)
    return value


def require(name: str) -> str:
    value = get(name)
    if value is None:
        raise KeyMissing(f"{name} is not set", hint=f"add {name} to {env_file().name} or the Grok secret store; see .env.example")
    return value


def status() -> dict[str, bool]:
    """Every known variable -> whether it is set, directly or through its mapped secret. Never returns values."""
    file_values, mapped = load_env_file(), aliases()
    return {name: bool(_value(name, file_values) or (name in mapped and _value(mapped[name], file_values)))
            for name in UNLOCKS}


def scan() -> dict[str, object]:
    """`keys scan`: names only. Known variables not set yet, the current mappings, and the names of other secrets
    present in the environment or .env, for the bot to judge which of them is which known variable."""
    file_values, found = load_env_file(), status()
    present = {n for n, v in {**file_values, **os.environ}.items() if v} - set(UNLOCKS)
    return {"unset": sorted(n for n, ok in found.items() if not ok), "mapped": aliases(),
            "candidates": sorted(n for n in present if _CANDIDATE.search(n.upper()))}


def map_key(name: str, source: str) -> dict[str, object]:
    """`keys map`: read the known variable `name` from the user's existing secret `source` (stores the two names)."""
    if name not in UNLOCKS:
        raise ValidationError(f"{name} is not a PLSI key variable", hint="plsi keys scan")
    if source in UNLOCKS or source == name:
        raise ValidationError(f"{source} is itself a PLSI key variable; set it directly", hint="plsi keys status")
    if _value(source, load_env_file()) is None:
        raise NotFound(f"{source} is not set in the environment or .env", code="KEY_NOT_FOUND", hint="plsi keys scan")
    files.atomic_write_json(map_file(), {**aliases(), name: source})
    return {"name": name, "from": source, "set": True}


def unmap_key(name: str) -> dict[str, object]:
    """`keys unmap`: forget a mapping (the user's secret itself is untouched)."""
    mapped = aliases()
    if mapped.pop(name, None) is None:
        raise NotFound(f"{name} is not mapped", code="KEY_NOT_FOUND", hint="plsi keys scan")
    files.atomic_write_json(map_file(), mapped)
    return {"name": name, "set": status()[name]}


def redact(text: str) -> str:
    """Mask every recorded secret value, secret query parameters and bearer tokens."""
    text = str(text)
    for name in UNLOCKS:
        _remember(name, os.environ.get(name, ""))
    try:
        file_values = load_env_file()
        for name, source in aliases().items():
            _remember(name, _value(source, file_values) or "")
    except (OSError, ValueError):
        pass
    for value in sorted(_seen, key=len, reverse=True):
        text = text.replace(value, "***")
    return _BEARER.sub(r"\1***", _QUERY_SECRET.sub(r"\1***", text))
