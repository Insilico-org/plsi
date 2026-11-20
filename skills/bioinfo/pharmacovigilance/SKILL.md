---
name: pharmacovigilance
description: Use as PLSI Bioinformatician on demand, for a drug-safety reports step (FAERS and the like) - deduplicate the reports, map drugs to ingredients and targets, count drug-event pairs, compute disproportionality, and check the permutation null and the positive control before any signal is read.
---

# Spontaneous reports: deduplication, disproportionality, nulls

Craft for one step of `bioinfo/analyze`. Spontaneous reports show what is **reported** with a drug, shaped by
publicity, indication, co-medication and who reports. A disproportionality signal is a hypothesis about reporting,
never a rate, a risk or a cause.

## The data

FAERS quarterly ASCII files from the FDA (HTTPS), the quarters frozen. Keep every file's URL, size and date in
`data/meta/sources.csv`. The tables join on `primaryid`; `caseid` names the case across its versions.

## Deduplication

1. Keep only the latest version of each case (the highest `caseversion`, else the latest `fda_dt`, per `caseid`).
2. Drop reports flagged as deleted in the quarterly deletion files.
3. Then collapse remaining duplicates on the frozen key (event date, age, sex, country, drugs and reactions).
Report the counts after each stage.

## Mapping

- **Drugs to ingredients**: the active-ingredient field where present, else the drug name normalised and mapped
  through RxNorm (salts and esters to their parent, combinations to each ingredient). Report coverage (the share of
  drug mentions mapped) and run a second pass on the unmapped names before freezing; unmapped mentions are left
  out and counted.
- **Ingredients to targets** from a frozen resource and version (ChEMBL mechanisms, DrugBank where licensed): an
  ingredient without a target is out of a target-level analysis and counted.
- **Reactions** as MedDRA preferred terms, grouped only by a frozen grouping (an SMQ or a list).
- The role: primary and secondary suspect only, unless the protocol says otherwise.

## Disproportionality

One row per drug-event pair with its 2x2 counts after deduplication (a = the drug with the event, b = the drug with
other events, c = other drugs with the event, d = the rest):

```bash
plsi bio disproportionality --file results/pairs_2x2.csv --out results/pairs_all.csv --figure figures/<step>.png
```

It returns the reporting odds ratio with its 95% interval, the PRR, the chi-square and BH-adjusted p; a pair under 3
reports in the drug-event cell is `sparse_table` and never a signal. A signal is the lower bound above 1 at the
adjusted p. Stratified or adjusted questions (age, sex, the indication) are logistic models in the script, with a
pair that separates perfectly reported as such, not fitted.

## Controls before reading anything

- **A positive control** frozen in advance (named in the inputs' README, or from the literature): a drug-event
  association with an established reporting signal of the kind the question asks about, passed as
  `--control '<drug>:<event>'`. Its ROR is the first result of the step; `control_missed` (it is not a signal) means
  the pipeline is wrong and blocks `supported`.
- **A permutation null** that destroys only what the question is about and keeps the rest. Shuffle the variable of
  interest (an age label, a target assignment) across reports the way the protocol states, rerun the identical
  pipeline, write the null run's p-values to a table (`p` column), and check it:

  ```bash
  plsi bio null-check --file results/null_p.csv
  ```

  A null that flags far more than alpha is `null_misspecified`: the shuffle kept the structure it should remove (a
  shuffle within one drug keeps that drug's background age gradient, for example). Fix the permutation in an
  amendment before reading the real run; a misspecified null blocks `supported`. When the inputs name the
  correct null and the one asked for is broken, say so in the result and ask in `questions` whether to run the
  correct one; never swap it in yourself.
- **Class sharing.** A target-level effect has to beat the effect of sharing a drug class; compare against the
  class with the same null.

## On the step page

The quarters, the counts after each deduplication stage, the mapping coverage, the pairs tested, the positive
control's ratio and interval, the null check, and the signals with their intervals. Every page carries the
reporting caveat in its methods.
