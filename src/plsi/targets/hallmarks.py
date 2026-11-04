"""The hallmarks of aging as a computed frame, from one closed mapping (`AGING_MECHANISMS`).

`targets hallmarks --gene` reads the mechanisms Open Genes curated for a stored target and says which
hallmarks they sit under; `targets discover --hallmark` asks Open Genes for the genes under a hallmark's
mechanisms. Hallmark names follow Lopez-Otin et al. (Cell 2023, PMID 36599349); which mechanism sits under
which hallmark is PLSI's reading and is printed beside every row. Nothing is scored or ranked, and a hallmark
the source has no vocabulary for is reported differently from one with no evidence.
"""

from __future__ import annotations

from typing import Any

from plsi.targets import aging, store
from plsi.vocab.targets import AgingHallmark

# Open Genes' aging mechanisms -> (the numeric id `byAgingMechanism` filters on, the hallmark(s) it sits
# under). The mapping is PLSI's reading of Open Genes' words, so every reported hallmark names the mechanism
# it came from; a mechanism missing from this map is reported as unmapped. `None` marks a mechanism the source
# identifies by uuid only, which cannot be filtered server-side.
AGING_MECHANISMS: dict[str, tuple[int | None, tuple[AgingHallmark, ...]]] = {
    "nuclear DNA instability": (75, (AgingHallmark.GENOMIC_INSTABILITY,)),
    "nuclear architecture impairment": (76, (AgingHallmark.GENOMIC_INSTABILITY,)),
    "mitochondrial DNA instability": (74, (AgingHallmark.GENOMIC_INSTABILITY,
                                           AgingHallmark.MITOCHONDRIAL_DYSFUNCTION)),
    "telomere attrition": (77, (AgingHallmark.TELOMERE_ATTRITION,)),
    "alterations in histone modifications": (78, (AgingHallmark.EPIGENETIC_ALTERATIONS,)),
    "chromatin remodeling": (79, (AgingHallmark.EPIGENETIC_ALTERATIONS,)),
    "transcriptional alterations": (80, (AgingHallmark.EPIGENETIC_ALTERATIONS,)),
    "alterations in DNA methylation": (81, (AgingHallmark.EPIGENETIC_ALTERATIONS,)),
    "SIRT pathway dysregulation": (None, (AgingHallmark.EPIGENETIC_ALTERATIONS,
                                          AgingHallmark.DEREGULATED_NUTRIENT_SENSING)),
    "impairment of proteins folding and stability": (82, (AgingHallmark.LOSS_OF_PROTEOSTASIS,)),
    "degradation of proteolytic systems": (83, (AgingHallmark.LOSS_OF_PROTEOSTASIS,)),
    "disabled macroautophagy": (95, (AgingHallmark.DISABLED_MACROAUTOPHAGY,)),
    "TOR pathway dysregulation": (84, (AgingHallmark.DEREGULATED_NUTRIENT_SENSING,)),
    "AMPK pathway dysregulation": (85, (AgingHallmark.DEREGULATED_NUTRIENT_SENSING,)),
    "INS/IGF-1 pathway dysregulation": (86, (AgingHallmark.DEREGULATED_NUTRIENT_SENSING,)),
    "impairment of the mitochondrial integrity and biogenesis": (87, (AgingHallmark.MITOCHONDRIAL_DYSFUNCTION,)),
    "accumulation of reactive oxygen species": (88, (AgingHallmark.MITOCHONDRIAL_DYSFUNCTION,)),
    "senescent cells accumulation": (89, (AgingHallmark.CELLULAR_SENESCENCE,)),
    "stem cell exhaustion": (90, (AgingHallmark.STEM_CELL_EXHAUSTION,)),
    "intercellular communication impairment": (93, (AgingHallmark.ALTERED_INTERCELLULAR_COMMUNICATION,)),
    "changes in the extracellular matrix structure": (94, (AgingHallmark.ALTERED_INTERCELLULAR_COMMUNICATION,)),
    "sterile inflammation": (92, (AgingHallmark.CHRONIC_INFLAMMATION,)),
}

# Hallmarks no Open Genes mechanism maps onto: the source has no vocabulary for them.
HALLMARKS_NOT_IN_OPEN_GENES = frozenset({AgingHallmark.DYSBIOSIS})


def _hallmarks_of(mechanisms: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Mechanism names -> {hallmark: [the mechanisms that put it there]}, plus the unmapped ones."""
    found: dict[str, list[str]] = {}
    unmapped = []
    for mechanism in mechanisms:
        entry = AGING_MECHANISMS.get(str(mechanism or "").strip())
        if entry is None:
            unmapped.append(mechanism)
            continue
        for hallmark in entry[1]:
            found.setdefault(hallmark.value, []).append(mechanism)
    return found, unmapped


def frame(facts: dict[str, Any]) -> dict[str, Any]:
    """The hallmark frame for one gathered target, recomputed from the stored aging block."""
    aging_block = facts.get("aging") or {}
    curated = aging_block.get("curated")
    mechanisms = list(aging_block.get("mechanisms") or [])
    touched, unmapped = _hallmarks_of(mechanisms)
    rows = []
    for hallmark in AgingHallmark:
        via = touched.get(hallmark.value) or []
        rows.append({
            "hallmark": hallmark.value,
            "touched": bool(via),
            "via_mechanisms": via,
            # Why a hallmark is empty: no vocabulary in the source, gene not curated, not read, or none filed.
            "silence": None if via else
            "Open Genes has no mechanism vocabulary for this hallmark, so it cannot be seen from this source"
            if hallmark in HALLMARKS_NOT_IN_OPEN_GENES else
            "Open Genes does not curate this gene at all, so no hallmark is checked here" if curated is False
            else "this source was not read on this gather" if curated is None
            else "curated, and no mechanism under this hallmark is filed for this gene",
        })
    return {
        "gene": facts.get("symbol"),
        "curated": curated,
        "confidence": aging_block.get("confidence"),
        "mechanisms": mechanisms,
        "clusters": list(aging_block.get("clusters") or []),
        "why_curated": list(aging_block.get("why") or []),
        "rows": rows,
        "touched": sorted(touched),
        "touched_count": len(touched),
        "unmapped_mechanisms": unmapped,
        "evidence_counts": aging_block.get("counts") or {},
        "source": {"ref": "open_genes", "external_text": True},
        "mapping": "mechanism names are Open Genes'; hallmark names are Lopez-Otin et al. (PMID 36599349); "
                   "which mechanism sits under which hallmark is PLSI's reading and is printed beside every "
                   "row so it can be disagreed with",
        "not_a_score": "a gene touching more hallmarks is more broadly curated, which usually says how much "
                       "it has been studied. Nothing here ranks by this count and no total is drawn.",
    }


def hallmarks(gene: str) -> dict[str, Any]:
    """`plsi targets hallmarks --gene <SYMBOL>`: the aging frame for a gathered target (no network)."""
    document = store.load(gene)
    facts = document.get("facts") or {}
    found = frame(facts)
    return {**found, "gathered": document.get("gathered"),
            "empty": "this target has no Open Genes record, so there is no hallmark evidence to frame - "
                     "which is an absence of curation and not a statement that it has nothing to do with "
                     "aging" if found["curated"] is not True else None,
            "next": f"plsi targets show --gene {document.get('gene')}"}


def candidates(name: str, limit: int) -> dict[str, Any]:
    """`plsi targets discover --hallmark "<name>"`: the curated aging genes under one hallmark, alphabetical,
    with the source's confidence, the mechanisms that put each gene there and the curator's reason. No band
    (no disease is named) and no ranking. `name` is one of the closed AgingHallmark values."""
    hallmark = AgingHallmark(name)
    under = {mechanism: entry for mechanism, entry in AGING_MECHANISMS.items() if hallmark in entry[1]}
    if hallmark in HALLMARKS_NOT_IN_OPEN_GENES or not under:
        return {"hallmark": hallmark.value, "mechanisms": [], "candidates": [], "found": 0, "shown": 0,
                "unsearchable": [],
                "empty": f"Open Genes has no mechanism vocabulary under {hallmark.value!r}, so this hallmark "
                         "cannot be searched from this source. That is a coverage gap in Open Genes, not a "
                         "statement that no gene belongs here.",
                "source": {"ref": "open_genes", "external_text": True}, "next": None}

    genes: dict[str, dict[str, Any]] = {}
    searched, unsearchable, warnings = [], [], []
    for mechanism, (mechanism_id, _) in sorted(under.items()):
        if mechanism_id is None:
            # identified by uuid only, so it cannot be filtered; reported in `incomplete`
            unsearchable.append(mechanism)
            continue
        found = aging.by_mechanism(mechanism, mechanism_id)
        searched.append({"mechanism": mechanism, "genes": found["matched"],
                         "curated_total": found["curated_total"]})
        if found.get("warning"):
            warnings.append(found["warning"])
        for row in found["rows"]:
            entry = genes.setdefault(row["symbol"], {**row, "via_mechanisms": []})
            entry["via_mechanisms"].append(mechanism)

    rows = sorted(genes.values(), key=lambda r: r["symbol"])
    return {
        "hallmark": hallmark.value,
        "mechanisms": searched,
        "unsearchable": unsearchable,
        "found": len(rows), "shown": min(limit, len(rows)),
        "candidates": rows[:limit],
        "warnings": warnings or None,
        "source": {"ref": "open_genes", "external_text": True},
        "note": "curated aging genes under one hallmark, in alphabetical order. There is no band because no "
                "disease was named, and no ranking because Open Genes publishes no score and an order "
                "invented here would be this tool's opinion.",
        "incomplete": (f"{', '.join(unsearchable)} sits under this hallmark and has no numeric id in Open "
                       "Genes, so it could not be searched: this list is short by whatever it holds"
                       if unsearchable else None),
        "next": "plsi targets dossier --gene <symbol> --disease \"<indication>\"",
    }
