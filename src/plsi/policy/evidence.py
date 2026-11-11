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

from plsi import extensions, keys, net, references
from plsi.clock import now
from plsi.errors import NetworkError, ValidationError, warn
from plsi.files import append_jsonl, read_jsonl
from plsi.map import registry
from plsi.models import CAP_ABSTRACT, SourceRef, parse, sanitize_external
from plsi.paths import plsi_home
from plsi.policy import ctgov
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
RETRACTED = "retracted publication"  # a PubMed or Europe PMC publication type, lower-cased
CAP_TITLE = 500  # a ledger entry's title
MAX_RESULTS = 50


def ledger_path() -> Path:
    return plsi_home() / "verifications.jsonl"


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


def _retracted(pub_types: list[Any]) -> bool:
    return RETRACTED in (str(t).lower() for t in pub_types)


def cite_url(kind: SourceKind, ident: str) -> str | None:
    """The citable page of one record (None for model and rule sources)."""
    return references.get(CITED_AT[kind]).cite_url.format(id=ident) if kind in CITED_AT else None


def _ncbi_params(**params: Any) -> dict[str, Any]:
    return {**params, "tool": "plsi", "email": keys.get("NCBI_EMAIL"), "api_key": keys.get("NCBI_API_KEY")}


def _esummary(ids: list[str]) -> dict[str, Any]:
    """PubMed esummary: {pmid: summary}. An invalid PMID still answers, with an `error` and no title."""
    base = references.api_base("ncbi_eutils")
    return net.get_json(f"{base}/esummary.fcgi", _ncbi_params(db="pubmed", id=",".join(ids), retmode="json")).get("result", {})


def _titled(item: dict[str, Any]) -> bool:
    return bool(item.get("title")) and not item.get("error")


def label_query(search: str, limit: int, **params: Any) -> dict[str, Any]:
    """openFDA drug label search; zero hits (openFDA answers 404 NOT_FOUND) are an empty result."""
    try:
        return net.get_json(f"{references.api_base('openfda_label')}/drug/label.json",
                            {"search": search, "limit": limit, **params, "api_key": keys.get("OPENFDA_API_KEY")})
    except NetworkError as exc:
        if exc.status == 404 and "NOT_FOUND" in exc.body:
            return {"meta": {"results": {"total": 0}}, "results": []}
        raise


def label_title(label: dict[str, Any]) -> str | None:
    """Brand names of an openFDA label, else its generic names."""
    names = label.get("openfda", {})
    return "; ".join(names.get("brand_name") or names.get("generic_name") or []) or None


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
            _log(SourceKind(r["ref"]["kind"]), r["ref"]["id"], ok, r["title"]["text"], r["ref"].get("url"))
    out: dict[str, Any] = {"source": source, "query": query, "count": len(results), "results": results}
    if note:
        out["note"] = note
    return out


def _log(kind: SourceKind, ident: str, ok: bool, title: str | None, url: str | None) -> Verification:
    v = Verification(kind=kind, id=ident, ok=ok, checked_at=now(), canonical_url=url,
                     title=sanitize_external(title, CAP_TITLE, kind.value) if title else None)
    append_jsonl(ledger_path(), v.dump())
    return v


def _check_pmid(ident: str) -> tuple[bool, str | None]:
    item = _esummary([ident]).get(ident) or {}
    if _retracted(item.get("pubtype") or []):
        return False, f"Retracted: {item.get('title')}"
    return _titled(item), item.get("title")


def _check_doi(ident: str) -> tuple[bool, str | None]:
    data = net.get_json(f"{references.api_base('doi')}/{urllib.parse.quote(ident, safe='/')}", missing=(404,))
    return bool(data) and data.get("responseCode") == 1, None


def _check_nct(ident: str) -> tuple[bool, str | None]:
    data = ctgov.study(ident, "NCTId,BriefTitle")
    return data is not None, (ctgov.record(data)["title"] or None) if data else None


def _check_label(ident: str) -> tuple[bool, str | None]:
    data = label_query(f'set_id:"{ident}"', 1)
    labels = data.get("results", [])
    brands = labels[0].get("openfda", {}).get("brand_name", []) if labels else []
    return data.get("meta", {}).get("results", {}).get("total", 0) >= 1, "; ".join(brands) or None


def _check_evipedia(ident: str) -> tuple[bool, str | None]:
    text = net.get_text(f"{references.api_base('evipedia')}/{ident}.md", missing=(404,))
    heading = next((ln.lstrip("# ").strip() for ln in (text or "").splitlines() if ln.startswith("#")), None)
    return text is not None, heading


def _check_model(ident: str) -> tuple[bool, str | None]:
    ref = references.load().get(ident)
    return ref is not None and ref.kind in (ReferenceKind.MODEL, ReferenceKind.ORACLE), ref.title if ref else None


def _check_rule(ident: str) -> tuple[bool, str | None]:
    return ident in registry.rule_ids(), None


# kind -> check(id) -> (resolves, title); each contacts only the fixed host for its kind.
CHECKS: dict[SourceKind, Callable[[str], tuple[bool, str | None]]] = {
    SourceKind.PMID: _check_pmid,
    SourceKind.DOI: _check_doi,  # resolves only: the DOI handle API knows no retractions (search sees Europe PMC's)
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
    ok, title = CHECKS[k](id)
    url = cite_url(k, id) or (references.load()[id].url if k == SourceKind.MODEL and ok else None)
    if not ok:
        warn("NOT_VERIFIED", f"{kind} {id} was looked up and does not resolve: not a citable source")
        url = None
    return _log(k, id, ok, title, url).dump()


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
