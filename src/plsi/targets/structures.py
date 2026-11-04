"""Structures: what the PDB holds for a protein and whether anything was bound, with AlphaFold when the PDB
has nothing.

An entry is holo when a real ligand is bound: crystallisation additives (named in ADDITIVES) and components
under MIN_LIGAND_DA do not count. A prediction is a model, never an experiment.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from plsi import net, references
from plsi.models import external_str
from plsi.vocab.targets import StructureState

MAX_ENTRIES = 12  # read in one GraphQL call

# Crystallisation additives, cryoprotectants, buffer components and ions: not ligands.
ADDITIVES = frozenset({
    "HOH", "DOD", "EDO", "GOL", "PEG", "PG4", "PGE", "1PE", "P6G", "2PE", "MPD", "DMS", "TRS", "EPE", "MES",
    "ACT", "ACY", "FMT", "CIT", "FLC", "TLA", "MLI", "MLA", "SIN", "BME", "DTT", "IMD", "BTB", "BCT",
    "SO4", "PO4", "NO3", "CL", "BR", "IOD", "F", "NA", "K", "MG", "CA", "ZN", "MN", "FE", "FE2", "NI", "CU",
    "CU1", "CD", "HG", "CO", "CS", "RB", "SR", "BA", "LI", "AU", "PT", "SE", "UNX", "UNL", "NH4", "AZI",
    "GLC", "NAG", "BMA", "MAN", "FUC", "XYP", "SUC", "TRT", "LDA", "BOG", "OLC", "PLM", "MYR", "STE",
})
MIN_LIGAND_DA = 150.0

SEARCH = {
    "return_type": "entry",
    "request_options": {"paginate": {"start": 0, "rows": MAX_ENTRIES},
                        "results_content_type": ["experimental"],
                        "sort": [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}]},
}
ENTRIES = """query Entries($ids: [String!]!) {
  entries(entry_ids: $ids) {
    rcsb_id
    struct { title }
    rcsb_entry_info { resolution_combined experimental_method }
    rcsb_accession_info { initial_release_date }
    nonpolymer_entities { nonpolymer_comp { chem_comp { id name formula_weight } } }
  }
}"""


def _term(attribute: str, value: str) -> dict[str, Any]:
    return {"type": "terminal", "service": "text",
            "parameters": {"attribute": attribute, "operator": "exact_match", "value": value}}


def _accession_query(accession: str) -> dict[str, Any]:
    return {**SEARCH, "query": {"type": "group", "logical_operator": "and", "nodes": [
        _term("rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
              accession),
        _term("rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_name",
              "UniProt")]}}


def _ligands(entity_rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """The bound components that are not crystallisation chemistry."""
    out = []
    for entity in entity_rows or []:
        comp = ((entity or {}).get("nonpolymer_comp") or {}).get("chem_comp") or {}
        code = str(comp.get("id") or "").upper()
        weight = comp.get("formula_weight")
        if not code or code in ADDITIVES:
            continue
        if weight is not None and float(weight) < MIN_LIGAND_DA:
            continue
        out.append({"id": code, "name": external_str(comp.get("name")), "weight_da": weight})
    return out


def _entries(ids: list[str]) -> list[dict[str, Any]]:
    rows = []
    for entry in net.graphql(references.api_base("rcsb_data"), ENTRIES, {"ids": ids}).get("entries") or []:
        info = entry.get("rcsb_entry_info") or {}
        resolution = (info.get("resolution_combined") or [None])[0]
        ligands = _ligands(entry.get("nonpolymer_entities"))
        rows.append({
            "pdb_id": external_str(entry.get("rcsb_id")).upper(),
            "title": external_str((entry.get("struct") or {}).get("title")),
            "method": external_str(info.get("experimental_method")),
            "resolution_a": resolution,
            "released": external_str((entry.get("rcsb_accession_info") or {}).get("initial_release_date"))[:10] or None,
            "state": StructureState.HOLO.value if ligands else StructureState.APO.value,
            "ligands": ligands,
        })
    rows.sort(key=lambda r: (r["resolution_a"] is None, r["resolution_a"] or 0))
    return rows


def experimental(accession: str) -> dict[str, Any]:
    """Deposited structures for one UniProt accession, best resolution first."""
    reply = net.post_json(f"{references.api_base('rcsb_pdb')}/query", _accession_query(accession))
    if reply.status == 204 or not reply.text.strip():  # RCSB answers a zero-hit search with No Content
        return {"total": 0, "shown": 0, "rows": []}
    found = reply.json()
    ids = [str(r.get("identifier") or "").upper() for r in found.get("result_set") or []]
    ids = [i for i in ids if i][:MAX_ENTRIES]
    return {"total": found.get("total_count") or 0, "shown": len(ids),
            "rows": _entries(ids) if ids else []}


def predicted(accession: str) -> dict[str, Any] | None:
    """The AlphaFold model for one accession, or None. Mean pLDDT is reported with the confidently modelled
    and disordered fractions, because a folded domain and a disordered tail average out."""
    data = net.get_json(f"{references.api_base('alphafold')}/prediction/{urllib.parse.quote(accession, safe='')}",
                        missing=(400, 404))
    model = (data or [None])[0]
    if not isinstance(model, dict):
        return None
    very_high, confident = model.get("fractionPlddtVeryHigh"), model.get("fractionPlddtConfident")
    low, very_low = model.get("fractionPlddtLow"), model.get("fractionPlddtVeryLow")
    usable = None if very_high is None or confident is None else round(very_high + confident, 3)
    return {"entry_id": external_str(model.get("entryId")), "confidence_plddt": model.get("globalMetricValue"),
            "fraction_well_modelled": usable,
            "fraction_disordered": None if low is None or very_low is None else round(low + very_low, 3),
            "version": model.get("latestVersion"), "created": external_str(model.get("modelCreatedDate"))[:10] or None,
            "note": "a predicted model, not an experiment: pLDDT says where the fold is confident, not that a "
                    "pocket exists"
                    + ("" if usable is None else
                       f". {usable:.0%} of the chain is modelled confidently or better; the mean is a "
                       "whole-chain average")}


def structures(accession: str) -> dict[str, Any]:
    """Everything structural for one accession; AlphaFold is read only when the PDB has nothing."""
    found = experimental(accession)
    out: dict[str, Any] = {"accession": accession, **found,
                           "holo": sum(1 for r in found["rows"] if r["state"] == StructureState.HOLO)}
    out["predicted"] = predicted(accession) if not found["rows"] else None
    return out
