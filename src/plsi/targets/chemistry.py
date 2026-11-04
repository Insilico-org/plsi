"""ChEMBL: whether measured chemical matter exists against a protein, and at what potency.

A ChEMBL target can be a protein family (activities filed against two paralogues together), so a single-protein
target is preferred and the kind is reported. pChEMBL is -log10(molar): 7 is 100 nM and 8 is 10 nM.
"""

from __future__ import annotations

from typing import Any

from plsi import net, references
from plsi.models import external_str

# Inhibition and binding (IC50, Ki, Kd) and activation (EC50) measures; reported separately, never pooled.
ACTIVITY_TYPES = "IC50,Ki,Kd,EC50"
INHIBITION_MEASURES = frozenset({"IC50", "KI", "KD"})
POTENT = 7.0  # pChEMBL 7 = 100 nM
VERY_POTENT = 8.0  # 10 nM
MAX_COMPOUNDS = 10
MAX_MEASURE_SAMPLE = 1_000  # rows read to split potency by measure; the split is of these, not of the total
SINGLE_PROTEIN = "SINGLE PROTEIN"
# No relation filter: ChEMBL assigns `pchembl_value` only to exact (`=`) measurements.


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    return net.get_json(f"{references.api_base('chembl')}/{path}", params) or {}


def _targets(accession: str) -> list[dict[str, Any]]:
    data = _get("target.json", {"target_components__accession": accession, "limit": 10})
    return data.get("targets") or []


def _count(target_id: str, minimum: float) -> int:
    """How many measured activities clear a potency floor, from `page_meta.total_count` (one row fetched)."""
    data = _get("activity.json", {"target_chembl_id": target_id, "standard_type__in": ACTIVITY_TYPES,
                                  "pchembl_value__gte": minimum, "limit": 1})
    return int((data.get("page_meta") or {}).get("total_count") or 0)


def _measures(target_id: str, minimum: float) -> dict[str, int]:
    """How the potent measurements split between inhibition and activation, over one page of them."""
    data = _get("activity.json", {"target_chembl_id": target_id, "standard_type__in": ACTIVITY_TYPES,
                                  "pchembl_value__gte": minimum, "limit": MAX_MEASURE_SAMPLE})
    rows = data.get("activities") or []
    out: dict[str, int] = {}
    for row in rows:
        kind = external_str(row.get("standard_type")).upper()
        if kind:
            out[kind] = out.get(kind, 0) + 1
    return {"sampled": len(rows), "by_measure": out,
            "inhibition": sum(n for k, n in out.items() if k in INHIBITION_MEASURES),
            "activation": sum(n for k, n in out.items() if k not in INHIBITION_MEASURES)}


def _best(target_id: str) -> tuple[int, list[dict[str, Any]]]:
    """The most potent distinct compounds and how many measurements reach 10 nM, in one request."""
    data = _get("activity.json", {"target_chembl_id": target_id, "standard_type__in": ACTIVITY_TYPES,
                                  "pchembl_value__gte": VERY_POTENT, "order_by": "-pchembl_value",
                                  "limit": MAX_COMPOUNDS * 3})
    total = int((data.get("page_meta") or {}).get("total_count") or 0)
    seen: dict[str, dict[str, Any]] = {}
    for row in data.get("activities") or []:
        molecule = external_str(row.get("molecule_chembl_id"))
        if not molecule or molecule in seen:
            continue
        seen[molecule] = {
            "chembl_id": molecule, "name": external_str(row.get("molecule_pref_name")) or None,
            "measure": external_str(row.get("standard_type")), "value": row.get("standard_value"),
            "unit": external_str(row.get("standard_units")) or None,
            "pchembl": row.get("pchembl_value"), "document": external_str(row.get("document_chembl_id")) or None,
        }
        if len(seen) >= MAX_COMPOUNDS:
            break
    return total, list(seen.values())


def ligandability(accession: str) -> dict[str, Any]:
    """Measured chemical matter against one UniProt accession. `curated: false` means ChEMBL has no target
    record for the protein at all."""
    targets = _targets(accession)
    if not targets:
        return {"curated": False, "accession": accession,
                "note": "ChEMBL holds no target record for this protein: no assay has been filed against it"}
    single = [t for t in targets if str(t.get("target_type") or "").upper() == SINGLE_PROTEIN]
    chosen = (single or targets)[0]
    target_id = external_str(chosen.get("target_chembl_id"))
    very, compounds = _best(target_id)
    potent = _count(target_id, POTENT)
    measures = _measures(target_id, POTENT) if potent else {"sampled": 0, "by_measure": {},
                                                            "inhibition": 0, "activation": 0}
    return {
        "curated": True, "accession": accession, "target_chembl_id": target_id,
        "target_name": external_str(chosen.get("pref_name")),
        "target_kind": external_str(chosen.get("target_type")),
        "family_target": not single,  # activities filed against a family are not evidence about one protein
        "other_targets": len(targets) - 1,
        "potent_100nm": potent, "potent_10nm": very,
        "measures": measures,
        "compounds": compounds,
        "scale": f"pChEMBL is -log10(molar): {POTENT:.0f} is 100 nM, {VERY_POTENT:.0f} is 10 nM",
    }
