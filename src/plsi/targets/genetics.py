"""Human genetics on a target from Open Targets: fine-mapped molecular QTLs and locus-to-gene scores.

`target.credibleSets` says whether natural variation moves this gene's transcript (eQTL) or protein (pQTL)
in people. The L2G score is Open Targets' locus-to-gene probability for this gene at a GWAS locus for the
named disease. Counts are over the rows read and labelled as samples; nothing is scored or combined.
"""

from __future__ import annotations

from typing import Any

from plsi.models import external_str
from plsi.targets.opentargets import query

# Molecular QTL study types in Open Targets credible sets, protein first, with what each one measures.
QTL_TYPES = ("pqtl", "eqtl", "sceqtl", "sqtl", "tuqtl")
QTL_MEANING = {
    "pqtl": "plasma protein level",
    "eqtl": "transcript level in a tissue",
    "sceqtl": "transcript level in one cell type",
    "sqtl": "splicing",
    "tuqtl": "transcript usage",
}

# Rows read; the breakdowns are of these and `sampled` says so.
MAX_CREDIBLE_SETS = 200
MAX_GWAS_EVIDENCE = 100
MAX_PROJECTS = 6

CREDIBLE_SETS = """query Genetics($id: String!, $n: Int!) {
  target(ensemblId: $id) {
    credibleSets(page: {index: 0, size: $n}) {
      count
      rows { studyType beta study { projectId } }
    }
  }
}"""

GWAS_FOR_PAIR = """query Gwas($efo: String!, $ids: [String!]!, $n: Int!) {
  disease(efoId: $efo) {
    evidences(ensemblIds: $ids, datasourceIds: ["gwas_credible_sets"], size: $n) {
      count
      rows { score }
    }
  }
}"""

# Open Targets' working threshold for assigning a locus to a gene; the maximum is reported too.
L2G_CONFIDENT = 0.5


def instruments(ensembl_id: str) -> dict[str, Any]:
    """The fine-mapped molecular QTLs on this gene, by type, counted over the rows read."""
    data = query(CREDIBLE_SETS, {"id": ensembl_id, "n": MAX_CREDIBLE_SETS}).get("target") or {}
    found = data.get("credibleSets") or {}
    rows = found.get("rows") or []
    by_type: dict[str, int] = {}
    projects: dict[str, set[str]] = {}
    for row in rows:
        kind = external_str(row.get("studyType")).lower()
        if not kind:
            continue
        by_type[kind] = by_type.get(kind, 0) + 1
        project = external_str((row.get("study") or {}).get("projectId"))
        if project:
            projects.setdefault(kind, set()).add(project)
    return {
        "total": found.get("count") or 0,
        "sampled": len(rows),
        "by_type": [{"type": kind, "sets": by_type[kind], "means": QTL_MEANING.get(kind),
                     "projects": sorted(projects.get(kind, set()))[:MAX_PROJECTS]}
                    for kind in sorted(by_type, key=lambda k: (QTL_TYPES.index(k) if k in QTL_TYPES else 99))],
        "has_pqtl": by_type.get("pqtl", 0) > 0,
        "has_eqtl": by_type.get("eqtl", 0) + by_type.get("sceqtl", 0) > 0,
        "note": "fine-mapped credible sets from Open Targets, counted over the rows read. A pQTL is "
                "variation in the protein level; an eQTL is variation in a transcript level.",
    }


def gene_assignment(ensembl_id: str, efo_id: str) -> dict[str, Any]:
    """Open Targets' locus-to-gene scores for this gene at the GWAS loci of this pair: the best score and
    how many loci reach L2G_CONFIDENT."""
    data = query(GWAS_FOR_PAIR, {"efo": efo_id, "ids": [ensembl_id], "n": MAX_GWAS_EVIDENCE})
    found = ((data.get("disease") or {}).get("evidences")) or {}
    rows = found.get("rows") or []
    scores = sorted((float(row["score"]) for row in rows if row.get("score") is not None), reverse=True)
    if not scores:
        return {"loci": found.get("count") or 0, "sampled": len(rows), "best_l2g": None,
                "confident_loci": 0, "threshold": L2G_CONFIDENT,
                "evidence": "no GWAS credible set in Open Targets assigns a locus to this gene for this "
                            "disease. That is an absence of recorded evidence, not evidence of no link."}
    best = round(scores[0], 3)
    confident = sum(1 for score in scores if score >= L2G_CONFIDENT)
    return {
        "loci": found.get("count") or 0, "sampled": len(rows),
        "best_l2g": best, "confident_loci": confident, "threshold": L2G_CONFIDENT,
        "evidence": f"best locus-to-gene score {best:.2f}"
                    + (f", and {confident} locus(es) at or above {L2G_CONFIDENT}"
                       if confident else
                       f", below the {L2G_CONFIDENT} the pipeline uses to assign a locus to a gene"),
    }
