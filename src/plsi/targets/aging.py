"""Open Genes: whether a target has anything to do with aging, and what that rests on.

Lifespan experiments are animal results and longevity associations are human genetic ones; they are kept apart.
A gene Open Genes has not curated answers `curated: false`, which is different from "no aging evidence".
"""

from __future__ import annotations

import urllib.parse
from functools import lru_cache
from typing import Any

from plsi import net, references
from plsi.errors import NetworkError
from plsi.models import external_str
from plsi.vocab import SourceKind

# Open Genes' `methylationCorrelation` codes. Any other code is reported as unread.
OPEN_GENES_METHYLATION = {"1": "methylation correlates with age", "0": "no correlation with age recorded"}

MAX_EXPERIMENTS = 12
MAX_ASSOCIATIONS = 8
MAX_AGE_CHANGES = 8


def _source(item: dict[str, Any]) -> dict[str, str] | None:
    """The row's PMID or DOI as a SourceRef-shaped pair (Open Genes fills one and leaves the other empty)."""
    pmid, doi = str(item.get("pmid") or "").strip(), str(item.get("doi") or "").strip()
    if pmid.isdigit():
        return {"kind": SourceKind.PMID.value, "id": pmid}
    if doi.startswith("10."):
        return {"kind": SourceKind.DOI.value, "id": external_str(doi)}
    return None


def _interventions(interventions: Any) -> list[dict[str, Any]]:
    """The experiment's intervention entries, flattened out of the nested groups."""
    groups = interventions.values() if isinstance(interventions, dict) else []
    return [row for group in groups if isinstance(group, list) for row in group if isinstance(row, dict)]


def _perturbed(item: dict[str, Any], gene_id: Any) -> dict[str, Any]:
    """Which gene this experiment changed. Open Genes files an experiment under a gene when the gene is part
    of the mechanism, so each intervention's own `gene` id is compared with the record's: `this-gene`,
    `with-others` (also another gene), `unstated` (no entry names a gene; the filing stands) or `another-gene`,
    the only kind excluded from claims."""
    entries = _interventions(item.get("interventions"))
    genes = {entry.get("gene") for entry in entries if entry.get("gene") is not None}
    others = sorted(g for g in genes if g != gene_id)
    if not genes:
        kind = "unstated"  # no intervention entry names a gene: unverifiable, not contradicted
    elif gene_id in genes:
        kind = "with-others" if others else "this-gene"
    else:
        kind = "another-gene"
    return {
        "kind": kind,
        "on_this_gene": kind != "another-gene",
        "other_gene_ids": others,
        "genotypes": sorted({external_str(e.get("genotype")) for e in entries if e.get("genotype")})[:4],
        "methods": sorted({external_str(e.get("interventionMethod")) for e in entries
                           if e.get("interventionMethod")})[:4],
        "effects": sorted({external_str(e.get("experimentMainEffect")) for e in entries
                           if e.get("experimentMainEffect")})[:3],
    }


def _change(item: dict[str, Any]) -> float | None:
    """The mean lifespan change as a magnitude. Open Genes states the direction in words and its sign does not
    always agree with them, so the words carry the direction."""
    value = item.get("lifespanMeanChangePercent")
    return abs(value) if isinstance(value, (int, float)) else None


def _lifespan(item: dict[str, Any], gene_id: Any) -> dict[str, Any]:
    """One lifespan experiment, percentages as the record holds them."""
    perturbed = _perturbed(item, gene_id)
    return {
        "organism": external_str(item.get("modelOrganism")), "line": external_str(item.get("organismLine")),
        "sex": external_str(item.get("sex")), "intervention": external_str(item.get("interventionResultForLifespan")),
        "methods": perturbed["methods"],
        "perturbed": perturbed,
        "change_mean_pct": _change(item),
        "change_max_pct": item.get("lifespanMaxChangePercent"),
        "significance": external_str(item.get("lMeanChangeStatSignificance")) or None,
        "source": _source(item),
    }


def _age_change(item: dict[str, Any]) -> dict[str, Any]:
    """One age-related change in expression, methylation or activity."""
    return {
        "organism": external_str(item.get("modelOrganism")), "sex": external_str(item.get("sex")) or None,
        "measured": external_str(item.get("expressionEvaluationBy")) or None,
        "tissue": external_str(item.get("sample")) or None,
        "change": external_str(item.get("changeType")) or None,
        "value": external_str(item.get("value")) or None,
        "age_from": item.get("meanAgeOfControls"), "age_to": item.get("meanAgeOfExperiment"),
        "age_unit": external_str(item.get("ageUnit")) or None,
        "source": _source(item),
    }


def _association(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "effect": external_str(item.get("longevityEffect")),
        "variant": external_str(item.get("polymorphismId")) or None,
        "allele": external_str(item.get("associatedAllele")) or None,
        "ethnicity": external_str(item.get("ethnicity")) or None,
        "study": external_str(item.get("studyType")) or None, "source": _source(item),
    }


MAX_MECHANISM_GENES = 200  # one page of the source's own search


def _search(params: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One page of Open Genes' `/gene/search` -> (its `options`, its gene rows)."""
    data = net.get_json(f"{references.api_base('open_genes')}/gene/search", {**params, "page": 1})
    if not isinstance(data, dict):
        raise NetworkError("Open Genes returned something this version could not read", code="BAD_RESPONSE")
    return data.get("options") or {}, [item for item in data.get("items") or [] if isinstance(item, dict)]


@lru_cache(maxsize=1)
def curated_symbols() -> frozenset[str]:
    """Every gene symbol Open Genes curates, upper-cased, cached: the source's own total is read first and the
    whole corpus is then asked for in one page of that size. A reply shorter than the total raises rather than
    returning a partial corpus."""
    total = _search({"pageSize": 1})[0].get("total") or 0
    if not total:
        raise NetworkError("Open Genes reported no corpus size", code="BAD_RESPONSE")
    items = _search({"pageSize": total})[1]
    if len(items) < total:
        raise NetworkError(f"Open Genes returned {len(items)} of {total} curated genes; a partial corpus "
                           "would under-report every intersection built on it", code="BAD_RESPONSE")
    return frozenset(external_str(item.get("symbol")).upper() for item in items if item.get("symbol"))


def by_mechanism(mechanism: str, mechanism_id: int, limit: int = MAX_MECHANISM_GENES) -> dict[str, Any]:
    """Every curated gene Open Genes files under one aging mechanism. The source ignores an unknown filter
    and returns the whole corpus, so each returned gene is checked against the mechanism name and a
    mismatch is reported."""
    options, items = _search({"byAgingMechanism": mechanism_id, "pageSize": limit})
    pagination = options.get("pagination") or {}
    wanted = mechanism.strip().lower()
    rows, mismatched = [], []
    for item in items:
        names = {external_str(m.get("name")).strip().lower() for m in item.get("agingMechanisms") or []}
        row = {
            "symbol": external_str(item.get("symbol")), "name": external_str(item.get("name")),
            "confidence": external_str((item.get("confidenceLevel") or {}).get("name")) or None,
            "mechanisms": [external_str(m.get("name")) for m in item.get("agingMechanisms") or []][:8],
            "clusters": [external_str(c.get("name")) for c in item.get("functionalClusters") or []][:6],
            "why": [external_str(c.get("name")) for c in item.get("commentCause") or []][:6],
        }
        (rows if wanted in names else mismatched).append(row)
    return {
        "mechanism": mechanism, "mechanism_id": mechanism_id,
        "matched": len(rows), "returned": len(items),
        "curated_total": options.get("objTotal"), "corpus": options.get("total"),
        "pages": pagination.get("pagesTotal"),
        "rows": rows,
        "filter_ignored": bool(items) and not rows,
        "mismatched": len(mismatched),
        "warning": (f"Open Genes returned {len(items)} genes and not one of them carries "
                    f"{mechanism!r}: the filter was ignored, so this is the corpus and not a shortlist"
                    if items and not rows else
                    f"{len(mismatched)} of {len(items)} returned genes do not carry {mechanism!r} and were "
                    "dropped" if mismatched else None),
    }


def _methylation(value: Any) -> str | None:
    if value is None:
        return None
    return OPEN_GENES_METHYLATION.get(str(value).strip(), f"Open Genes code {value!r}, which this version cannot read")


def _origin(family: Any) -> dict[str, Any] | None:
    """The clade the gene family first appears in, with the source's own age estimate."""
    if not isinstance(family, dict) or not family.get("phylum"):
        return None
    return {"phylum": external_str(family.get("phylum")), "age_mya": external_str(family.get("age")) or None}


def relevance(symbol: str) -> dict[str, Any]:
    """`{curated, confidence, mechanisms, clusters, why, lifespan[], longevity[], age_related[]}` for one gene
    symbol: animal lifespan work and human longevity associations kept apart."""
    # Quoted: the symbol can come from a search reply.
    gene = urllib.parse.quote(symbol.strip(), safe="")
    record = net.get_json(f"{references.api_base('open_genes')}/gene/{gene}", missing=(400, 404))
    if not isinstance(record, dict) or not record.get("symbol"):
        return {"curated": False, "note": f"Open Genes does not curate {symbol}"}
    studies = record.get("researches") or {}
    gene_id = record.get("id")

    # Rows on this gene first, then the cap, so the sample shown is the part a claim can rest on.
    all_lifespan = [_lifespan(item, gene_id) for item in studies.get("increaseLifespan") or []]
    all_lifespan.sort(key=lambda row: (not row["perturbed"]["on_this_gene"], row["source"] is None))
    lifespan = all_lifespan[:MAX_EXPERIMENTS]
    longevity = [_association(item) for item in
                 (studies.get("geneAssociatedWithLongevityEffects") or [])[:MAX_ASSOCIATIONS]]
    age_related = [_age_change(item) for item in
                   (studies.get("ageRelatedChangesOfGene") or [])[:MAX_AGE_CHANGES]]
    off_target = sum(1 for row in all_lifespan if not row["perturbed"]["on_this_gene"])
    return {
        "curated": True,
        "confidence": external_str((record.get("confidenceLevel") or {}).get("name")) or None,
        # The clade the gene family first appears in, with the source's age estimate.
        "family_origin": _origin(record.get("familyOrigin")),
        "methylation_with_age": _methylation(record.get("methylationCorrelation")),
        "mechanisms": [external_str(m.get("name")) for m in record.get("agingMechanisms") or []][:8],
        "clusters": [external_str(c.get("name")) for c in record.get("functionalClusters") or []][:8],
        "why": [external_str(c.get("name")) for c in record.get("commentCause") or []][:8],
        "lifespan": lifespan,
        "longevity": longevity,
        "age_related": age_related,
        # `shown` beside the counts, so a sample is never read as the evidence base.
        "shown": {"lifespan": len(lifespan), "longevity": len(longevity), "age_related": len(age_related)},
        "counts": {"lifespan_experiments": len(all_lifespan),
                   "lifespan_on_this_gene": len(all_lifespan) - off_target,
                   "lifespan_on_another_gene": off_target,
                   "longevity_associations": len(studies.get("geneAssociatedWithLongevityEffects") or []),
                   "age_related_changes": len(studies.get("ageRelatedChangesOfGene") or []),
                   "progeria": len(studies.get("geneAssociatedWithProgeriaSyndromes") or [])},
        "cited": sum(1 for item in lifespan + longevity + age_related if item["source"]),
        "note": (f"{off_target} of {len(all_lifespan)} curated lifespan experiments perturbed a gene other "
                 f"than {record.get('symbol')}; Open Genes files an experiment under a gene when that gene is "
                 "in the mechanism, not only when it was the thing changed. Read `perturbed` on every row."
                 if off_target else None),
    }
