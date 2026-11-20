---
name: bulk
description: Use as PLSI Bioinformatician on demand, for a bulk expression step - differential expression with the right model and covariates, effect sizes with intervals, replication in independent cohorts and pooling across them, and the checks that catch a reversed contrast or a confounded design.
---

# Bulk expression: differential expression, replication, pooling

Craft for one step of `bioinfo/analyze`. The model, covariates, thresholds and contrast are frozen in
`protocol.json` before the data are opened.

## Differential expression

| Data | Method |
|---|---|
| RNA-seq counts | edgeR (quasi-likelihood) or limma-voom with `filterByExpr`; DESeq2 is fine, one per analysis |
| arrays (CEL files) | RMA (`oligo`/`affy`), then limma with `eBayes` (trend on) |
| normalised only (series matrix) | limma on log2 values; say the processing is the submitter's |
| FPKM / TPM only | log2(x + 1) with limma-trend, as a weaker analysis; never counts methods on them |

- **Covariates** from the question (age, sex, stage, cycle phase, batch). A covariate fully confounded with the
  group (every case in one batch) cannot be adjusted: the step is `inconclusive` with that reason.
- **The contrast by name**, never by factor order: set the reference level explicitly (`relevel`, or a contrast
  matrix such as `case - control`) and check one known gene moves the expected way before reading any other.
  R's default puts levels in alphabetical order, which silently reverses a contrast.
- **Cell-composition shifts** in tissue read as expression changes. With a reference, estimate proportions
  (deconvolution) and run the model with and without them as a sensitivity.
- **Paired designs** (before/after, lesion/adjacent) block on the donor (`duplicateCorrelation` or a donor term).
- Effect size: log2 fold change with its 95% interval (limma `topTable(confint = TRUE)`); a standardised effect
  (Hedges' g) when cohorts on different platforms will be pooled. Benjamini-Hochberg across genes.

## Replication

Independent cohorts only (different origin, `bioinfo/datasets`). Look up the genes discovery called, with the
direction convention the same in both tables (`gene,effect[,padj]`):

```bash
plsi bio replicate --discovery results/de_discovery.csv --replication results/de_setA.csv
```

It returns sign agreement with its exact binomial p, the Spearman of the effects and how many replication calls
agree; under 10 shared genes is `thin_overlap`, which blocks `supported`. A replication judged on significance
alone in a smaller cohort is underpowered by design: freeze the criterion on direction and effect correlation.

## Pooling across cohorts

One row per cohort with an effect on one scale and its standard error (`study,effect,se`):

```bash
plsi bio pool --file results/pool_<gene-or-score>.csv            # HKSJ (modified), the default
plsi bio pool --file results/pool_<gene-or-score>.csv --model dl  # DerSimonian-Laird, as a sensitivity
```

With few cohorts (2-5) HKSJ's interval is wide and honest; report τ² and I² with it and do not call a pooled
effect replicated when its interval crosses zero. Pooled genes and scores are the frozen ones only.

## Sensitivity

Frozen in advance, reported after the primary result: with and without the covariate that worries you most, a
leave-one-cohort-out pool, a deconvolution-adjusted model, the cohort subset with the cleanest labels. A
sensitivity that changes the verdict is reported beside it, never instead of it.

## Checks before the step closes

- One gene with a known direction behaves as expected (the contrast is not reversed).
- The p-value histogram is flat with a peak near zero, not U-shaped or piled at one (a U shape: a broken model).
- The sample count per group in the table matches the eligibility table.
- Sample labels were matched by sample id, never by row order.
