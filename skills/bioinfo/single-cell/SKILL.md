---
name: single-cell
description: Use as PLSI Bioinformatician on demand, for a single-cell step - quality control, doublets, integration, annotation and marker gating, cell-type composition against frozen limits, and differential expression by pseudobulk, with a feasibility pilot before any rare-population aim.
---

# Single-cell analysis

Craft for one step of `bioinfo/analyze`. Cells from one donor are not independent: every comparison between
conditions is between **donors**, and n is the number of donors.

## Feasibility first

Before an aim about a rare population or a feature the chemistry may not capture, freeze a pilot as its own step,
blind to condition: the expected yield of the population, the call rate of the feature (TCR V genes on 3' data,
for example), and the bar each must reach. A failed pilot ends the aim (`not_supported`, the rule named), and the
plan's fallback applies. Check memory before loading: the two largest samples' peak RAM against what is free; too
large for this computer is a hand-off (`bioinfo/datasets`, Fits this computer).

## Quality control

Per sample, with thresholds frozen as rules (median absolute deviations, not fixed numbers across chemistries):
genes and counts per cell, mitochondrial share, ambient RNA (SoupX or CellBender where raw matrices exist), doublets
(scDblFinder or scrublet). Report cells kept per sample and per condition; a condition losing far more cells than
the other is a finding to report.

## Embeddings

Export the embedding with what colours it (`umap1,umap2,value,group` for a gene's normalised expression split by
condition, or `umap1,umap2,label,group` for cell types) and draw it with
`plsi bio plot umap --file results/<step>_umap.csv --figure figures/<step>.png --title "<GENE> expression"`: zero or
missing expression in grey, one colour bar across the panels. An embedding shows; it never decides a verdict, and
drawing one is not a gated step (`bioinfo/analyze`, A figure on its own).

## Integration and clustering

Integrate across donors or batches (Harmony, scVI) only after QC; check that conditions still separate where
biology says they should and batches do not. Clusters are a tool, not a result.

## Annotation and gating

- **A reference annotator** (CellTypist with a frozen model, or label transfer from a reference atlas) and
  **marker gating** (a population defined by frozen markers and exclusions, such as `TRDC+ TRGC+ CD3D+` and not the
  NK markers) answer different questions; freeze which decides.
- A gate has to be checked against an annotator: the share of gated cells the annotator calls something else. A
  frozen contamination limit is tested with code:

  ```bash
  plsi bio composition --file results/gate_labels.csv --limit "NK cells<=0.25" --limit "gd T cells>=0.05"
  ```

  One row per cell with `label` and `sample`. A broken limit is `limit_exceeded`: a stop rule, which blocks
  `supported` and ends the aim as the plan says.

## Composition between conditions

Cell-type shares per donor, compared between conditions by donor (a compositional method such as scCODA or propeller,
or a rank-sum on per-donor shares), never by pooling cells. Report shares per donor in `files`.

## Virtual knockout

What would change if a gene were knocked out, predicted from a network of wild-type cells of one type:
`bioinfo/virtual-knockout`.

## Differential expression

**Pseudobulk**: sum counts per donor and cell type, then the bulk methods (`bioinfo/bulk`) with donor as the unit.
A cell-level test (Wilcoxon on cells) treats thousands of cells from a few donors as independent and calls almost
everything significant; it may rank markers, never compare conditions.

## On the step page

Cells and donors per condition after QC, the annotator and its model version, the gate and its contamination, the
composition result per donor, the pseudobulk effect sizes, and any flag.
