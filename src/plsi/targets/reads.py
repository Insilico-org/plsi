"""The per-source reads in a dossier's computed block: structures, chemistry, selectivity, development level,
genetic instruments and protein features.

Each read is a count or a lookup over what the gather stored, reported in the source's own terms. A block whose
source did not answer comes back with `source_read: False`, which is what `gaps` branches on.
"""

from __future__ import annotations

from typing import Any

from plsi.vocab.targets import StructureState

# Species a programme routinely runs experiments in, matched as substrings of Open Targets' species names.
LAB_SPECIES = ("mouse", "rat", "zebrafish", "fruitfly", "drosophila", "nematode", "caenorhabditis",
               "dog", "pig", "rabbit", "macaque", "cynomolgus", "rhesus")

# Reported marks, not verdicts: whether an identity is at or above / below the mark is stated as a fact.
PARALOGUE_MARK_PCT = 60.0
ORTHOLOGUE_MARK_PCT = 70.0


def unread(found: dict[str, Any]) -> dict[str, Any] | None:
    """The block every read returns when its source did not answer, else None."""
    if found.get("read") is False:
        return {"source_read": False, "known": False,
                "evidence": found.get("note") or "the source did not answer"}
    return None


def structural(found: dict[str, Any]) -> dict[str, Any]:
    """Co-crystals (holo entries), apo entries and the predicted model. `co_crystals` counts the
    `entries_read`; `deposited` and `sampled` say when that is a floor."""
    if gap := unread(found):
        return {**gap, "deposited": None, "entries_read": 0, "co_crystals": 0,
                "best_resolution_a": None, "best_pdb": None, "best_co_crystal": None,
                "predicted_plddt": None, "sampled": False}
    rows = found.get("rows") or []
    holo = [r for r in rows if r.get("state") == StructureState.HOLO]
    best = next((r for r in rows if r.get("resolution_a") is not None), None)
    predicted = found.get("predicted") or None
    deposited = found.get("total") or 0
    return {
        "source_read": True,
        "deposited": deposited, "entries_read": len(rows),
        "co_crystals": len(holo),
        "sampled": deposited > len(rows),
        "best_resolution_a": (best or {}).get("resolution_a"),
        "best_pdb": (best or {}).get("pdb_id"),
        "best_co_crystal": (holo[0]["pdb_id"] if holo else None),
        "predicted_plddt": (predicted or {}).get("confidence_plddt"),
        "predicted_well_modelled": (predicted or {}).get("fraction_well_modelled"),
        "predicted_disordered": (predicted or {}).get("fraction_disordered"),
        "evidence": ("a co-crystal exists: a ligand is bound in at least one entry" if holo
                     else "structures exist and every one read is apo" if rows else
                     "a predicted model only; nothing has been crystallised" if predicted else
                     "no structure, experimental or predicted")
                    + (f" ({len(holo)} co-crystal(s) among the {len(rows)} entries read of {deposited} "
                       f"deposited - a floor, not a total)" if deposited > len(rows) else ""),
    }


def chemical(found: dict[str, Any]) -> dict[str, Any]:
    """Whether measured chemical matter exists, split by inhibition and activation, and whether it is filed
    against a protein family rather than this protein alone."""
    if gap := unread(found):
        return {**gap, "potent_100nm": 0, "potent_10nm": 0, "curated": None}
    if found.get("curated") is not True:
        return {"source_read": True, "known": False, "curated": found.get("curated"),
                "potent_100nm": 0, "potent_10nm": 0,
                "evidence": found.get("note") or "no chemistry was read"}
    potent, very = found.get("potent_100nm") or 0, found.get("potent_10nm") or 0
    measures = found.get("measures") or {}
    inhibition, activation = measures.get("inhibition") or 0, measures.get("activation") or 0
    direction = ("both inhibition and activation measures are recorded" if inhibition and activation
                 else "all of it is activation (EC50)" if activation
                 else "all of it is inhibition or binding" if inhibition else None)
    return {
        "source_read": True, "curated": True,
        "known": True, "potent_100nm": potent, "potent_10nm": very,
        "inhibition": inhibition, "activation": activation,
        "by_measure": measures.get("by_measure") or {},
        "measures_sampled": measures.get("sampled") or 0,
        "chemistry_direction": direction,
        "family_target": bool(found.get("family_target")),
        "evidence": (f"{potent} measured activities at 100 nM or better, {very} at 10 nM or better" if potent
                     else "a ChEMBL target exists but nothing reaches 100 nM")
                    + (f" - of {measures['sampled']} read, {direction}" if direction and measures.get("sampled")
                       else "")
                    + (" - filed against a protein family, not this protein alone"
                       if found.get("family_target") else ""),
    }


def selectivity(homology: dict[str, Any]) -> dict[str, Any]:
    """The nearest paralogue and the nearest routine lab species, with Open Targets' full-length identities
    and whether each is at or past its reported mark."""
    paralogues = homology.get("paralogues") or []
    orthologues = homology.get("orthologues") or []
    nearest = paralogues[0] if paralogues else None
    lab = [o for o in orthologues if any(s in str(o.get("species") or "").lower() for s in LAB_SPECIES)]
    mouse = next((o for o in lab if "mouse" in str(o.get("species") or "").lower()), None)
    model = mouse or (lab[0] if lab else None)
    return {
        "lab_model": bool(lab),
        "no_lab_model": bool(orthologues) and not lab,
        "nearest_paralogue": (nearest or {}).get("symbol"),
        "paralogue_identity_pct": (nearest or {}).get("query_identity"),
        "paralogue_mark_pct": PARALOGUE_MARK_PCT,
        "paralogue_at_or_above_mark": bool(nearest and (nearest.get("query_identity") or 0) >= PARALOGUE_MARK_PCT),
        "model_species": (model or {}).get("species"),
        "model_identity_pct": (model or {}).get("query_identity"),
        "model_mark_pct": ORTHOLOGUE_MARK_PCT,
        "model_below_mark": bool(model and (model.get("query_identity") or 0) < ORTHOLOGUE_MARK_PCT),
        "note": "full-length identity as Open Targets computed it; active-site identity is not recorded. "
                "`model_species` is the nearest routine lab species, not the nearest orthologue of any kind",
    }


def development(found: dict[str, Any]) -> dict[str, Any]:
    """Pharos' target development level and patent series, passed through as Pharos' own."""
    if gap := unread(found):
        return {**gap, "level": None}
    if not found.get("known"):
        return {"source_read": True, "known": False, "level": None,
                "evidence": found.get("note") or "no development level was read"}
    level = found.get("level")
    return {"source_read": True, "known": True, "level": level,
            "recognised": bool(found.get("level_recognised")),
            "patents": found.get("patents"), "patent_note": found.get("patent_note"),
            "family": found.get("family"), "novelty": found.get("novelty"),
            "evidence": f"{level}: {found.get('meaning')}" if found.get("meaning")
            else f"{level} (a level this version does not know)"}


def instruments(found: dict[str, Any], protein_coding: bool | None = None) -> dict[str, Any]:
    """The fine-mapped molecular QTLs on this gene, counted over the rows read. A pQTL is variation in the
    protein itself; an eQTL is variation in a transcript."""
    if gap := unread(found):
        return {**gap, "has_pqtl": None, "has_eqtl": None, "sets": 0}
    rows = found.get("by_type") or []
    pqtl = next((r for r in rows if r["type"] == "pqtl"), None)
    return {
        "source_read": True, "known": bool(rows),
        "sets": found.get("total") or 0, "sampled": found.get("sampled") or 0,
        "by_type": rows,
        "has_pqtl": bool(pqtl), "has_eqtl": bool(found.get("has_eqtl")),
        "pqtl_projects": (pqtl or {}).get("projects") or [],
        "evidence": (f"{pqtl['sets']} fine-mapped pQTL credible set(s): variation in the protein itself"
                     if pqtl else
                     "fine-mapped eQTLs exist; this is an RNA gene, so no pQTL is expected"
                     if rows and protein_coding is False else
                     "fine-mapped molecular QTLs exist and none is a pQTL" if rows else
                     "no fine-mapped molecular QTL is recorded on this gene"),
    }


def constraint_note(constraint: list[dict[str, Any]]) -> str | None:
    """Loss-of-function intolerance in the source's own bin (0 = the most constrained sixth of genes)."""
    lof = next((c for c in constraint if str(c.get("kind")) == "lof" and c.get("bin") is not None), None)
    return f"loss-of-function constraint bin {lof['bin']} of 5 (0 = most intolerant)" if lof else None


def protein(found: dict[str, Any]) -> dict[str, Any]:
    """Length, named domains, site counts, mutagenesis and activity regulation from UniProt."""
    if gap := unread(found):
        return {**gap, "length_aa": None, "domains": [], "binding_sites": 0, "active_sites": 0,
                "transmembrane": 0}
    features = found.get("features") or {}
    return {"source_read": True, "known": bool(found.get("known")), "length_aa": found.get("length_aa"),
            "mutagenesis": found.get("mutagenesis") or [],
            "regulation": found.get("regulation") or [],
            "domains": [f"{f['description'] or 'domain'} ({f['span']})" for f in features.get("domain") or []],
            "binding_sites": len(features.get("binding") or []),
            "active_sites": len(features.get("active-site") or []),
            "transmembrane": len(features.get("transmembrane") or [])}
