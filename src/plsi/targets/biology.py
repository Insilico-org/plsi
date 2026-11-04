"""What Open Targets holds about the protein itself: prioritisation scores, interaction network, expression,
homology, essentiality, constraint, safety and names. The prioritisation scores are passed through grouped
and never summed.
"""

from __future__ import annotations

from typing import Any

from plsi.errors import NotFound
from plsi.models import external_str
from plsi.targets.opentargets import CAP_PROSE, disease_row, prose, query, tractability

# Open Targets' signed prioritisation scores (-1..+1). Keys and values are theirs; the grouping is for reading
# only and nothing sums a group. A key outside these lists is kept under `other`.
PRIORITISATION_GROUPS: dict[str, tuple[str, ...]] = {
    "precedence": ("maxClinicalStage",),
    "tractability": ("hasLigand", "hasSmallMoleculeBinder", "hasPocket", "hasHighQualityChemicalProbes"),
    "doability": ("isInMembrane", "isSecreted", "mouseOrthologMaxIdentityPercentage"),
    "safety": ("geneticConstraint", "geneEssentiality", "hasSafetyEvent", "isCancerDriverGene",
               "mouseKOScore", "paralogMaxIdentityPercentage", "tissueSpecificity", "tissueDistribution",
               "celltypeSpecificity", "celltypeDistribution"),
}

DEPENDENT = -0.5  # DepMap calls a cell line dependent on a gene below this; -1 is the common-essential median
MAX_SAFETY = 20
MAX_PHENOTYPES = 20
MAX_PROBES = 10
MAX_PATHWAYS = 12
MAX_PARTNERS = 20
MAX_TISSUES = 12
MAX_HOMOLOGUES = 8
PARTNER_SCORE = 0.75  # STRING/IntAct combined score: below this a partner is a hint, not a neighbour
PARALOG = "paralog"  # Open Targets homologyType is e.g. ortholog_one2one, within_species_paralog

TARGET = """query Target($id: String!, $n: Int!, $partners: Float!) {
  target(ensemblId: $id) {
    id approvedSymbol approvedName biotype isEssential
    functionDescriptions
    symbolSynonyms { label }
    nameSynonyms { label }
    obsoleteSymbols { label }
    pharmacogenomics { pgxCategory evidenceLevel isDirectTarget variantRsId phenotypeText
                       drugs { drugFromSource } }
    targetClass { label }
    subcellularLocations { location }
    proteinIds { id source }
    genomicLocation { chromosome start end strand }
    tractability { label modality value }
    geneticConstraint { constraintType score upperBin6 }
    safetyLiabilities { event datasource literature }
    chemicalProbes { id isHighQuality }
    mousePhenotypes { modelPhenotypeLabel modelPhenotypeClasses { label } }
    prioritisation { items { key value } }
    pathways { pathwayId pathway topLevelTerm }
    homologues { speciesName homologyType targetGeneSymbol targetPercentageIdentity
                 queryPercentageIdentity isHighConfidence }
    interactions(scoreThreshold: $partners) { count rows { score sourceDatabase targetB { approvedSymbol } } }
    baselineExpression { count rows { datasourceId median specificity_score unit
                                      tissueBiosample { biosampleName } celltypeBiosample { biosampleName } } }
    depMapEssentiality { tissueName screens { cellLineName geneEffect } }
    literatureOcurrences { count earliestPubYear }
    associatedDiseases(page: {index: 0, size: $n}) {
      count
      rows { score datatypeScores { id score } disease { id name } }
    }
  }
}"""


def _uniprot(protein_ids: list[dict[str, Any]] | None) -> str | None:
    """The reviewed (Swiss-Prot) accession; TrEMBL entries are not used."""
    for item in protein_ids or []:
        if str(item.get("source") or "") == "uniprot_swissprot":
            return external_str(item.get("id"))
    return None


def _prioritisation(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """The signed scores as an ordered list of groups (so the order survives a sorted JSON round trip), with
    unknown keys under `other`."""
    scored: dict[str, float] = {}
    for item in items or []:
        key = external_str(item.get("key"))
        try:
            scored[key] = round(float(item.get("value")), 3)
        except (TypeError, ValueError):
            continue
    out, placed = [], set()
    for group, keys in PRIORITISATION_GROUPS.items():
        rows = [{"key": key, "value": scored[key]} for key in keys if key in scored]
        if rows:
            out.append({"group": group, "items": rows})
            placed.update(row["key"] for row in rows)
    if extra := [{"key": k, "value": v} for k, v in scored.items() if k not in placed]:
        out.append({"group": "other", "items": extra})
    return out


def _partners(interactions: dict[str, Any] | None) -> dict[str, Any]:
    rows, seen = [], set()
    for row in (interactions or {}).get("rows") or []:
        symbol = external_str((row.get("targetB") or {}).get("approvedSymbol"))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        rows.append({"symbol": symbol, "score": round(float(row.get("score") or 0.0), 3),
                     "source": external_str(row.get("sourceDatabase"))})
    rows.sort(key=lambda r: -r["score"])
    return {"total": (interactions or {}).get("count") or 0, "rows": rows[:MAX_PARTNERS],
            "score_threshold": PARTNER_SCORE}


def _expression(expression: dict[str, Any] | None) -> dict[str, Any]:
    """The tissues and cell types where the protein is most expressed, with the source's specificity score.
    Ranked within each source, never across them: the units differ between sources."""
    rows = []
    for row in (expression or {}).get("rows") or []:
        median = row.get("median")
        if median is None:
            continue
        tissue = external_str((row.get("tissueBiosample") or {}).get("biosampleName"))
        celltype = external_str((row.get("celltypeBiosample") or {}).get("biosampleName"))
        rows.append({"tissue": tissue or None, "cell_type": celltype or None,
                     "median": round(float(median), 2), "unit": external_str(row.get("unit")) or None,
                     "specificity": round(float(row.get("specificity_score")), 3)
                     if row.get("specificity_score") is not None else None,
                     "source": external_str(row.get("datasourceId"))})
    by_source: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_source.setdefault(row["source"], []).append(row)
    out, per_source = [], max(1, MAX_TISSUES // max(1, len(by_source)))
    for source in sorted(by_source):
        group = sorted(by_source[source], key=lambda r: -r["median"])
        out.extend(group[:per_source])
    return {"measurements": (expression or {}).get("count") or 0, "rows": out,
            "sources": {source: len(group) for source, group in sorted(by_source.items())},
            "note": "ranked within each source; the units differ between sources and are not comparable"}


def _homology(homologues: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Orthologues and paralogues with both identity percentages Open Targets computed: `query_identity`
    (share of the human protein) and `target_identity` (share of the other one)."""
    orthologues, paralogues = [], []
    for row in homologues or []:
        kind = external_str(row.get("homologyType"))
        item = {"symbol": external_str(row.get("targetGeneSymbol")), "species": external_str(row.get("speciesName")),
                "kind": kind,
                "query_identity": round(float(row["queryPercentageIdentity"]), 1)
                if row.get("queryPercentageIdentity") is not None else None,
                "target_identity": round(float(row["targetPercentageIdentity"]), 1)
                if row.get("targetPercentageIdentity") is not None else None}
        (paralogues if PARALOG in kind else orthologues).append(item)
    for group in (orthologues, paralogues):
        group.sort(key=lambda r: -(r["query_identity"] or 0))
    return {"orthologues": orthologues[:MAX_HOMOLOGUES], "paralogues": paralogues[:MAX_HOMOLOGUES],
            "note": "identity is full-length and computed by Open Targets; an active-site identity is a "
                    "different number and is not here"}


def _essentiality(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    """DepMap gene-effect scores per tissue; a line counts as dependent below -0.5 (DepMap's cutoff)."""
    tissues, lines, dependent = [], 0, 0
    for row in rows or []:
        effects = [s.get("geneEffect") for s in row.get("screens") or [] if s.get("geneEffect") is not None]
        if not effects:
            continue
        below = sum(1 for e in effects if float(e) < DEPENDENT)
        lines, dependent = lines + len(effects), dependent + below
        tissues.append({"tissue": external_str(row.get("tissueName")), "lines": len(effects), "dependent": below,
                        "mean_effect": round(sum(float(e) for e in effects) / len(effects), 3)})
    tissues.sort(key=lambda t: t["mean_effect"])
    return {"cell_lines": lines, "dependent_lines": dependent, "cutoff": DEPENDENT,
            "tissues": tissues[:MAX_TISSUES]}


MAX_NAMES = 12
MAX_PGX = 12


def _labels(items: list[dict[str, Any]] | None) -> list[str]:
    return sorted({external_str(item.get("label")) for item in items or [] if item.get("label")})[:MAX_NAMES]


def _names(data: dict[str, Any]) -> dict[str, list[str]]:
    """Symbols, protein names and retired symbols, kept apart because each finds the gene somewhere else."""
    return {"symbols": _labels(data.get("symbolSynonyms")),
            "protein_names": _labels(data.get("nameSynonyms")),
            "obsolete_symbols": _labels(data.get("obsoleteSymbols"))}


def _pharmacogenomics(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Pharmacogenomic variants, listing only those Open Targets marks as acting on this target."""
    direct = [r for r in rows or [] if r.get("isDirectTarget")]
    kinds: dict[str, int] = {}
    for row in direct:
        key = external_str(row.get("pgxCategory")) or "unclassified"
        kinds[key] = kinds.get(key, 0) + 1
    return {
        "total": len(rows or []), "on_this_target": len(direct),
        "by_category": kinds,
        "rows": [{"rsid": external_str(r.get("variantRsId")) or None,
                  "category": external_str(r.get("pgxCategory")) or None,
                  "evidence_level": external_str(r.get("evidenceLevel")) or None,
                  "effect": external_str(r.get("phenotypeText"), CAP_PROSE) or None,
                  "drugs": sorted({external_str(d.get("drugFromSource")) for d in r.get("drugs") or []
                                   if d.get("drugFromSource")})[:3]}
                 for r in direct[:MAX_PGX]],
        "note": "only variants Open Targets marks as acting on THIS target are listed; the total counts "
                "every pharmacogenomic row filed under the gene, including ones about other drugs",
    }


def profile(ensembl_id: str) -> dict[str, Any]:
    """One target's biology from Open Targets, with every long list capped."""
    data = query(TARGET, {"id": ensembl_id, "n": 8, "partners": PARTNER_SCORE}).get("target")
    if not data:
        raise NotFound(f"Open Targets has no target {ensembl_id!r}", code="TARGET_NOT_FOUND")
    literature = data.get("literatureOcurrences") or {}
    return {
        "ensembl_id": data.get("id"), "symbol": external_str(data.get("approvedSymbol")),
        "name": external_str(data.get("approvedName")), "biotype": external_str(data.get("biotype")),
        "uniprot": _uniprot(data.get("proteinIds")),
        "location": _location(data.get("genomicLocation")),
        "function": prose((data.get("functionDescriptions") or [""])[0]),
        "classes": [external_str(c.get("label")) for c in data.get("targetClass") or []][:6],
        "other_names": _names(data),
        "pharmacogenomics": _pharmacogenomics(data.get("pharmacogenomics")),
        "locations": sorted({external_str(loc.get("location")) for loc in data.get("subcellularLocations") or []})[:8],
        "tractability": tractability(data.get("tractability")),
        "constraint": [{"kind": external_str(c.get("kind") or c.get("constraintType")), "score": c.get("score"),
                        "bin": c.get("upperBin6")} for c in data.get("geneticConstraint") or []],
        "essential": data.get("isEssential"),
        "essentiality": _essentiality(data.get("depMapEssentiality")),
        "probes": [{"id": external_str(p.get("id")), "high_quality": p.get("isHighQuality")}
                   for p in data.get("chemicalProbes") or []][:MAX_PROBES],
        "safety": [{"event": external_str(s.get("event")), "datasource": external_str(s.get("datasource")),
                    "pmid": external_str(s.get("literature")) or None}
                   for s in data.get("safetyLiabilities") or []][:MAX_SAFETY],
        "mouse_phenotypes": [{"phenotype": external_str(p.get("modelPhenotypeLabel")),
                              "classes": [external_str(c.get("label"))
                                          for c in p.get("modelPhenotypeClasses") or []][:2]}
                             for p in data.get("mousePhenotypes") or []][:MAX_PHENOTYPES],
        "prioritisation": _prioritisation((data.get("prioritisation") or {}).get("items")),
        "pathways": [{"id": external_str(p.get("pathwayId")), "name": external_str(p.get("pathway")),
                      "area": external_str(p.get("topLevelTerm"))} for p in data.get("pathways") or []][:MAX_PATHWAYS],
        "pathways_total": len(data.get("pathways") or []),
        "homology": _homology(data.get("homologues")),
        "network": _partners(data.get("interactions")),
        "expression": _expression(data.get("baselineExpression")),
        "literature": {"publications": literature.get("count"), "first_year": literature.get("earliestPubYear")},
        "indications": [disease_row(row) for row in (data.get("associatedDiseases") or {}).get("rows") or []],
        "indications_total": (data.get("associatedDiseases") or {}).get("count"),
    }


def _location(location: dict[str, Any] | None) -> str | None:
    if not location or location.get("chromosome") is None:
        return None
    strand = "+" if str(location.get("strand") or "").upper().startswith("P") else "-"
    return f"chromosome {external_str(location['chromosome'])} {location.get('start')}-{location.get('end')} ({strand})"
