"""`plsi targets brief`: the citable part of a dossier, small enough to hand to the research bots.

It writes nothing into a research topic or a note; PLSI carries it as a card. Each row hands over the claim,
the identifier and the exact stored record. A curated database record is not a quote from the paper, so a
finding written from it passes no `text`, and its quote stays unverified until the source is retrieved.
"""

from __future__ import annotations

from typing import Any

from plsi.targets import gaps, rank, store
from plsi.vocab import SourceKind
from plsi.vocab.research import ResearchDesign, ResearchSpecies
from plsi.vocab.targets import StructureState

# human evidence first, then work with no biological subject, then animal and in-vitro work
SPECIES_ORDER = {s: i for i, s in enumerate((ResearchSpecies.HUMAN, ResearchSpecies.NOT_APPLICABLE,
                                              ResearchSpecies.ANIMAL, ResearchSpecies.IN_VITRO))}

MAX_FACTS = 30


def _fact(claim: str, source: dict[str, str] | None, record: str, design: ResearchDesign,
          species: ResearchSpecies, origin: str) -> dict[str, Any]:
    """One citable row, with `design` and `species` from the research graph's closed lists."""
    return {"claim": claim, "source": source, "record": record,
            "design": design.value, "species": species.value, "origin": origin}


def _origin(source: dict[str, str] | None, fallback: str) -> str:
    """The independence key for the research graph: the paper (kind:id) when there is one, else `fallback`."""
    return f"{source['kind']}:{source['id']}" if source else fallback


def _aging_facts(gene: str, aging: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in aging.get("lifespan") or []:
        perturbed = item.get("perturbed") or {}
        # An experiment that perturbed a different gene is never a claim about this one.
        if perturbed and not perturbed.get("on_this_gene"):
            continue
        change = item.get("change_mean_pct")
        amount = f"by {change}% at the mean" if change is not None else "(no percentage recorded)"
        genotypes = "; ".join(perturbed.get("genotypes") or []) or "not recorded"
        others = perturbed.get("other_gene_ids") or []
        alongside = f" (alongside {len(others)} other gene(s) in the same animal)" if others else ""
        out.append(_fact(
            f"{gene}: {item.get('intervention') or 'lifespan change'} in "
            f"{item.get('organism') or 'an animal model'} {amount}{alongside}",
            item.get("source"),
            f"Open Genes lifespan record: organism {item.get('organism')}, line {item.get('line')}, "
            f"sex {item.get('sex')}, methods {'; '.join(item.get('methods') or []) or 'not recorded'}, "
            f"genotype {genotypes}, perturbed {perturbed.get('kind')}, "
            f"mean change {change}% (magnitude; direction is in the result wording), "
            f"max change {item.get('change_max_pct')}, significant {item.get('significance')}",
            ResearchDesign.MECHANISTIC, ResearchSpecies.ANIMAL, _origin(item.get("source"), f"open-genes:{gene}")))
    for item in aging.get("longevity") or []:
        out.append(_fact(
            f"{gene} {item.get('variant') or 'variant'}: {item.get('effect') or 'longevity association'} in people",
            item.get("source"),
            f"Open Genes longevity association: variant {item.get('variant')}, allele {item.get('allele')}, "
            f"ethnicity {item.get('ethnicity')}, study {item.get('study')}",
            ResearchDesign.OBSERVATIONAL, ResearchSpecies.HUMAN, _origin(item.get("source"), f"open-genes:{gene}")))
    for item in aging.get("age_related") or []:
        human = str(item.get("organism") or "").lower() == "human"
        out.append(_fact(
            f"{gene}: {item.get('change') or 'changes'} in {item.get('tissue') or 'tissue'} with age"
            + (f", {item.get('value')}" if item.get("value") else "")
            + f" ({item.get('age_from')} to {item.get('age_to')} {item.get('age_unit') or ''})".rstrip(" )") + ")",
            item.get("source"),
            f"Open Genes age-related change: organism {item.get('organism')}, tissue {item.get('tissue')}, "
            f"measured by {item.get('measured')}, {item.get('change')}, value {item.get('value')}, "
            f"ages {item.get('age_from')} to {item.get('age_to')} {item.get('age_unit')}",
            ResearchDesign.OBSERVATIONAL, ResearchSpecies.HUMAN if human else ResearchSpecies.ANIMAL,
            _origin(item.get("source"), f"open-genes:{gene}")))
    return out


def _safety_facts(gene: str, target: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in target.get("safety") or []:
        pmid = str(item.get("pmid") or "").strip()
        source = {"kind": SourceKind.PMID.value, "id": pmid} if pmid.isdigit() else None
        out.append(_fact(
            f"{gene}: {item.get('event')} reported as a safety liability",
            source,
            f"Open Targets safety liability: event {item.get('event')}, source {item.get('datasource')}",
            ResearchDesign.MECHANISTIC, ResearchSpecies.NOT_APPLICABLE,
            _origin(source, f"opentargets-safety:{item.get('datasource')}")))
    return out


def _asset_facts(gene: str, assets: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in assets.get("rows") or []:
        what = (row.get("mechanisms") or [row.get("modality") or "mechanism not recorded"])[0]
        for trial in row.get("trials") or []:
            nct = str(trial.get("id") or "")
            if not nct.startswith("NCT"):
                continue
            out.append(_fact(
                f"{row.get('drug')} ({what}) reached {trial.get('phase')} against {gene}",
                {"kind": SourceKind.NCT.value, "id": nct},
                f"ClinicalTrials.gov via Open Targets: phase {trial.get('phase')}, "
                f"status {trial.get('status')}, sponsor {trial.get('sponsor')}",
                ResearchDesign.CONTROLLED_TRIAL, ResearchSpecies.HUMAN, nct))
    return out


def _structure_facts(gene: str, found: dict[str, Any]) -> list[dict[str, Any]]:
    """Holo entries only: a deposited ligand-bound structure is a checkable claim, an apo entry is not."""
    out = []
    for row in (found.get("rows") or [])[:4]:
        if row.get("state") != StructureState.HOLO:
            continue
        ligands = ", ".join(f"{lig['id']} ({lig['name']})" for lig in row.get("ligands") or [])
        out.append(_fact(
            f"{gene}: a ligand-bound structure exists at {row.get('resolution_a')} Å (PDB {row.get('pdb_id')})",
            None,  # a PDB entry is not a SourceKind the ledger can verify; the accession is in the record
            f"RCSB PDB {row.get('pdb_id')}: {row.get('method')}, resolution {row.get('resolution_a')} A, "
            f"released {row.get('released')}, bound {ligands or 'none named'}",
            ResearchDesign.MECHANISTIC, ResearchSpecies.IN_VITRO, f"pdb:{row.get('pdb_id')}"))
    return out


def _sampled(facts: dict[str, Any]) -> dict[str, Any] | None:
    """`shown of total` per curated list, or None when nothing was cut."""
    aging = facts.get("aging") or {}
    shown, counts = aging.get("shown") or {}, aging.get("counts") or {}
    pairs = {"lifespan": counts.get("lifespan_experiments"),
             "longevity": counts.get("longevity_associations"),
             "age_related": counts.get("age_related_changes")}
    cut = {key: {"shown": shown.get(key, 0), "of": total}
           for key, total in pairs.items() if total and total > shown.get(key, 0)}
    if not cut:
        return None
    return {**cut, "note": "a sample, not the evidence base; `--limit` cannot raise it because the cut was "
                           "made when the dossier was gathered. Say `n of N` wherever you use these."}


def brief(gene: str, question: str | None = None, limit: int = MAX_FACTS) -> dict[str, Any]:
    """The citable part of a dossier, for a research move or a note: human evidence first, then trials,
    then animal and mechanistic work."""
    document = store.load(gene)
    facts = document.get("facts") or {}
    symbol = str(document.get("gene") or gene)
    rows = _asset_facts(symbol, facts.get("assets") or {}) \
        + _aging_facts(symbol, facts.get("aging") or {}) \
        + _safety_facts(symbol, facts.get("target") or {}) \
        + _structure_facts(symbol, facts.get("structures") or {})
    rows.sort(key=lambda r: (SPECIES_ORDER.get(r["species"], len(SPECIES_ORDER)), r["source"] is None))
    cited = [row for row in rows if row["source"]][:limit]
    uncitable = [row for row in rows if not row["source"]]
    assessment = document.get("assessment") or {}
    computed = rank.summary(facts)
    return {
        "gene": symbol, "question": question, "gathered": document.get("gathered"),
        "what_it_is": facts.get("name"), "function": (facts.get("target") or {}).get("function"),
        "band": computed.get("band"), "stage": computed.get("stage"),
        "facts": cited, "uncited": len(rows) - len(cited),
        # What the dossier stored against what the source holds (cut at gather time).
        "sampled": _sampled(facts),
        # Accessions the verification ledger has no kind for (PDB entries): checkable by hand, not sources.
        "accessions": [{"claim": row["claim"], "record": row["record"], "origin": row["origin"]}
                       for row in uncitable][:limit],
        "open_questions": computed.get("open_questions"),
        # Absences that belong to this gather travel with the open questions.
        "not_read": computed.get("not_read") or None,
        "sources_unread": [s["ref"] for s in gaps.unread(facts)] or None,
        "gather_warning":
            "this dossier was gathered while one or more sources were unreachable: whatever it says is "
            "missing from them is missing from THIS GATHER. Do not write a finding that rests on one of "
            "those absences without re-gathering." if gaps.unread(facts) else None,
        "assessment": {"verdict": assessment.get("verdict"), "falsifier": assessment.get("falsifier"),
                       "limitations": assessment.get("limitations")} if assessment else None,
        "how_to_use": "Each row is a database record with its identifier, not a sentence from a paper. To save "
                      "one as a finding, retrieve the source and quote its results sentence; a finding written "
                      "from the `record` string alone is honest only with no `text`, so its quote stays unverified. "
                      "`design` and `species` are filled in from what the record is; check them against the "
                      "source you retrieve. Verify every identifier before citing it.",
        "boundary": "This brief writes nothing to a research topic or a note. It is material for a move the "
                    "receiving bot makes itself.",
    }
