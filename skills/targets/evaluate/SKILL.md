---
name: evaluate
description: Use as PLSI Target Hunter when one named target has to be evaluated end to end - what it is, what it is associated with, whether it can be drugged, what it would cost in safety, who is already there, and what would show the case is wrong - ending in a target file that can be shared with the Longevity Mothership.
---

# PLSI target evaluation

Follow `persona.md` (repo root) and `shared/team`. Owner: **PLSI Target Hunter**. Reply only in handoffs to PLSI; never
message the user.

One target, the questions below, one assessment. A shortlist is `targets/discover`; this is the long form for one
candidate.

## When to use

- "Evaluate <gene> as a target", "is <gene> druggable", "<gene> for <disease>", "who else is working on <gene>".
- Scope it with a disease whenever there is one: a phase, a safety read and the competitive picture are all per
  indication.

## The questions

In this order, because each one can end the evaluation.

| | Question | Where the answer comes from |
|---|---|---|
| 0 | Is the gene a protein? | `protein_coding`; if false, the structure, chemistry and residue sections do not apply |
| 1 | Is it the gene we meant? | `identity`: two independent resolvers and the aliases |
| 2 | What is it associated with, and on what? | the per-datatype breakdown, scoped to the indication |
| 3 | How confidently does the GWAS point at this gene? | `gene_assignment.best_l2g` |
| 4 | How worked-over is it? | the Pharos development level (`Tclin`, `Tchem`, `Tbio`, `Tdark`) |
| 5 | Where do Open Targets' pipelines put it? | the prioritisation panel of signed scores |
| 6 | Does it matter for aging? | the Open Genes block, animal and human apart; `plsi targets hallmarks` frames it |
| 7 | Which part would a molecule bind? | UniProt domains, binding and active sites with residue ranges |
| 8 | Has anyone put a molecule in a pocket? | PDB entries, apo against holo, with `entries_read` of `deposited` |
| 9 | Has anyone made a molecule that binds it, and in which direction? | ChEMBL potencies, `family_target`, `inhibition` against `activation` (EC50 is agonism; IC50, Ki and Kd are not) |
| 10 | What would it be confused with, and what reads across? | computed paralogue and orthologue identity |
| 11 | What would it cost in safety? | liabilities, constraint, DepMap, expression breadth, mouse; `withdrawn`, `black_boxed`, `pharmacogenomics` |
| 12 | Who is already there, in this indication? | `stage` (this indication) against `stage_any_indication`; then `plsi targets trials`, reading `with_results` |
| 13 | Is there a human genetic instrument on it? | `genetics`: a pQTL is the protein itself, an eQTL the transcript and a weaker claim |
| 14 | Which way do we push it? | `direction`: Open Targets' `(on_trait, on_target)` pair; `(protect, LoF)` means inhibit |
| 15 | What is the way in, and what would show it is wrong? | your judgment; start the falsifier from `protein.mutagenesis`, residues already changed with a recorded consequence |

One command reads the free sources (MyGene.info, Open Targets, Pharos, the RCSB PDB, AlphaFold, ChEMBL, UniProt,
Open Genes); `plsi targets trials` grounds question 12 on ClinicalTrials.gov. None needs a key. When the user has set
a PandaOmics or PandaClaw token of their own, the dossier's `keyed` block says what it would add and what is left
of today's cap; read `targets/pandaomics` before spending a call.

## Steps

1. **Gather.**

   ```bash
   plsi targets dossier --gene <SYMBOL> --disease "<indication>"
   ```

   Check these before reading anything else:
   - **`unread`**: sources that did not answer. Their absences belong to this gather, not to the field;
     `computed.not_read` names the questions now unanswerable (see When the gather came back incomplete).
   - **`protein_coding: false`**: say so in the first line and consider oligonucleotide modalities, which none of
     these sources covers.
   - **`scope_warning`**: a gather without `--disease` dropped the indication the stored assessment names.
   - **`warning`** and `exact_symbol_match: false`: the resolvers disagree or guessed. Settle the identity and
     gather again; everything after inherits the mistake. Use the symbol in `data.gene` from here on.
   - **`aliases`**: search the literature under these too; reviews name the protein, not the symbol.
   - **`disagreements`**: two sources contradict each other. Report both; never resolve it for them.
   - **`band_basis`**: "not among this target's recorded associations" means the link has to be argued from the
     literature, a weaker evaluation. Say so in the first line.

2. **Read what the records do not say.** `computed.open_questions` is read off the counts:

   | It says | It means |
   |---|---|
   | no tractability bucket true | nothing says this protein can be drugged |
   | no co-crystal read | nothing to design a pocket from; all-apo and predicted-only are degrees of the same gap |
   | nobody has filed an assay | the strongest negative on chemical matter |
   | filed against a protein family | potency is not about this protein alone |
   | selectivity is a chemistry problem | the nearest paralogue is close full-length; the active-site identity is not in the dossier |
   | reads across weakly | the orthologue is distant: an animal result is a weak argument about people |
   | nothing past phase 1 | efficacy in people is untested |
   | no safety liability recorded | an absence of curation, not a clean target |
   | no constraint recorded | what happens when a person lacks the gene is unknown |
   | no baseline expression | nothing says where an on-target effect would land |
   | Tdark | almost nothing is known |
   | no domain, binding or active site annotated | any residue number in a pocket claim would be an estimate |
   | association rests on literature only | co-mention: a reason to look |
   | association rests on `clinical` only | a drug reached a trial here and nothing says this target is why |
   | Open Genes does not curate it | the aging link is unchecked here |

   These are usually the honest content of `limitations`.

3. **Check the field.** The dossier says what is recorded; the literature says what happened.

   ```bash
   plsi evidence search --source pubmed    --query "<gene> <indication> inhibitor" --limit 20
   plsi evidence search --source europepmc --query "EXT_ID:<pmid>" --limit 1   # the abstract for one paper
   plsi evidence search --source ctgov     --query "<gene or compound>" --limit 20
   plsi evidence search --source openfda   --query "<approved compound>" --limit 5
   plsi evidence verify --kind pmid --id <id>
   ```

   `pubmed` ranks by relevance and returns no abstract; `europepmc` returns abstracts and ranks by date, so find a
   paper on `pubmed` and read its abstract through `europepmc`. A DOI check confirms the DOI resolves, not that it
   is the paper claimed: for a directional claim, read the abstract. A knockout phenotype from a high-throughput
   screen needs a targeted-knockout paper before it is stated as fact (`targets/grounding`).

4. **Harvest the field** when the competitive picture matters (repurposing, crowding, "who else is there"). The
   asset table is a floor: trials are indexed by drug, not by gene. Do it as `targets/landscape` says.

5. **Write the assessment.**

   ```bash
   plsi targets assess --gene <SYMBOL> --file assessment.json
   ```

   ```json
   {"verdict": "pursue|monitor|deprioritize",
    "druggability": "high|moderate|low|unknown", "safety": "high|moderate|low|unknown",
    "competition": "high|moderate|low|unknown",
    "indication": "<the one this is about>",
    "rationale": "... (PMID 12345678) ...",
    "falsifier": "what we would see if this target were the wrong one",
    "next_experiment": "the cheapest thing that would settle it",
    "limitations": ["what this did not cover"],
    "risks": [{"dimension": "...", "risk": "high|moderate|low|unknown", "evidence": "... (NCT01234567)",
               "mitigation": "..."}],
    "strategies": [{"name": "...", "modality": "small-molecule|antibody|protac|other-modality",
                    "description": "... (PMID 12345678)"}],
    "harvested_assets": [{"drug": "...", "mechanism": "...", "nct": "NCT01234567", "sponsor": "..."}]}
   ```

   A refusal lists every violation at once and writes nothing; fix them all and save again (`targets/grounding`
   says what each checks). The three ratings do not point the same way:

   | Rating | `high` means | Reads as |
   |---|---|---|
   | `druggability` | it can be drugged | good |
   | `safety` | a clean safety outlook; the danger goes in `risks[]` | good |
   | `competition` | the field is crowded | bad: it argues against entering, not against the biology |

   `unknown` is for nothing recorded either way, and is not `low`.

6. **Write the dossier file and the target file, and return.**

   ```bash
   plsi targets show --gene <SYMBOL> > <PLSI_HOME>/work/<thread>/target_<gene>.json   # each target, when "which of these"
   ```

   Write `<PLSI_HOME>/work/<thread>/targets_<gene>_<YYYYMMDD>.md` (the gene as a lowercase slug) and any data files
   as `targets/report` (The target file) says: one candidate section built from this dossier and assessment. Return
   one `result` as `targets/report` (Returning) says. Never write into a research topic or a note.

## When the gather came back incomplete

An incomplete gather looks like a thin target in the output; `unread` tells them apart.

1. Read `unread` and `computed.not_read`.
2. Gather once more. A source that answers the second time was transient; one that fails twice is down.
3. If it is still down, decide by what it would have answered, and say which you chose:
   - **ChEMBL, the PDB or UniProt**: `druggability` is `unknown`, not `low`, and the reason goes in `limitations`.
   - **Open Genes**: no aging frame; do not substitute recall.
   - **Pharos**: no development level; the ChEMBL counts answer a different question.
   - **The per-indication drug query**: no stage for this indication; the furthest stage anywhere is not a
     stand-in.
4. Never write a sentence with "no" about a source in `unread`; the only true sentence is that it was not read.
5. `targets brief` carries `sources_unread`; say in the handoff when a brief comes from a degraded gather.

## Rules

- **An absence in a database is not an absence in the world**; the honest wording is "no identified ...", in
  `limitations` or with a source identifier in the same sentence. An unread source is not an absence at all.
- **A phase belongs to an indication.** Report each indication's phase; never carry one across.
- **Sponsor and phase come from the trial record**, verbatim, never from memory or a company's own description.
- **The aging column stays honest**: an animal lifespan result stays animal on the dashboard, in the brief, in the target
  file and in the summary.
- **Identity percentages come from the dossier**, never from memory; the active-site identity is not available and
  is said to be.
- **No probability of success, composite score or confidence number**, and no average of the prioritisation scores.
  Three ratings and a verdict, each with its evidence, and the limitations beside them.
