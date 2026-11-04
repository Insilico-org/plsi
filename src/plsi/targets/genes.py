"""MyGene.info: which gene was meant, and what else it is called.

A second, independent resolver beside Open Targets: it matches symbols, names and aliases (`KLOTHO` is `KL`)
and hands back the aliases a literature or registry search needs.
"""

from __future__ import annotations

from typing import Any

from plsi import net, references
from plsi.models import external_str

CAP_SUMMARY = 2_000  # the NCBI gene summary is worth having whole
FIELDS = "symbol,name,alias,summary,entrezgene,uniprot.Swiss-Prot,HGNC,type_of_gene,genomic_pos,pharmgkb"
MAX_ALIASES = 12


def _listed(value: Any) -> list[str]:
    """A field MyGene returns as a bare string or a list, as a list."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [external_str(item) for item in items if item]


def _first(value: Any) -> str | None:
    items = _listed(value)
    return items[0] if items else None


def _hit(hit: dict[str, Any], asked: str) -> dict[str, Any]:
    symbol = external_str(hit.get("symbol"))
    aliases = _listed(hit.get("alias"))[:MAX_ALIASES]
    matched = asked.strip().lower()
    return {
        "symbol": symbol, "name": external_str(hit.get("name")),
        "aliases": aliases,
        "entrez": str(hit.get("entrezgene") or "") or None,
        "uniprot": _first((hit.get("uniprot") or {}).get("Swiss-Prot")),
        "hgnc": str(hit.get("HGNC") or "") or None,
        "kind": external_str(hit.get("type_of_gene")) or None,
        "summary": external_str(hit.get("summary"), CAP_SUMMARY) or None,
        # `alias` means the name asked for is not the symbol, so searches should cover both.
        "matched": ("symbol" if symbol.lower() == matched
                    else "alias" if any(a.lower() == matched for a in aliases)
                    else "name"),
    }


def resolve(query: str) -> dict[str, Any]:
    """A symbol, alias, name or Ensembl id -> the canonical gene, or `{found: false}`. Advisory: a
    disagreement with Open Targets is reported, never reconciled."""
    hits = _query(f"symbol:{query.strip()}") or _query(query.strip())
    if not hits:
        return {"found": False, "asked": external_str(query),
                "note": f"MyGene.info has no human gene matching {query!r}"}
    return {"found": True, "asked": external_str(query), **_hit(hits[0], query),
            "other_matches": [external_str(h.get("symbol")) for h in hits[1:4] if h.get("symbol")]}


def _query(term: str) -> list[dict[str, Any]]:
    data = net.get_json(f"{references.api_base('mygene')}/query",
                        {"q": term, "species": "human", "fields": FIELDS, "size": 5})
    return [h for h in (data or {}).get("hits", []) if h.get("symbol")]
