"""Live multi-source evidence search: run each source's fetcher and log every id it resolved.

Base URLs come from plsi.references; HTTP only via plsi.net; every relayed string is ExternalText.
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Callable
from typing import Any

from plsi import extensions, net, references
from plsi.errors import ValidationError
from plsi.models import CAP_ABSTRACT, SourceRef, parse, sanitize_external
from plsi.policy import ctgov
from plsi.policy.ledger import Found, _log
from plsi.policy.records import (ID_PATTERNS, Result, _esummary, _ncbi_params, _retracted, _titled, cite_url,
                                 label_query)
from plsi.vocab import SearchSource, SourceKind

MAX_RESULTS = 50


def _text(value: Any, origin: str) -> dict[str, Any]:
    return sanitize_external(str(value or ""), CAP_ABSTRACT, origin).model_dump(mode="json")


def _result(kind: SourceKind, ident: str, title: Any, origin: str, *, year: str | None = None,
            pub_types: Any = None, abstract: Any = None) -> Result:
    """One search hit, cited at its record's page; every relayed string is ExternalText."""
    url = cite_url(kind, ident)
    out = {"ref": SourceRef(kind=kind, id=ident, url=url).dump(), "title": _text(title, origin), "url": _text(url, origin)}
    if year:
        out["year"] = year
    if pub_types:
        out["pub_types"] = [_text(v, origin) for v in (pub_types if isinstance(pub_types, list) else [pub_types])]
    if abstract:
        out["abstract"] = _text(abstract, origin)
    return out


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
            out.append(_result(SourceKind.PMID, pmid, item["title"], "pubmed",
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
            out.append(_result(kind, id_, item.get("title"), "europepmc",
                               year=item.get("pubYear"), pub_types=types, abstract=item.get("abstractText")))
    return out


def _ctgov(query: str, limit: int) -> list[Result]:
    data = ctgov.studies({"query.term": query, "pageSize": limit, "fields": "NCTId,BriefTitle,OverallStatus,Phase,StartDate"})
    out = []
    for study in (ctgov.record(raw) for raw in data.get("studies", [])[:limit]):
        if re.match(ID_PATTERNS[SourceKind.NCT], nct := study["nct"]):
            out.append(_result(SourceKind.NCT, nct, study["title"], "ctgov",
                               year=(study["started"] or "")[:4], pub_types=[p for p in [*study["phases"], study["status"]] if p]))
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
            out.append(_result(SourceKind.LABEL, set_id, title, "openfda",
                               year=str(label.get("effective_time", ""))[:4], pub_types=names.get("product_type")))
    return out


def _evipedia(query: str, limit: int) -> list[Result]:
    data = net.get_json(f"{references.api_base('evipedia_mcp')}/search", {"q": query})
    out = []
    for item in data.get("results", [])[:limit]:
        slug = urllib.parse.urlsplit(item.get("url", "")).path.strip("/").removesuffix(".md")
        if re.match(ID_PATTERNS[SourceKind.EVIPEDIA], slug):
            out.append(_result(SourceKind.EVIPEDIA, slug, item.get("topic"), "evipedia"))
    return out


SOURCES: dict[SearchSource, Callable[[str, int], list[Result]]] = {
    SearchSource.PUBMED: _pubmed,
    SearchSource.EUROPEPMC: _europepmc,
    SearchSource.CTGOV: _ctgov,
    SearchSource.OPENFDA: _openfda,
    SearchSource.EVIPEDIA: _evipedia,
}


def _search_extension(source: str, query: str, limit: int) -> list[dict[str, Any]]:
    """Results from an evidence_source extension. Items with a kind+id become SourceRefs (verify them); others are leads.
    An item that is not an object, or names a kind and an id no SourceRef can hold, raises EXTENSION_INVALID."""
    results = []
    for item in extensions.evidence_source(source.removeprefix("ext:"))(query, limit)[:limit]:
        if not isinstance(item, dict):
            raise ValidationError(f"{source} returned a result that is not an object", code="EXTENSION_INVALID")
        kind, rid = item.get("kind"), item.get("id")
        ref = (parse(SourceRef, {"kind": kind, "id": str(rid)}, f"{source} ref", code="EXTENSION_INVALID").dump()
               if kind in {k.value for k in SourceKind} and rid else None)
        results.append({"ref": ref, "title": _text(item.get("title") or "", source), "url": _text(item.get("url"), source)})
    return results


def search(source: str, query: str, limit: int = 10) -> dict[str, Any]:
    """`plsi evidence search` (network). Logs a Verification for every id it resolved, not ok when retracted."""
    if not 1 <= limit <= MAX_RESULTS:
        raise ValidationError(f"limit must be between 1 and {MAX_RESULTS}")
    if source.startswith("ext:"):
        results, note = _search_extension(source, query, limit), "extension results are leads; run plsi evidence verify on each ref before citing"
    else:
        if source not in {s.value for s in SearchSource}:
            raise ValidationError(f"unknown source {source!r}", hint=f"one of {', '.join(SearchSource)} or ext:<extension id>")
        results, note = SOURCES[SearchSource(source)](query, limit), None
        for r in results:
            ok = not _retracted([t["text"] for t in r.get("pub_types", [])])
            _log(SourceKind(r["ref"]["kind"]), r["ref"]["id"], Found(ok, r["title"]["text"]), r["ref"].get("url"))
    out: dict[str, Any] = {"source": source, "query": query, "count": len(results), "results": results}
    if note:
        out["note"] = note
    return out
