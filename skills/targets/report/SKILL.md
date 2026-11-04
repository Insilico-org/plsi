---
name: report
description: Use as PLSI Target Hunter when a target evaluation or shortlist is handed over - the dossier file the dashboard is drawn from, the assessment prose, the things a target report must never state, and the target file (an evidence-based report the Longevity Mothership can receive through the research-note route) with its optional data files.
---

# Handing over a target

Follow `persona.md` (repo root) and `shared/team`. Owner: **PLSI Target Hunter**. Read before handing any evaluation
or shortlist to PLSI.

Two things leave this bot: the **dossier file** PLSI Visualizer draws the user's dashboard from, and the **target
file**, a markdown report written by you from the dossier and the assessment, which is also what PLSI may share
with the Longevity Mothership. You never write HTML.

## The dossier file

```bash
plsi targets show --gene <SYMBOL> > <PLSI_HOME>/work/<thread>/target_<gene>.json   # one per target
```

It holds the identity, the computed reads, the unread sources and the assessment, read offline from the stored
dossier; write it after `assess` so the assessment is in it. PLSI has Visualizer render it (`visualizer/dashboard`,
scope target dossier, or target comparison when the question is "which of these"). A comparison ranks nothing; in
your prose say what a candidate is strongest and weakest *at*, with the read that shows it, never "the strongest
candidate". What you add is the assessment prose, checked by the refusals before it is stored.

## Writing the assessment prose

- **`rationale`**: three or four sentences, each with its identifier. Start from the strongest evidence type and
  name it ("genetics, not co-mention"); end on what would most change your mind.
- **`risks[]`**: one row per risk with `evidence` carrying a source and `mitigation` (or `none known`). Rate the
  risk, not the target. Usual rows: on-target toxicity (from expression breadth), selectivity (from the nearest
  paralogue's full-length identity; the active-site identity is not in the dossier), translation (from the
  orthologue identity; below about 70% a mouse result is a weak read) and crowding (from the asset count, a
  floor).
- **`falsifier`**: a result that separates this account from its obvious rival, such as a molecule that engages the
  target fully and changes nothing. "The trial fails" is not a test of the biology.
- **`limitations[]`**: never empty. The dossier's `computed.open_questions` that bear on the verdict, in your
  words, plus what you did not cover (registries, languages, modalities, how far the harvest went).

## Never state

1. A probability of success, a composite score (including an average of the prioritisation scores) or a completion
   percentage: none has a denominator or a shared unit.
2. A ranking across targets or a "best candidate".
3. A superlative ("first-in-class", "the only programme") without a source in the same sentence.
4. A phase without a trial, or a phase carried from one indication to another (`Furthest stage here` and `Furthest
   stage anywhere` are two facts).
5. An identity percentage from memory; quote the computed ones, and say an active-site identity is not available.
6. A score quoted as prose ("expression 0.87") where a sentence saying what it means belongs.
7. An absence from a source in `unread`: the only true sentence is that it was not read.
8. A sample as a total: carry `read of deposited` and `n of N` into the prose.

## The target file

`<PLSI_HOME>/work/<thread>/targets_<topic>_<YYYYMMDD>.md`, written by `targets/discover` (a shortlist) or
`targets/evaluate` (one target, `<topic>` the gene). It is the deliverable as a report built from the dossiers and
the assessments, and it is written so that PLSI Explorer can send it to the Longevity Mothership as the research
note's `report` (`explorer/mothership`), with one note item per candidate Challenger finds `worthy`. Only those
candidates' rows and sections go; Explorer moves every other candidate to `## Dropped` with Challenger's one-line
reason. A dig writes the whole file again.

```markdown
# <the research question>

Method: PLSI Target Hunter, targets/<discover|evaluate>; sources read: <the free sources that answered>;
platforms: <PandaOmics or PandaClaw, model_derived> or none.

| Target | Band | Furthest stage here | Modalities | Co-crystal | Chemical matter | Aging link | Rationale | Falsifier | Next experiment |
|---|---|---|---|---|---|---|---|---|---|

## <SYMBOL> for <indication>

- Question: <the question this candidate answers, one line>
- Kind: target | repurposing | hallmark
- Claim: <one sentence, at most 300 characters, no identifiers>
- Verdict: <pursue|monitor|deprioritize>; druggability <rating>, safety <rating>, competition <rating>; band <band>
- Grade: <High|Medium|Low|Speculative> (<evidence class>)
- Sources: PMID 12345678, NCT01234567, DOI 10.1234/abcd
- Support:
  - PMID 12345678: <what it found, one line>
- Against:
  - NCT01234567: <what it found, one line>
- Risks:
  - <dimension>, <rating>: <evidence> (PMID 12345678); mitigation: <what would be done, or none known>
- Limits:
  - <one gap per line>
- Model output:
  - pandaomics: <what it said, in its own terms>
- Falsified by: <the falsifier>
- Next step: <the cheapest experiment>
- Accessions: UniProt <accession>, PDB <code>, <ChEMBL id>, <Ensembl gene id>, <EFO or MONDO id>

<the rationale, and a paragraph on what the dossier shows: band basis, aging link (species named), structures,
chemistry with its direction, safety, the assets in this indication>

## Dropped

<each candidate dropped and why>

## Not covered

<sources unread, registries, languages and modalities not searched>
```

- One section per finalist; leave out an empty line (no Against found is a Limits line saying what was searched).
  `Model output` only when a platform was asked.
- **Grade** per persona.md: a candidate resting on animal, cell or model data is at most Low; one resting on a
  curated mechanism label or pathway membership alone is Speculative (`hypothesis_only`).
- **Support, Against and Risks** lines each cite one PMID, NCT or DOI, verified (`plsi evidence verify`) and listed
  in `Sources`; those are the only kinds a note item can carry. UniProt, PDB, Ensembl, ChEMBL, EFO, MONDO, MGI, `rs`
  and AlphaFold ids stay in the body and the `Accessions` line.
- **What the gate refuses**, so the file never needs editing before it leaves: any URL except a `doi.org` link
  (a source named like a web address too: write `MyGene`, not `MyGene.info`), an email, a date finer than a year, a run of eight or more digits, spaces, dots or dashes that is not a PMID,
  NCT, DOI, Ensembl id or a decimal range (write `residues 1020 to 1210`, not `1020-1210`; a ChEMBL id over seven
  digits is named by its compound), and anything about a person. Also leave out oracle links, thread and file
  names, PandaOmics run counts and the `gathered` date; those go in the `result`.
- At most 40,000 characters; trim the per-finalist paragraphs before dropping a candidate.

### Data files

Optional, beside the target file in `<PLSI_HOME>/work/<thread>/`, named in lower case with letters, digits, `_` and
`-`, no date, ending `.csv`, `.tsv`, `.md` or `.json` (at most 20 files, 9 MB each). The useful ones:

- `<gene>-brief.csv` from `plsi targets brief --gene <SYMBOL>`: one row per fact with columns `claim`, `source`
  (written `PMID 12345678`, `NCT01234567` or `DOI 10.1234/abcd`), `species` and `design`, plus the `accessions` rows
  with an empty `source`. Leave out the `record` column and every date.
- `<topic>-shortlist.csv`: the shortlist table.

The same refusals apply cell by cell (no URLs, dates, long numbers or formulas). The JSON dossier, the dossier file
and the dashboard never go: they carry dates and links.

## Returning

One `result` with the target file, its data files and every `target_<gene>.json` in `files`; in `summary` the gene and
indication (or the top 3 with their bands), the verdict with its three ratings, the falsifier in one line, what was
not covered, and "PandaOmics runs used: <m> of <n>" or "free sources only". PLSI shows the dashboard and offers Share
(`orchestrator/research`).

When the evaluation bears on a research question a topic or a session is working, say so and save the output of
`plsi targets brief --gene <SYMBOL> --question "<question>"` as `<PLSI_HOME>/work/<thread>/brief_<gene>.json` in
`files`; PLSI decides whether it crosses (`targets/grounding`, Handing a target to the research bots).
