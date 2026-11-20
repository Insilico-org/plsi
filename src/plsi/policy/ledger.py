"""The verification ledger: check one ref against its source and record what resolved.

Ledger: <PLSI_HOME>/verifications.jsonl, one Verification per line. HTTP only via plsi.net; every
relayed string is ExternalText.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any, NamedTuple

from plsi import net, references
from plsi.clock import now
from plsi.errors import NetworkError, ValidationError, warn
from plsi.files import append_jsonl, read_jsonl
from plsi.map import registry
from plsi.models import ExternalText, SourceRef, sanitize_external
from plsi.paths import plsi_home
from plsi.policy import ctgov
from plsi.policy.models import Verification
from plsi.policy.records import ID_PATTERNS, _esummary, _retracted, _titled, cite_url, label_query
from plsi.vocab import ReferenceKind, SourceKind

LEDGER_MAX_AGE_DAYS = 30
CAP_TITLE = 500  # a ledger entry's title
CAP_AUTHORS = 200  # a ledger entry's author line
NAMED_AUTHORS = 3  # authors named before "et al."


def ledger_path() -> Path:
    return plsi_home() / "verifications.jsonl"


class Found(NamedTuple):
    """What one check learned: resolves, and the record's own title, authors, journal and year when it has them."""

    ok: bool
    title: str | None = None
    authors: str | None = None
    journal: str | None = None
    year: str | None = None


def _ext(text: str | None, cap: int, origin: str) -> ExternalText | None:
    return sanitize_external(text, cap, origin) if text else None


def _log(kind: SourceKind, ident: str, found: Found, url: str | None) -> Verification:
    v = Verification(kind=kind, id=ident, ok=found.ok, checked_at=now(), canonical_url=url,
                     title=_ext(found.title, CAP_TITLE, kind.value), authors=_ext(found.authors, CAP_AUTHORS, kind.value),
                     journal=_ext(found.journal, CAP_TITLE, kind.value), year=found.year or None)
    append_jsonl(ledger_path(), v.dump())
    return v


def _author_line(names: list[str]) -> str | None:
    """'A, B, C, et al.' from the record's own names, or None when it lists none."""
    names = [n for n in names if n]
    if not names:
        return None
    return ", ".join(names[:NAMED_AUTHORS]) + (", et al." if len(names) > NAMED_AUTHORS else "")


def _check_pmid(ident: str) -> Found:
    item = _esummary([ident]).get(ident) or {}
    authors = _author_line([str(a.get("name") or "") for a in item.get("authors") or [] if isinstance(a, dict)])
    found = Found(_titled(item), item.get("title"), authors, item.get("fulljournalname") or item.get("source"),
                  str(item.get("pubdate") or "")[:4] or None)
    return found._replace(ok=False, title=f"Retracted: {found.title}") if _retracted(item.get("pubtype") or []) else found


def _europepmc_doi(ident: str) -> dict[str, Any]:
    """Europe PMC's record of a DOI (journals and preprints), or {} when it has none or does not answer: the DOI
    still resolves, it just comes back without authors."""
    try:
        data = net.get_json(f"{references.api_base('europepmc')}/search",
                            {"query": f'DOI:"{ident}"', "format": "json", "pageSize": 1, "resultType": "lite"})
    except NetworkError:
        warn("NO_AUTHORS", f"doi {ident} resolves, but Europe PMC did not answer: no authors, journal or year")
        return {}
    hits = data.get("resultList", {}).get("result", [])
    return hits[0] if hits and str(hits[0].get("doi", "")).lower() == ident.lower() else {}


def _check_doi(ident: str) -> Found:
    data = net.get_json(f"{references.api_base('doi')}/{urllib.parse.quote(ident, safe='/')}", missing=(404,))
    if not (bool(data) and data.get("responseCode") == 1):
        return Found(False)
    item = _europepmc_doi(ident)
    authors = [a.strip() for a in str(item.get("authorString") or "").rstrip(".").split(",")]
    journal = item.get("journalTitle") or (item.get("bookOrReportDetails") or {}).get("publisher")
    return Found(True, item.get("title"), _author_line(authors), journal, item.get("pubYear"))


def _check_nct(ident: str) -> Found:
    data = ctgov.study(ident, "NCTId,BriefTitle")
    return Found(data is not None, (ctgov.record(data)["title"] or None) if data else None)


def _check_label(ident: str) -> Found:
    data = label_query(f'set_id:"{ident}"', 1)
    labels = data.get("results", [])
    brands = labels[0].get("openfda", {}).get("brand_name", []) if labels else []
    return Found(data.get("meta", {}).get("results", {}).get("total", 0) >= 1, "; ".join(brands) or None)


def _check_evipedia(ident: str) -> Found:
    text = net.get_text(f"{references.api_base('evipedia')}/{ident}.md", missing=(404,))
    heading = next((ln.lstrip("# ").strip() for ln in (text or "").splitlines() if ln.startswith("#")), None)
    return Found(text is not None, heading)


def _check_model(ident: str) -> Found:
    ref = references.load().get(ident)
    return Found(ref is not None and ref.kind in (ReferenceKind.MODEL, ReferenceKind.ORACLE), ref.title if ref else None)


def _check_rule(ident: str) -> Found:
    return Found(ident in registry.rule_ids())


# kind -> check(id) -> Found; each contacts only the fixed hosts for its kind (a DOI: the handle API, then Europe PMC).
CHECKS: dict[SourceKind, Callable[[str], Found]] = {
    SourceKind.PMID: _check_pmid,
    SourceKind.DOI: _check_doi,  # the handle API decides; it knows no retractions (search sees Europe PMC's)
    SourceKind.NCT: _check_nct,
    SourceKind.LABEL: _check_label,
    SourceKind.EVIPEDIA: _check_evipedia,
    SourceKind.MODEL: _check_model,
    SourceKind.RULE: _check_rule,
}


def verify(kind: str, id: str) -> dict[str, Any]:  # noqa: A002 - CLI dest name
    """`plsi evidence verify --kind K --id ID`: one ledger line; network failure raises. A negative is ok false,
    no canonical_url, and a NOT_VERIFIED warning (the envelope `ok` only says the check ran)."""
    k = SourceKind(kind)
    if k in ID_PATTERNS and not re.match(ID_PATTERNS[k], id):
        raise ValidationError(f"{kind} id {id!r} has the wrong format", code="BAD_ID", hint=f"must match {ID_PATTERNS[k]}")
    found = CHECKS[k](id)
    url = cite_url(k, id) or (references.load()[id].url if k == SourceKind.MODEL and found.ok else None)
    if not found.ok:
        warn("NOT_VERIFIED", f"{kind} {id} was looked up and does not resolve: not a citable source")
        url = None
    return _log(k, id, found, url).dump()


def latest_verification(kind: str, ident: str) -> Verification | None:
    """Newest ledger entry for (kind, ident), or None."""
    for raw in reversed(read_jsonl(ledger_path())):
        if isinstance(raw, dict) and raw.get("kind") == kind and raw.get("id") == ident:
            try:
                return Verification.model_validate(raw)
            except ValueError:
                continue
    return None


def is_verified(ref: SourceRef) -> bool:
    """True when the newest ledger entry for ref is ok and at most LEDGER_MAX_AGE_DAYS old (G5)."""
    v = latest_verification(ref.kind.value, ref.id)
    return v is not None and v.ok and now() - v.checked_at <= timedelta(days=LEDGER_MAX_AGE_DAYS)
