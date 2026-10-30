"""Live evidence search and the verification ledger.

Base URLs come from plsi.references; HTTP only via plsi.net; every relayed string is ExternalText.
Ledger: <PLSI_HOME>/verifications.jsonl, one Verification per line.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

from plsi import keys, net, references
from plsi.clock import now
from plsi.errors import NetworkError, ValidationError
from plsi.files import append_jsonl, read_jsonl
from plsi.map import registry
from plsi.models import CAP_ABSTRACT, SourceRef, sanitize_external
from plsi.paths import plsi_home
from plsi.policy.models import Verification
from plsi.vocab import ReferenceKind, SearchSource, SourceKind

LEDGER_MAX_AGE_DAYS = 30
ID_PATTERNS = {
    SourceKind.PMID: r"^\d{1,9}$",
    SourceKind.DOI: r"^10\.\d{4,9}/\S+$",
    SourceKind.NCT: r"^NCT\d{8}$",
    SourceKind.LABEL: r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    SourceKind.EVIPEDIA: r"^[a-z0-9][a-z0-9_-]{0,127}$",
}
CITED_AT = {  # source kind -> the reference whose cite_url is the record's citable page
    SourceKind.PMID: "ncbi_eutils",
    SourceKind.DOI: "doi",
    SourceKind.NCT: "ctgov",
    SourceKind.LABEL: "dailymed",
    SourceKind.EVIPEDIA: "evipedia",
}
Result = dict[str, Any]


def ledger_path() -> Path:
    return plsi_home() / "verifications.jsonl"


def _text(value: Any, origin: str) -> dict[str, Any]:
    return sanitize_external(str(value or ""), CAP_ABSTRACT, origin).model_dump(mode="json")


def _result(kind: SourceKind, id: str, title: Any, url: str, origin: str, **extra: Any) -> Result:  # noqa: A002
    ref = SourceRef(kind=kind, id=id, url=url)
    out = {"ref": ref.dump(), "title": _text(title, origin), "url": _text(url, origin)}
    for key, value in extra.items():
        if value:
            out[key] = (_text(value, origin) if key == "abstract"
                        else [_text(v, origin) for v in (value if isinstance(value, list) else [value])] if key == "pub_types"
                        else value)
    return out


def cite_url(kind: SourceKind, id: str) -> str | None:  # noqa: A002
    """The citable page of one record (None for model and rule sources)."""
    return references.get(CITED_AT[kind]).cite_url.format(id=id) if kind in CITED_AT else None


def _ncbi_params(**params: Any) -> dict[str, Any]:
    return {**params, "tool": "plsi", "email": keys.get("NCBI_EMAIL"), "api_key": keys.get("NCBI_API_KEY")}


def _esummary(ids: list[str]) -> dict[str, Any]:
    """PubMed esummary: {pmid: summary}. An invalid PMID still answers, with an `error` and no title."""
    base = references.api_base("ncbi_eutils")
    return net.get_json(f"{base}/esummary.fcgi", _ncbi_params(db="pubmed", id=",".join(ids), retmode="json")).get("result", {})


def _titled(item: dict[str, Any]) -> bool:
    return bool(item.get("title")) and not item.get("error")


def label_query(search: str, limit: int, **params: Any) -> dict[str, Any]:
    """openFDA drug label search (zero hits answer as an empty result)."""
    return net.get_json(f"{references.api_base('openfda_label')}/drug/label.json",
                        {"search": search, "limit": limit, **params, "api_key": keys.get("OPENFDA_API_KEY")})


def label_title(label: dict[str, Any]) -> str | None:
    """Brand names of an openFDA label, else its generic names."""
    names = label.get("openfda", {})
    return "; ".join(names.get("brand_name") or names.get("generic_name") or []) or None


# ---------------------------------------------------------------- search, one function per source

def _pubmed(query: str, limit: int) -> list[Result]:
    base = references.api_base("ncbi_eutils")
    found = net.get_json(f"{base}/esearch.fcgi", _ncbi_params(db="pubmed", term=query, retmode="json", retmax=limit, sort="relevance"))
    ids = found.get("esearchresult", {}).get("idlist", [])[:limit]
    if not ids:
        return []
    summary = _esummary(ids)
    out = []
    for pmid in ids:
        item = summary.get(pmid) or {}
        if _titled(item):
            out.append(_result(SourceKind.PMID, pmid, item["title"], cite_url(SourceKind.PMID, pmid), "pubmed",
                               year=str(item.get("pubdate", ""))[:4], pub_types=item.get("pubtype")))
    return out


def _europepmc(query: str, limit: int) -> list[Result]:
    data = net.get_json(f"{references.api_base('europepmc')}/search",
                        {"query": query, "format": "json", "pageSize": limit, "resultType": "core"})
    out = []
    for item in data.get("resultList", {}).get("result", [])[:limit]:
        # records without a PMID or DOI (e.g. PMC-only) cannot be cited as a SourceRef and are skipped
        kind, id_ = (SourceKind.PMID, item.get("pmid")) if item.get("pmid") else (SourceKind.DOI, item.get("doi"))
        if id_ and re.match(ID_PATTERNS[kind], id_):
            types = item.get("pubTypeList", {}).get("pubType") or None
            out.append(_result(kind, id_, item.get("title"), cite_url(kind, id_), "europepmc",
                               year=item.get("pubYear"), pub_types=types, abstract=item.get("abstractText")))
    return out


def _ctgov(query: str, limit: int) -> list[Result]:
    data = net.get_json(f"{references.api_base('ctgov')}/studies",
                        {"query.term": query, "pageSize": limit, "fields": "NCTId,BriefTitle,OverallStatus,Phase,StartDate"})
    out = []
    for study in data.get("studies", [])[:limit]:
        sec = study.get("protocolSection", {})
        nct = sec.get("identificationModule", {}).get("nctId", "")
        if re.match(ID_PATTERNS[SourceKind.NCT], nct):
            status = sec.get("statusModule", {})
            out.append(_result(SourceKind.NCT, nct, sec["identificationModule"].get("briefTitle"), cite_url(SourceKind.NCT, nct),
                               "ctgov", year=status.get("startDateStruct", {}).get("date", "")[:4],
                               pub_types=[p for p in [*sec.get("designModule", {}).get("phases", []), status.get("overallStatus")] if p]))
    return out


def _openfda(query: str, limit: int) -> list[Result]:
    q = query.replace('"', "")
    search = " ".join(f'openfda.{f}:"{q}"' for f in ("generic_name", "brand_name", "substance_name"))
    out = []
    for label in label_query(search, limit).get("results", [])[:limit]:
        set_id = label.get("set_id", "")
        names = label.get("openfda", {})
        if re.match(ID_PATTERNS[SourceKind.LABEL], set_id):
            title = "; ".join(names.get("brand_name", []) + names.get("generic_name", [])) or set_id
            out.append(_result(SourceKind.LABEL, set_id, title, cite_url(SourceKind.LABEL, set_id), "openfda",
                               year=str(label.get("effective_time", ""))[:4], pub_types=names.get("product_type")))
    return out


def _evipedia(query: str, limit: int) -> list[Result]:
    data = net.get_json(f"{references.api_base('evipedia_mcp')}/search", {"q": query})
    out = []
    for item in data.get("results", [])[:limit]:
        slug = urllib.parse.urlsplit(item.get("url", "")).path.strip("/").removesuffix(".md")
        if re.match(ID_PATTERNS[SourceKind.EVIPEDIA], slug):
            out.append(_result(SourceKind.EVIPEDIA, slug, item.get("topic"), cite_url(SourceKind.EVIPEDIA, slug), "evipedia"))
    return out


SOURCES: dict[SearchSource, Callable[[str, int], list[Result]]] = {
    SearchSource.PUBMED: _pubmed,
    SearchSource.EUROPEPMC: _europepmc,
    SearchSource.CTGOV: _ctgov,
    SearchSource.OPENFDA: _openfda,
    SearchSource.EVIPEDIA: _evipedia,
}


def _search_extension(source: str, query: str, limit: int) -> list[dict[str, Any]]:
    """Results from an evidence_source extension. Items with a kind+id become SourceRefs (verify them); others are leads."""
    from plsi import extensions

    ext_id = source.removeprefix("ext:")
    results = []
    for item in extensions.evidence_source(ext_id)(query, limit)[:limit]:
        kind, rid = item.get("kind"), item.get("id")
        ref = SourceRef(kind=kind, id=str(rid)).dump() if kind in {k.value for k in SourceKind} and rid else None
        results.append({"ref": ref, "title": _text(item.get("title") or "", source), "url": _text(item.get("url"), source)})
    return results


def search(source: str, query: str, limit: int = 10) -> dict[str, Any]:
    """`plsi evidence search` (network). Logs an ok Verification for every id it resolved."""
    if source.startswith("ext:"):
        results, note = _search_extension(source, query, limit), "extension results are leads; run plsi evidence verify on each ref before citing"
    else:
        if source not in {s.value for s in SearchSource}:
            raise ValidationError(f"unknown source {source!r}", hint=f"one of {', '.join(SearchSource)} or ext:<extension id>")
        if not 1 <= limit <= 50:
            raise ValidationError("limit must be between 1 and 50")
        results, note = SOURCES[SearchSource(source)](query, limit), None
        for r in results:
            _log(SourceKind(r["ref"]["kind"]), r["ref"]["id"], True, r["title"]["text"], r["ref"].get("url"))
    out: dict[str, Any] = {"source": source, "query": query, "count": len(results), "results": results}
    if note:
        out["note"] = note
    return out


# ---------------------------------------------------------------- verification ledger

def _log(kind: SourceKind, id: str, ok: bool, title: str | None, url: str | None) -> Verification:  # noqa: A002
    v = Verification(kind=kind, id=id, ok=ok, checked_at=now(), canonical_url=url,
                     title=sanitize_external(title, 500, kind.value) if title else None)
    append_jsonl(ledger_path(), v.dump())
    return v


def _not_found(fetch: Callable[[], Any]) -> Any:
    """Run fetch; a definitive HTTP 404 means 'does not resolve' (None). Other failures raise."""
    try:
        return fetch()
    except NetworkError as exc:
        if exc.status == 404:
            return None
        raise


def _check_pmid(id: str) -> tuple[bool, str | None]:  # noqa: A002
    item = _esummary([id]).get(id) or {}
    return _titled(item), item.get("title")


def _check_doi(id: str) -> tuple[bool, str | None]:  # noqa: A002
    data = _not_found(lambda: net.get_json(f"{references.api_base('doi')}/{urllib.parse.quote(id, safe='/')}"))
    return bool(data) and data.get("responseCode") == 1, None


def _check_nct(id: str) -> tuple[bool, str | None]:  # noqa: A002
    data = _not_found(lambda: net.get_json(f"{references.api_base('ctgov')}/studies/{id}", {"fields": "NCTId,BriefTitle"}))
    return data is not None, (data or {}).get("protocolSection", {}).get("identificationModule", {}).get("briefTitle")


def _check_label(id: str) -> tuple[bool, str | None]:  # noqa: A002
    data = label_query(f'set_id:"{id}"', 1)
    labels = data.get("results", [])
    return data.get("meta", {}).get("results", {}).get("total", 0) >= 1, ("; ".join(labels[0].get("openfda", {}).get("brand_name", [])) or None) if labels else None


def _check_evipedia(id: str) -> tuple[bool, str | None]:  # noqa: A002
    text = _not_found(lambda: net.get_text(f"{references.api_base('evipedia')}/{id}.md"))
    heading = next((ln.lstrip("# ").strip() for ln in (text or "").splitlines() if ln.startswith("#")), None)
    return text is not None, heading


def _check_model(id: str) -> tuple[bool, str | None]:  # noqa: A002
    ref = references.load().get(id)
    return ref is not None and ref.kind in (ReferenceKind.MODEL, ReferenceKind.ORACLE), ref.title if ref else None


def _check_rule(id: str) -> tuple[bool, str | None]:  # noqa: A002
    return id in registry.rule_ids(), None


# kind -> check(id) -> (resolves, title); each contacts only the fixed host for its kind.
CHECKS: dict[SourceKind, Callable[[str], tuple[bool, str | None]]] = {
    SourceKind.PMID: _check_pmid,
    SourceKind.DOI: _check_doi,
    SourceKind.NCT: _check_nct,
    SourceKind.LABEL: _check_label,
    SourceKind.EVIPEDIA: _check_evipedia,
    SourceKind.MODEL: _check_model,
    SourceKind.RULE: _check_rule,
}


def verify(kind: str, id: str) -> dict[str, Any]:  # noqa: A002 - CLI dest name
    """`plsi evidence verify --kind K --id ID`: one ledger line. Definitive negative -> ok false; network failure raises."""
    k = SourceKind(kind)
    if k in ID_PATTERNS and not re.match(ID_PATTERNS[k], id):
        raise ValidationError(f"{kind} id {id!r} has the wrong format", code="BAD_ID", hint=f"must match {ID_PATTERNS[k]}")
    ok, title = CHECKS[k](id)
    url = cite_url(k, id) or (references.load()[id].url if k == SourceKind.MODEL and ok else None)
    return _log(k, id, ok, title, url).dump()


def latest_verification(kind: str, id: str) -> Verification | None:  # noqa: A002
    """Newest ledger entry for (kind, id), or None."""
    for raw in reversed(read_jsonl(ledger_path())):
        if isinstance(raw, dict) and raw.get("kind") == kind and raw.get("id") == id:
            try:
                return Verification.model_validate(raw)
            except ValueError:
                continue
    return None


def is_verified(ref: SourceRef) -> bool:
    """True when the newest ledger entry for ref is ok and at most LEDGER_MAX_AGE_DAYS old (G5)."""
    v = latest_verification(ref.kind.value, ref.id)
    return v is not None and v.ok and now() - v.checked_at <= timedelta(days=LEDGER_MAX_AGE_DAYS)
