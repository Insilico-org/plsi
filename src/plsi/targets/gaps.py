"""What a target dossier does not settle: the questions its counts leave open, the places two of its sources
disagree (reported, never resolved), and the sources this gather could not read.

All three take the reads `rank.summary` already computed, so every command answers from one number.
Each sentence states what the record holds or lacks; interpreting it is the skill's job.
"""

from __future__ import annotations

from typing import Any

from plsi.targets.opentargets import CAUSAL_DATATYPES
from plsi.vocab.targets import ClinicalStage, DevelopmentLevel

Reads = dict[str, Any]  # the computed block in progress: band, stage, structures, chemistry, selectivity, …


def unread(facts: dict[str, Any]) -> list[dict[str, str]]:
    """The sources that did not answer on the gather that wrote these facts."""
    return [{"ref": str(source.get("ref")), "note": str(source.get("note") or "")}
            for source in facts.get("sources") or [] if source.get("ok") is False]


def disagreements(facts: dict[str, Any], reads: Reads) -> list[str]:
    """Where two sources say different things about the same question. Reported, never resolved."""
    out = []
    level = (reads.get("development") or {}).get("level")
    chem = reads.get("chemistry") or {}
    found = reads.get("structures") or {}
    uniprot = facts.get("protein") or {}
    # Two sources disagree only when both answered, so each rule is guarded by the sources it compares.
    spoke = {key: (reads.get(key) or {}).get("source_read") is not False
             for key in ("development", "chemistry", "structures", "protein")}
    assets_read = (facts.get("assets") or {}).get("read") is not False
    if spoke["development"] and spoke["chemistry"] \
            and level == DevelopmentLevel.TCHEM and chem.get("known") and not chem.get("potent_100nm"):
        out.append("Pharos calls this Tchem - potent chemistry exists - and ChEMBL holds nothing against it "
                   "under 100 nM (different thresholds)")
    if spoke["development"] and assets_read \
            and level == DevelopmentLevel.TCLIN and not (facts.get("assets") or {}).get("rows"):
        out.append("Pharos calls this Tclin - an approved drug acts on it - and Open Targets lists no drug")
    if spoke["protein"] and spoke["structures"] \
            and uniprot.get("known") and uniprot.get("pdb_entries") and not found.get("deposited"):
        out.append(f"UniProt cross-references {uniprot['pdb_entries']} PDB entries and the structure search "
                   "found none: the search is keyed on the accession and may have missed them")
    pocket = next((item["value"] for group in (facts.get("target") or {}).get("prioritisation") or []
                   for item in group["items"] if item["key"] == "hasPocket"), None)
    if spoke["structures"] and pocket is not None and pocket <= 0 and found.get("co_crystals"):
        out.append(f"Open Targets scores hasPocket {pocket:+.2f} and the PDB holds "
                   f"{found['co_crystals']} co-crystal(s)")
    identity = facts.get("identity") or {}
    if identity.get("resolvers_agree") is False:
        out.append("the two gene resolvers disagree about which gene this is - see the identity warning")
    return out


def not_read(facts: dict[str, Any], reads: Reads) -> list[str]:
    """The absences that belong to this gather (a source that did not answer) rather than to the field.
    Kept apart from `open_questions`: these call for a re-run."""
    out = []
    for key, what in (("structures", "the PDB"), ("chemistry", "ChEMBL"), ("development", "Pharos"),
                      ("protein", "UniProt"), ("genetics", "the Open Targets credible sets")):
        block = reads.get(key) or {}
        if block.get("source_read") is False:
            out.append(f"{what} was not read on this gather - {block.get('evidence')}. Nothing below about "
                       "it is a statement about the target")
    if ((facts.get("assets") or {}).get("read")) is False:
        out.append("the drug list was not read on this gather, so an empty asset table here is this "
                   "gather's silence and not the field's")
    if (facts.get("aging") or {}).get("read") is False:
        out.append("Open Genes was not read on this gather, so nothing here says whether this target has "
                   "anything to do with aging")
    if reads.get("stage_read") is False:
        out.append("the per-indication drug evidence was not read, so there is no stage for this indication "
                   "- and the target's furthest stage anywhere is not a substitute for one")
    return out


def open_questions(facts: dict[str, Any], reads: Reads) -> list[str]:  # noqa: C901 - one branch per absence
    """What this dossier does not answer, as observations. A block whose source was not read is skipped here
    and named in `not_read` instead."""
    out = []
    target = facts.get("target") or {}
    assets_block = facts.get("assets") or {}
    assets = assets_block.get("rows") or []
    indication = facts.get("indication") or {}
    aging = facts.get("aging") or {}
    found = reads.get("structures") or {}
    chem = reads.get("chemistry") or {}
    sel = reads.get("selectivity") or {}
    level = reads.get("development") or {}
    protein = reads.get("protein") or {}
    features = (facts.get("protein") or {}).get("features") or {}
    # The pocket, chemistry and residue questions assume a protein.
    is_protein = reads.get("protein_coding")

    if is_protein is False:
        out.append(f"this gene is {reads.get('biotype')}, not protein-coding: the tractability buckets, the "
                   "chemistry, the structures and the UniProt features below are all about proteins and none "
                   f"of them is a statement about it. {reads.get('not_a_protein_note')}")
    elif not reads.get("modalities"):
        out.append("no tractability bucket is true for any modality")
    if is_protein is not False and found.get("source_read") is not False and not found.get("co_crystals"):
        out.append(f"no co-crystal was read - {found.get('evidence')}")
    if is_protein is not False and chem.get("source_read") is not False:
        if chem.get("known") and not chem.get("potent_100nm"):
            out.append("chemistry has been filed against this protein and none of it reaches 100 nM")
        elif not chem.get("known"):
            out.append("no measured chemical matter: ChEMBL holds no assay against this protein")
        elif chem.get("family_target"):
            out.append("the chemistry is filed against a protein family, not this protein alone")
        if chem.get("known") and chem.get("activation") and not chem.get("inhibition"):
            out.append("every potent measurement read is an EC50 (activation); no inhibition measure is recorded")
        elif chem.get("known") and chem.get("inhibition") and not chem.get("activation"):
            out.append("every potent measurement read is inhibition or binding; no activation measure is recorded")
    if assets_block.get("read") is not False:
        if withdrawn := reads.get("withdrawn"):
            out.append(f"{len(withdrawn)} drug(s) against this target were withdrawn "
                       f"({', '.join(withdrawn[:4])})")
        if boxed := reads.get("black_boxed"):
            out.append(f"{len(boxed)} approved drug(s) against this target carry a boxed warning "
                       f"({', '.join(boxed[:4])})")
        if not assets:
            out.append("no drug or clinical candidate is on record in Open Targets (its coverage, not the "
                       "field's)")
        elif reads.get("stage_any_indication") in (ClinicalStage.PHASE_1.value,
                                                   ClinicalStage.PRECLINICAL.value, ClinicalStage.NONE.value):
            out.append("nothing against this target has passed phase 1 in any indication")
    if reads.get("stage_scoped") and reads.get("stage") == ClinicalStage.NONE.value and assets:
        out.append(f"no drug against this target has reached a trial in {indication.get('name')}, though "
                   f"{reads.get('assets')} asset(s) exist in other indications")
    if sel.get("paralogue_at_or_above_mark"):
        out.append(f"{sel.get('nearest_paralogue')} is {sel.get('paralogue_identity_pct')}% identical "
                   f"full-length (at or above {sel.get('paralogue_mark_pct')}%); the active-site identity is "
                   "not recorded")
    if sel.get("no_lab_model"):
        out.append("no orthologue is recorded in any routine lab species")
    if sel.get("model_below_mark"):
        out.append(f"the {sel.get('model_species')} orthologue is {sel.get('model_identity_pct')}% "
                   f"identical full-length (below {sel.get('model_mark_pct')}%)")
    if level.get("source_read") is not False:
        if level.get("level") == DevelopmentLevel.TDARK:
            out.append("Pharos calls this Tdark: almost nothing is known about it")
        elif not level.get("known"):
            out.append("Pharos holds no target development level for it")
    if is_protein is not False and protein.get("source_read") is not False:
        if not features.get("domain"):
            out.append("no domain is annotated in UniProt")
        if not (features.get("binding") or features.get("active-site")):
            out.append("no binding or active site is annotated in UniProt")
    gen = reads.get("genetics") or {}
    if gen.get("source_read") is not False:
        if not gen.get("has_pqtl"):
            out.append("no pQTL is recorded, as expected for an RNA gene" + ("; an eQTL is recorded" if gen.get("has_eqtl")
                                                                    else "; no eQTL is recorded either")
                       if is_protein is False else
                       "no pQTL is recorded on this gene" + ("; an eQTL (transcript level) is recorded"
                                                             if gen.get("has_eqtl") else ""))
    assignment = reads.get("gene_assignment") or {}
    if assignment and assignment.get("read") is not False and indication:
        best = assignment.get("best_l2g")
        if best is None:
            out.append(f"no GWAS credible set assigns a locus to this gene for {indication.get('name')}")
        elif best < (assignment.get("threshold") or 0.5):
            out.append(f"the best locus-to-gene score for {indication.get('name')} is {best:.2f}, below the "
                       f"{assignment.get('threshold')} Open Targets uses to assign a locus to a gene")
    if (reads.get("direction") or {}).get("known") is False and indication \
            and (reads.get("direction") or {}).get("source_read") is not False:
        out.append(f"no direction of effect is recorded for this target in {indication.get('name')}")
    if not target.get("safety"):
        out.append("no safety liability is recorded (an absence of curation, not a clean record)")
    if not any(str(c.get("kind")) == "lof" and c.get("bin") is not None for c in target.get("constraint") or []):
        out.append("no loss-of-function constraint is recorded")
    if not (target.get("expression") or {}).get("rows"):
        out.append("no baseline expression is recorded")
    if indication:
        live = {k for k, v in (indication.get("datatypes") or {}).items() if v > 0}
        if not live:
            out.append(f"Open Targets records no evidence linking this target to {indication.get('name')} "
                       "(the pair was asked for directly)")
        elif not live & CAUSAL_DATATYPES:
            out.append(f"the association with {indication.get('name')} rests on "
                       f"{', '.join(sorted(live))} - no genetics and no animal model")
    if aging.get("read") is False:
        pass  # said in `not_read`: an unreachable source is not a statement about the gene
    elif aging.get("curated") is False:
        out.append("Open Genes does not curate this gene")
    elif aging.get("curated"):
        if not aging.get("longevity"):
            out.append("Open Genes records no human longevity association for this gene")
        if aging.get("lifespan") and not aging.get("cited"):
            out.append("none of the lifespan experiments shown carries a PMID or DOI")
    return out
