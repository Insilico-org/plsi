"""`<PLSI_HOME>/targets/<gene>/dossier.json`: one folder per target, beside the research topics.

On disk: the gathered facts, the gather date, and once a bot has written one, its assessment and assessment
date. Nothing computed is stored; `rank.summary` runs on every read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files
from plsi.clock import now
from plsi.errors import NotFound, ValidationError
from plsi.paths import plsi_home, safe_join, validate_id

DOSSIER = "dossier.json"


def targets_dir() -> Path:
    return plsi_home() / "targets"


def folder(symbol: str) -> str:
    """A gene symbol as a folder name: lower case, and refused rather than mangled when it is not a symbol."""
    name = str(symbol or "").strip().lower()
    try:
        return validate_id(name, "gene symbol")
    except ValidationError:
        raise ValidationError(f"{symbol!r} is not a usable gene symbol", code="BAD_SYMBOL",
                              hint="use the HGNC symbol (letters, digits, - and _), e.g. SIRT6 or HLA-A") from None


def dir_of(symbol: str, *, must_exist: bool = False) -> Path:
    path = safe_join(targets_dir(), folder(symbol))
    if must_exist and not (path / DOSSIER).is_file():
        raise NotFound(f"no dossier for {symbol}", code="DOSSIER_NOT_FOUND",
                       hint=f"plsi targets dossier --gene {symbol}")
    return path


def save(symbol: str, facts: dict[str, Any], assessment: dict[str, Any] | None = None) -> Path:
    """Write the dossier whole. A stored assessment survives a re-gather unless one is passed, and
    `gathered` changes only when the facts do."""
    path = dir_of(symbol)
    stored = load(symbol) if (path / DOSSIER).is_file() else {}
    kept = assessment if assessment is not None else stored.get("assessment")
    unchanged = stored.get("facts") == facts and stored.get("gathered")
    document = {"gene": facts.get("symbol") or symbol,
                "gathered": stored["gathered"] if unchanged else now().isoformat(),
                "facts": facts}
    if kept:
        document["assessment"] = kept
        document["assessed"] = now().isoformat() if assessment is not None else stored.get("assessed")
    files.atomic_write_json(path / DOSSIER, document)
    return path / DOSSIER


def load(symbol: str) -> dict[str, Any]:
    document = files.load_json(dir_of(symbol, must_exist=True) / DOSSIER)
    if not isinstance(document, dict):
        raise ValidationError(f"{DOSSIER} for {symbol} is not a JSON object")
    return document


def list_dossiers() -> dict[str, Any]:
    """`plsi targets list`: every stored dossier, newest first, with whether a bot has assessed it."""
    rows = []
    for path in sorted(targets_dir().glob(f"*/{DOSSIER}")):
        document = files.load_json(path)
        if not isinstance(document, dict):
            continue
        facts = document.get("facts") or {}
        assessment = document.get("assessment") or {}
        rows.append({
            "gene": document.get("gene"), "gathered": document.get("gathered"),
            "assessed_at": document.get("assessed"),
            "indication": (facts.get("indication") or {}).get("name"),
            "assessed": bool(assessment), "verdict": assessment.get("verdict"),
            "path": str(path),
        })
    rows.sort(key=lambda r: str(r.get("gathered") or ""), reverse=True)
    return {"count": len(rows), "targets": rows, "store": str(targets_dir())}
