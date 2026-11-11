---
name: grounding
description: Use as PLSI Target Hunter on demand, before writing an assessment or handing a target brief to another bot - what a claim has to carry, what each refusal checks, what a database record can and cannot support, and the claims in this field that are most often wrong.
---

# Grounding a target claim

Craft, read when needed, not on
every run.

In a target report a sentence written from a paper looks the same as one written from memory. These rules keep them
apart; whether a target is worth pursuing stays your judgment.

## Every claim carries an identifier

Written inline in the sentence it supports:

| Form | From |
|---|---|
| `(PMID 12345678)` | `plsi evidence search --source pubmed\|europepmc` |
| `(NCT01234567)` | `plsi evidence search --source ctgov`, or the dossier's asset table |
| a DOI, `10.1234/abcd` | Open Genes rows, Europe PMC |
| a drug label set id (a UUID) | `plsi evidence search --source openfda` |
| a UniProt accession | the dossier's protein block |
| an AlphaFold id, `AF-<accession>-F1` | the structures block, where nothing is crystallised |
| a ChEMBL id, `CHEMBL<n>` | the asset table and the chemistry block |
| a PDB entry, written `PDB <code>` | the structures block |
| an Ensembl gene id, `EFO_<n>`, `MONDO_<n>`, `MGI:<n>`, `rs<n>` | the dossier itself |

This is the closed list: an identifier outside it is not a source and `assess` refuses the claim. A PDB entry needs
the literal `PDB` in front, because a bare four-character code can read as a year. The PMID, NCT, DOI and label ids
are checked against the verification ledger; the rest are carried for provenance and support "the dossier records
X", not "X was shown".

A PMID check confirms the record exists; a DOI check confirms only that the DOI resolves. For a directional or
mechanistic claim, read the abstract (`europepmc --query "EXT_ID:<pmid>"`). Verify before citing; a check holds for
thirty days:

```bash
plsi evidence verify --kind pmid --id <pmid>
plsi evidence verify --kind nct  --id <NCT id>
plsi evidence verify --kind doi  --id <doi>
```

With no identifier, put the claim in `limitations` as a gap instead of asserting it.

## The refusals

`plsi targets assess` returns every violation at once and writes nothing. Refusals 1-4 and 7 carry the rule
`target-refusal-<n>`; 5 and 6 come back as schema errors (`CLOSED_VOCABULARY`).

| | Refused | Because |
|---|---|---|
| 1 | a rationale, risk or strategy with no identifier | prose in the tables reads as a finding |
| 2 | a hand-harvested asset that duplicates one the dossier holds (its trial id is required and checked by 4) | a duplicate makes the field look wider than it is |
| 3 | a superlative with no source in the same sentence | a claim about everything that exists, from a table known to be incomplete |
| 4 | a PMID, NCT, DOI or label id the ledger has not verified in the last thirty days | a well-formed id is not a record |
| 5 | a rating outside `high`, `moderate`, `low`, `unknown`, or a verdict outside `pursue`, `monitor`, `deprioritize` | one closed vocabulary keeps sections comparable |
| 6 | a missing `falsifier` or an empty `limitations` | an assessment with no way to be wrong is a recommendation |
| 7 | a `platform_reads` entry with no billed call to that platform (for PandaOmics, that tool) in the egress ledger in the last thirty days | the platform cannot have been asked |

`target-refusal-3` is checked per sentence, so a citation in a neighbouring sentence does not earn the superlative,
and Markdown emphasis does not hide one ("no *identified*" is "no identified"). It is not checked on `limitations`,
where "no other registry was searched" is the honest sentence. No refusal checks that a
resolving citation is relevant; that is on you.

## What a database record supports

A curated record (an Open Genes lifespan row naming a DOI, an Open Targets safety liability naming a PMID) is a
curation decision, not a sentence from the paper.

- A record supports "the source records X, citing Y", not "X was shown".
- To claim the result, retrieve the source; `europepmc` returns abstracts.
- A finding written from the record alone passes no `text`; its quote stays unverified.

## Claims that are most often wrong

1. **"The knockout is lethal."** A high-throughput knockout screen is a first pass and often wrong for a given gene.
   Never state lethality, or lower a safety rating on it, without a targeted-knockout paper; if the literature says
   viable, report viable and the discordance.
2. **"Essential, therefore unsafe."** DepMap essentiality is about cell lines. Genetic constraint is the human read,
   and it is a bin, not a verdict.
3. **"Well characterised" or "novel".** Use Pharos' level (`Tclin`, `Tchem`, `Tbio`, `Tdark`) and say it is Pharos'
   judgment; when it disagrees with the ChEMBL counts, report both.
4. **"Phase 2."** A phase belongs to an indication. A registered trial with no phase is not phase 1. The sponsor is
   the trial record's lead sponsor, verbatim, never a developer inferred from press or recalled.
5. **"90% identical."** Quote the dossier's computed identities, never recalled ones. They are full-length; the
   active-site identity decides selectivity and is not in these sources. `query_identity` (coverage of the human
   protein) and `target_identity` (coverage of the other) are different numbers.
6. **"There is a pocket."** A tractability bucket is a prediction; a co-crystal is a molecule actually bound. "All
   structures read are apo", "no structure" and "a ligand has been bound" are three claims.
7. **"It is ligandable."** Potency filed against a protein family (`family_target`) is a claim about the family.
8. **"The evidence is thin."** Compare `shown` with `counts`: the curated lists are sampled at gather time. Say
   `n of N`.
9. **"Changing this gene extended lifespan."** Check `perturbed`: Open Genes files an experiment under a gene when it
   is in the mechanism, not only when it was changed. Those rows never reach a brief; `with-others` is a double
   mutant.
10. **"There is potent chemistry"** without a direction. IC50, Ki and Kd are inhibition and binding; EC50 is agonism.
    Quote `chemistry.inhibition` or `chemistry.activation`, whichever matches the direction of effect.
11. **"An approved drug exists"** without reading `withdrawn` and `black_boxed`: withdrawals and boxed warnings are
    precedent that argues the other way.
12. **A patent count as current activity.** Pharos' series stops years back (`patent_note`): it answers "has this been
    fought over", not "is anyone filing now".

Behind all of them: **an absence in a database is not an absence in the world**. The honest wording is "no
identified ...", written in `limitations`, or elsewhere only with a source identifier in the same sentence
(`target-refusal-3` refuses it anywhere else).

### Three absences

| What happened | Where it shows | What you may write |
|---|---|---|
| The source answered and holds nothing | `open_questions` | "no identified chemical matter in ChEMBL", a claim about one source, in `limitations` |
| The source did not answer | `unread`, `computed.not_read` | nothing about the target; gather again, or say it was not read |
| The lookup could not run | `computed.not_read`, with the reason | nothing about the target (an RNA gene has no UniProt accession) |

Check this before writing any sentence containing "no".

## Handing a target to the Research Orchestrator

`plsi targets brief --gene <SYMBOL> --question "<question>"` is the only way a dossier reaches it; it writes
nothing into a research topic or a note. Each row hands over the claim, the identifier, the stored record and a
suggested `design` and `species`. Save its output under `<PLSI_HOME>/work/<thread>/` and say, when passing it on:

- it is a **database record, not a quote**; the receiving bot retrieves any source it wants to quote;
- a residue number is UniProt's or a deposited structure's annotation, never recalled;
- `design` and `species` are suggestions from the record's shape, to be checked against the retrieved source;
- an animal result stays `species: animal`: it may refute a hypothesis about people, never support one.

It goes to PLSI as a file, and PLSI decides whether it reaches another bot.
