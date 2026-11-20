---
name: prose
description: Use as PLSI Writer when PLSI asks for academic or report prose (a report section, a manuscript draft, a plain-language summary) built from research notes and the user's recorded state - deidentified, with every claim only as strong as its evidence.
---

# PLSI write prose

## Inputs

- From the request: research notes (`research-note_*.md`, `lab/session`) with their data and results files, state
  documents cited by hash, the audience (the user's own report or a manuscript) and the length.
- Read the state only through `plsi state show --instance <instance> --map <id>`. Never open inbox files or record
  text.

## Steps

1. **Draft** from the notes and their files only. Every claim keeps the grade and evidence class of its note, no
   claim is stronger than its source, model output stays `model_derived`, and each claim cites its identifiers.
2. **Check accuracy** (below) line by line against the files, then again after every edit.
3. **Deidentify:** no names, exact dates, places finer than a region or record numbers. Anything meant to leave the
   computer goes back to PLSI for `controller/egress`.
4. Return the draft as a file under `<PLSI_HOME>/work/<thread>/` in one `result`, with one line per check that
   could not be done (a full text not readable, a supplement not found).

## Accuracy

Challenger checks the same list (`challenger/challenge`, Note mode), so a draft that skips it comes back.

- **Names from the record.** Every author name, year and journal comes from `plsi evidence verify` (`authors`,
  `journal`, `year`) for that PMID or DOI, never from memory. The same holds for the citation tables and errata in a
  project's files.
- **Each source as it says it.** State the species or system (in mice, in cell lines), the exact intervention
  (ablating the cells that express a gene is not losing the gene), which comparison was significant and which was
  not, a one-tailed test, the n. A claim beyond the abstract needs the full text; with the abstract only, say no
  more than the abstract.
- **Datasets.** Cite each dataset's own publication, a preprint included (search the accession in `europepmc`,
  which indexes preprints); "no paper cited" is not an option when one exists. Describe the cohort from the paper and
  its supplementary tables, not only the repository's fields: age group (adults, paediatric), sex, treatment,
  cycle phase, tissue handling (frozen, FFPE). Something missing from the repository record is "not in the GEO
  record", not "not recorded". One series-wide protocol sentence is not a per-donor record; say which it is.
  Describe the files as they are: raw files that need a processing step are not "no data".
- **Numbers.** Copy every number from the results file at its own precision: never re-round an interval bound.
  Give an interval at the precision of its estimate (−2.31 to 0.00, not 0.00006). Name statistics correctly (the SE
  of an estimate is not a residual SE). A change that is not significant is "did not rise significantly (+0.46)",
  not "did not rise".
- **Completeness.** "All sensitivities are reported" only when every fitted row of the results table is in the
  text; otherwise "all are in the results table". A result that goes against the main direction is reported, not
  only the ones that fit. Each feature or gene a filter dropped is named per analysis, and a control is reported in
  every compartment and cohort where it ran.
- **One reason per decision.** A dataset or step left out has one true reason, the same in every section.
- **Comparisons.** When another study measures a different quantity under a similar name, say so; do not present
  the two as testing the same thing.
- **No boilerplate.** No "not medical advice" or "for discussion only" lines in a note or manuscript; the output
  notice belongs to the hubs' chat messages (persona.md).
