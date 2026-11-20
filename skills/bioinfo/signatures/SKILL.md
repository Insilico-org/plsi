---
name: signatures
description: Use as PLSI Bioinformatician on demand, for a signature step - derive a gene signature from discovery and freeze it, score it per sample, query drug-perturbation connectivity (LINCS), and show it beats random and expression-matched gene sets and recovers known positive controls before any score is read as biology.
---

# Signatures and connectivity

Craft for one step of `bioinfo/analyze`. A signature is a hypothesis about a gene set. It earns a biological
reading only when it does better than gene sets that are not the signature, and when it finds what it should.

## Deriving one

From discovery data only, by a rule frozen at the protocol freeze (for example "the top 100 up and 100 down genes by
moderated t at FDR < 0.05"). The derived lists go to `protocol/discovery_frozen.json` and the discovery freeze
before any other set is scored (`bioinfo/analyze`, section 3). An empty signature (no gene passes) is a result:
the step is `not_supported` and the plan's fallback applies; the threshold is never loosened to fill it.

## Scoring per sample

Rank-based scores (singscore, or the mean within-sample rank) travel across platforms better than z-scores;
GSVA/ssGSEA depend on the cohort's composition. Freeze one. Up and down parts are scored separately and combined as
up minus down.

## Beating the null

Every signature result is compared with same-size gene sets drawn from the same table:

```bash
plsi bio signature-null --stats results/de_target.csv --up protocol/sig_up.txt --down protocol/sig_down.txt
plsi bio signature-null --stats results/de_target.csv --up protocol/sig_up.txt --null random --draws 5000
```

`--stats` is one row per gene with `stat` and, for the default expression-matched null, `mean_expr`. Matched draws
take each gene's place from the same expression bin, so a signature of highly expressed genes is not compared with
rarely detected ones. A matched run also returns `random_p` and `stat_tracks_expression` (Spearman of stat with
mean expression): beating random sets but not matched ones, with a stat that tracks expression, is an
expression-level explanation, and the step says so in those words. An empirical p above 0.05 is `null_as_good`:
the score is about the genes' expression level, platform depth or the size of the set, not the signature, and it
blocks `supported`.

## Connectivity (drug-perturbation signatures)

- Query LINCS (SigCom LINCS, or CLUE with access) with the frozen up and down lists; record the library version, the
  cell lines, doses and time points used.
- **Positive controls first.** Freeze, before querying, compounds or perturbations known to act on the signature's
  biology (from the literature, with verified sources) and the rank they must reach. A query that does not
  recover them is not working, whatever else it ranks first.
- **Profiling depth.** Compounds profiled in many cell lines and doses get more signatures and better ranks.
  Compare against random gene sets of the signature's size through the same query (`signature-null` on the query's
  scores, or the tool's own random-set runs), and count-match compounds by the number of signatures they have.
  An AUC that random gene sets also reach is depth, not biology.
- **Sign.** Check the direction convention on one positive control (reverser vs mimicker) before reading any rank.
- Zero-score or tied signatures at the boundary of a call are reported, never broken by hand.

## On the step page

The signature's size and source, the scoring method, the null (kind, draws, seed) with the empirical p, the
positive controls with their ranks, and the depth check. A connectivity result is a list of candidates for a
bench test, never a claim that a compound works.
