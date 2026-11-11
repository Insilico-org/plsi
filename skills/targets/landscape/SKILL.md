---
name: landscape
description: Use as PLSI Target Hunter on demand, from targets/evaluate or targets/discover, when the competitive picture for a target has to be complete - how to find every asset the structured sources missed, the six ways this search goes wrong, and when to stop.
---

# Harvesting the field

Craft, read when needed, not on
every run.

The goal is the complete, on-target, source-grounded list of drugs in development against one gene. There is no fixed
pipeline: loop and pivot until a fresh sweep turns up no new names. A well-studied target can carry fifteen to
twenty-five assets, so a short list usually means the search stopped.

## Why the dossier's asset table is a floor

`plsi targets dossier` grounds every asset Open Targets knows on its trial records. Trials are indexed by drug, not by
gene, and the drug-to-gene bridge comes from curated mechanism annotations that a new asset under a code name does
not have yet. So find the **names** where names live, then ground each name on a trial record.

## Four angles

Cover all four, in whatever order the target calls for.

| Angle | What to run |
|---|---|
| Mechanism class | web search `"<gene> inhibitor"`, `"<gene> agonist"`, `"<gene> degrader"`; read 2-4 recent reviews and pipeline pages, whose tables list the class |
| Sponsor pipeline | each developer's own pipeline page, for sibling and undisclosed assets |
| Indication and target | `"<gene> <lead indication> clinical trial"` |
| Registries beyond ClinicalTrials.gov | EU CTIS, jRCT, ChiCTR, ISRCTN, CTRI, when activity outside the US is likely |

Then ground every name in one call:

```bash
plsi targets trials --gene <SYMBOL> --asset "<name>" --asset "<code name>" --asset "<name>"
plsi evidence verify --kind nct --id <NCT id>    # before any id goes in an assessment
```

Read in what comes back:

- **`stage` per indication** (`by_indication`, `stopped`): an asset can be active in one indication and terminated
  in another.
- **`also_known_as`**: the registry's synonyms for the asset. Search those too; the sweep is not finished until you
  have.
- **`near_misses`**: studies that name the asset without administering it, usually as a comparator. Their phase
  belongs to another drug.
- **`same_drug` and `merge`**: two names for one drug with disjoint trial sets. Take the union and say which name the
  pivotal trials are under.
- **`no_trials`**: not disproof; the asset may be preclinical, outside the US or under another name. That goes in
  `limitations`.

## Six ways it goes wrong

1. **A short gene symbol collides with an acronym** (a clinical scale, an insect sting, an ordinary word). Search by
   drug and class, and discard homonyms by reading titles.
2. **The target arrives as a protein name.** Resolve to the HGNC symbol, then search every form. The dossier keeps
   three lists apart: `identity.search_as` (symbols, for registries), `identity.protein_names` (for the literature)
   and `identity.obsolete_symbols` (for older papers); `disease.also_known_as` does the same for the indication.
   Greek letters are yours to spell out (γ as gamma, δ as delta).
3. **Pathway-adjacent is not the target.** Decide by the drug's own mechanism, never by co-mention. Keep a
   neighbour's asset only labelled with its real target, and never count it as on-target.
4. **A tool compound is not a programme.** A name with no trials and no confirmed developer is dropped; tool
   compounds belong in the dossier's `probes` block.
5. **A mechanism you did not read is a guess.** Confirm each drug's target from a source you saw; with only one vague
   mention, find a second source or keep it as *target unverified*. Phase, status and sponsor come from the trial
   record, verbatim.
6. **Stopping early, then writing a superlative.** With a thin harvest or an unreachable source the sentence is "no
   identified programme (coverage incomplete)", written in `limitations`; anywhere else `assess` refuses it unless
   the same sentence carries a source identifier.

## Before you finish

- All four angles covered, including registries outside the US where the target is active?
- Is the count plausible for a target this studied? If not, harvest again.
- Anything still *target unverified* that a second source could settle?
- What could not be covered: which registries, languages, years?

## Writing it down

Assets found by hand go into the assessment, each with the trial that places it:

```json
{"harvested_assets": [{"drug": "...", "mechanism": "<its real target and action>",
                       "nct": "NCT01234567", "sponsor": "<lead sponsor, verbatim>",
                       "indication": "..."}]}
```

`assess` refuses a trial id the ledger has not verified and an asset the dossier already holds. State the coverage
achieved, and not achieved, in `limitations`.
