"""The Open Targets Platform client: the GraphQL exchange, name resolution and the target-disease associations.

No key. Every relayed string goes through `models.external_str`, and the exchange is `net.graphql`, so a reply
carrying `errors` is a failure even at HTTP 200. Drugs live in `plsi.targets.drugs`, the protein in
`plsi.targets.biology`.
"""

from __future__ import annotations

import re
from typing import Any

from plsi import net, references
from plsi.errors import NetworkError, NotFound, warn
from plsi.models import TRUNCATED, external_str
from plsi.vocab.targets import TargetModality

MODALITY_CODES = {"SM": TargetModality.SMALL_MOLECULE, "AB": TargetModality.ANTIBODY,
                  "PR": TargetModality.PROTAC, "OC": TargetModality.OTHER}

# Open Targets association datatypes. An id outside this list warns (`UNKNOWN_DATATYPE`) and never decides a
# band, so an upstream rename shows up instead of emptying a band.
TARGET_DATATYPES = ("genetic_association", "genetic_literature", "somatic_mutation", "clinical",
                    "affected_pathway", "rna_expression", "literature", "animal_model")
# The datatypes that bear on causation. `genetic_literature` is text-mined, not a curated association, so it
# is not among them.
CAUSAL_DATATYPES = frozenset({"genetic_association", "somatic_mutation", "animal_model"})
# The direction-of-effect pairs (directionOnTrait, directionOnTarget), in words. A pair outside these four is
# counted as unrecognised.
DIRECTION_MEANING: dict[tuple[str, str], str] = {
    ("protect", "LoF"): "loss of function is assessed as protective",
    ("risk", "GoF"): "gain of function is assessed as increasing risk",
    ("protect", "GoF"): "gain of function is assessed as protective",
    ("risk", "LoF"): "loss of function is assessed as increasing risk",
}

CAP_PROSE = 1_000  # a description: a disease definition, a protein's function, a drug warning

# UniProt's inline provenance markup: `(PubMed:123, PubMed:456)` and `(By similarity)`.
EVIDENCE_TAGS = re.compile(r"\s*\((?:(?:PubMed:\d+(?:,\s*)?)+|By similarity)\)", re.IGNORECASE)

SEARCH = """query Find($q: String!, $kind: [String!]!, $n: Int!) {
  search(queryString: $q, entityNames: $kind, page: {index: 0, size: $n}) {
    hits { id name entity description }
  }
}"""

# A disease's exact synonyms, for searching registries that file it under another name.
DISEASE_NAMES = """query DiseaseNames($efo: String!) {
  disease(efoId: $efo) { synonyms { relation terms } }
}"""
EXACT_SYNONYM = "hasExactSynonym"
MAX_DISEASE_NAMES = 10

ASSOCIATED = """query Assoc($efo: String!, $n: Int!) {
  disease(efoId: $efo) {
    id name
    associatedTargets(page: {index: 0, size: $n}) {
      count
      rows {
        score
        datatypeScores { id score }
        target {
          id approvedSymbol approvedName isEssential
          targetClass { label }
          tractability { label modality value }
        }
      }
    }
  }
}"""

ONE_ASSOCIATION = """query One($id: String!, $ids: [String!]) {
  target(ensemblId: $id) {
    associatedDiseases(Bs: $ids) {
      count
      rows { score datatypeScores { id score } disease { id name } }
    }
  }
}"""

def prose(value: Any) -> str:
    """A long description with UniProt's inline `(PubMed:...)` evidence tags removed (markup, not citations),
    cut at the last sentence that fits CAP_PROSE."""
    clean = EVIDENCE_TAGS.sub("", str(value or "")).strip()
    if len(clean) > CAP_PROSE:
        head = clean[:CAP_PROSE - len(TRUNCATED)]
        clean = (head[:head.rindex(". ") + 1] if ". " in head else head.rsplit(" ", 1)[0]) + TRUNCATED
    return external_str(clean, CAP_PROSE)


def query(document: str, variables: dict[str, Any]) -> dict[str, Any]:
    """One Open Targets GraphQL exchange (`net.graphql`)."""
    return net.graphql(references.api_base("open_targets"), document, variables)


def _hits(term: str, kind: str, limit: int) -> list[dict[str, Any]]:
    found = query(SEARCH, {"q": term, "kind": [kind], "n": limit}).get("search") or {}
    return [h for h in (found.get("hits") or []) if h.get("entity") == kind]


def find_disease(name: str) -> dict[str, Any]:
    """A disease name -> {id, name, description, ...}. Other hits are `also_matched` when the name was
    ambiguous, or `near_terms` when the top hit is the name asked for."""
    hits = _hits(name, "disease", 5)
    if not hits:
        raise NotFound(f"Open Targets has no disease matching {name!r}", code="DISEASE_NOT_FOUND",
                       hint="try the full clinical name, or an EFO/MONDO id")
    top, rest = hits[0], hits[1:]
    exact = external_str(top.get("name")).strip().lower() == str(name or "").strip().lower()
    others = [{"id": h["id"], "name": external_str(h.get("name"))} for h in rest]
    return {"id": top["id"], "name": external_str(top.get("name")),
            "description": external_str(top.get("description"), CAP_PROSE),
            "exact": exact,
            "also_known_as": disease_names(top["id"]),
            "also_matched": [] if exact else others,
            "near_terms": others if exact else [],
            "ambiguous": bool(others) and not exact}


def disease_names(efo_id: str) -> list[str]:
    """A disease's exact synonyms (only `hasExactSynonym`; broader relations name other diseases). Never
    raises: it is extra on top of a resolution that already succeeded, so a failure warns and answers []."""
    try:
        found = query(DISEASE_NAMES, {"efo": efo_id}).get("disease") or {}
    except (NetworkError, NotFound) as exc:
        warn("SOURCE_UNREADABLE", f"Open Targets' synonyms for {efo_id} could not be read ({exc.code}); "
                                  "`also_known_as` is empty on this run, which is not an absence of synonyms")
        return []
    for entry in found.get("synonyms") or []:
        if external_str(entry.get("relation")) == EXACT_SYNONYM:
            return sorted({external_str(term) for term in entry.get("terms") or [] if term})[:MAX_DISEASE_NAMES]
    return []


def find_target(symbol: str) -> dict[str, Any]:
    """A gene symbol or an Ensembl gene id -> {id, symbol, name, exact}. An exact match wins over the search
    ranking; `exact: false` is what the caller warns on."""
    hits = _hits(symbol, "target", 5)
    if not hits:
        raise NotFound(f"Open Targets has no target matching {symbol!r}", code="TARGET_NOT_FOUND",
                       hint="use the HGNC symbol (CACNG8, not TARP gamma-8) or an Ensembl gene id")
    asked = symbol.strip().lower()
    exact = [h for h in hits if asked in (str(h.get("name") or "").lower(), str(h.get("id") or "").lower())]
    top = (exact or hits)[0]
    return {"id": top["id"], "symbol": external_str(top.get("name")), "name": external_str(top.get("description")),
            "exact": bool(exact)}


def scores(row: dict[str, Any]) -> dict[str, float]:
    """The per-datatype breakdown. An id outside `TARGET_DATATYPES` is kept and warned about."""
    out = {}
    for item in row.get("datatypeScores") or []:
        key = external_str(item.get("id"))
        if not key:
            continue
        if key not in TARGET_DATATYPES:
            warn("UNKNOWN_DATATYPE", f"Open Targets returned the datatype {key!r}, which this version does not "
                                     "know; it is shown but does not decide a band")
        out[key] = round(float(item.get("score") or 0.0), 4)
    return out


def tractability(items: list[dict[str, Any]] | None) -> dict[str, list[str]]:
    """The true buckets, grouped by modality: {"small-molecule": ["Structure with Ligand", ...]}."""
    out: dict[str, list[str]] = {}
    for item in items or []:
        if item.get("value") is True:
            modality = MODALITY_CODES.get(str(item.get("modality") or ""))
            if modality:
                out.setdefault(modality.value, []).append(external_str(item.get("label")))
    return out


def associated_targets(efo_id: str, limit: int) -> dict[str, Any]:
    """Targets the evidence associates with a disease, ranked by Open Targets' own score (never ours)."""
    disease = query(ASSOCIATED, {"efo": efo_id, "n": limit}).get("disease")
    if not disease:
        raise NotFound(f"Open Targets has no disease {efo_id!r}", code="DISEASE_NOT_FOUND")
    assoc = disease.get("associatedTargets") or {}
    rows = []
    for row in assoc.get("rows") or []:
        target = row.get("target") or {}
        rows.append({
            "ensembl_id": target.get("id"), "symbol": external_str(target.get("approvedSymbol")),
            "name": external_str(target.get("approvedName")),
            "classes": [external_str(c.get("label")) for c in target.get("targetClass") or []][:4],
            "association": round(float(row.get("score") or 0.0), 4),
            "datatypes": scores(row),
            "tractability": tractability(target.get("tractability")),
            "essential": target.get("isEssential"),
        })
    return {"disease": {"id": disease.get("id"), "name": external_str(disease.get("name"))},
            "total": assoc.get("count"), "rows": rows}


def disease_row(row: dict[str, Any]) -> dict[str, Any]:
    """One `associatedDiseases` row: the disease, Open Targets' association score and its datatype breakdown."""
    disease = row.get("disease") or {}
    return {"id": disease.get("id"), "name": external_str(disease.get("name")),
            "association": round(float(row.get("score") or 0.0), 4), "datatypes": scores(row)}


def association(ensembl_id: str, efo_id: str) -> dict[str, Any] | None:
    """The evidence for one target-disease pair, asked of the source directly (a target's stored top
    indications are a sample). None means the source has nothing for the pair."""
    data = query(ONE_ASSOCIATION, {"id": ensembl_id, "ids": [efo_id]}).get("target") or {}
    rows = (data.get("associatedDiseases") or {}).get("rows") or []
    return disease_row(rows[0]) if rows else None
