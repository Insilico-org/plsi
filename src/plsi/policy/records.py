"""A single source record: its id format, its citable page, and reading it off NCBI or openFDA.

Base URLs come from plsi.references; HTTP only via plsi.net. Shared by the live search and the ledger.
"""

from __future__ import annotations

from typing import Any

from plsi import keys, net, references
from plsi.errors import NetworkError
from plsi.vocab import SourceKind

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


def cite_url(kind: SourceKind, ident: str) -> str | None:
    """The citable page of one record (None for model and rule sources)."""
    return references.get(CITED_AT[kind]).cite_url.format(id=ident) if kind in CITED_AT else None


def _retracted(pub_types: list[Any]) -> bool:
    return RETRACTED in (str(t).lower() for t in pub_types)


def _titled(item: dict[str, Any]) -> bool:
    return bool(item.get("title")) and not item.get("error")


def _ncbi_params(**params: Any) -> dict[str, Any]:
    return {**params, "tool": "plsi", "email": keys.get("NCBI_EMAIL"), "api_key": keys.get("NCBI_API_KEY")}


def _esummary(ids: list[str]) -> dict[str, Any]:
    """PubMed esummary: {pmid: summary}. An invalid PMID still answers, with an `error` and no title."""
    base = references.api_base("ncbi_eutils")
    return net.get_json(f"{base}/esummary.fcgi", _ncbi_params(db="pubmed", id=",".join(ids), retmode="json")).get("result", {})


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
