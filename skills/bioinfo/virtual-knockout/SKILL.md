---
name: virtual-knockout
description: Use as PLSI Bioinformatician on demand, for a virtual knockout step on single-cell data - predict which genes respond when a gene is knocked out, from a gene regulatory network built on wild-type cells (scTenifoldKnk), check that the knockout registers on its own gene, draw the result and say how far a prediction from a network can be read.
---

# Virtual gene knockout (scTenifoldKnk)

Craft for one step of `bioinfo/analyze`, after `bioinfo/single-cell` QC and annotation. A virtual knockout removes
a gene's outgoing edges from a network inferred from wild-type cells and ranks the genes whose position in the
network moves most. It predicts candidates for a real experiment; it never shows what the gene does.

## When it is the question

- Wild-type or control cells only, of **one cell type** (a network mixes nothing else), at least about 500 cells.
- The gene is **detected well** in that cell type (frozen as a share of cells, for example at least 10%): a gene
  that is rarely seen has few edges, and knocking it out moves nothing.
- A real perturbation of the gene (Perturb-seq, a CRISPR or mouse knockout with scRNA-seq) is the stronger answer;
  when one exists, use it, or use it as the check of the prediction.

## Freeze before running

The cell type and cells used, the gene filter, the knocked-out gene(s), the package version, the parameters
(`nc_nNet`, `nc_nCells`, `nc_q`, `td_K`, `ma_method`), the seed, alpha, and what the result would have to show
(for example "at least 20 genes at FDR < 0.05, with a known target of the gene among them").

## Running it

In the folder's R script: `install.packages("scTenifoldKnk")` (2.0.0 or later; the development version from
`cailab-tamu/scTenifoldKnk`), raw counts as genes x cells (`dgCMatrix`), `set.seed()` first.

- Remove mitochondrial and ribosomal genes, or their co-expression modules dominate the network.
- **Memory grows with the square of the gene count** (published: about 0.5 GB at 1,000 genes, 8.6 GB at 5,000).
  Check free memory first (`free -g`) and keep the genes to what fits, the most variable or best detected by a
  frozen rule, with the knocked-out gene kept in. A run that may pass 10 minutes goes under `nohup` with a log.
- Keep `dr_direction = TRUE` for the predicted direction of each response. `transcriptomeWide = TRUE` knocks out
  every gene in turn and costs far more; only when the plan asks for it.

Write `res$diffRegulation` with its gene names to CSV, then check and draw it:

```bash
plsi bio knockout --file results/<step>_dr.csv --gene <GENE> --figure figures/<step>.png
```

It returns the perturbed genes at FDR < 0.05 with how many are predicted up and down, and the knocked-out gene's
own rank. The gene must rank within its own top 5: when it does not, `ko_not_perturbed` blocks `supported`, since a
knockout that does not register on its own gene has nothing to say about the others. The figure shows the top
genes as bars of Z, signed by the predicted direction, with the knocked-out gene marked.

## Reading it

- **What the genes have in common:** over-representation of the perturbed genes (`bioinfo/pathways`,
  `plsi bio enrich`) with the network's genes as the universe, never the genome.
- **A known target as the positive control:** a gene with a verified link to the knocked-out gene (a literature
  source, verified) that the result should include. Missing it is said plainly.
- **Directions are predictions, made separately from the test.** scTenifoldKnk 2.0.0 diffuses the knockout through
  a heat kernel of the wild-type gene-gene correlation matrix (log1p CPM; `dr_directionT = 5`) and takes the sign;
  versions before 2.0.0 have no direction. The FDR says whether a gene responds, the direction which way. Its
  authors note the direction mostly follows the dominant wild-type expression program rather than the knocked-out
  gene, varies between cell types and data sets, and can lean down with sequencing depth. Report directions as
  "predicted", never as regulation by the gene. `direction_uniform` (nearly all responders one way) is a caution
  to say in the step, not a block.
- A network from correlation in one cell type cannot tell regulation from co-regulation, or a direct target from a
  downstream one. Say so in the step.

## On the step page

The cell type and cells, the genes kept, the gene's detection rate, the parameters and seed, the knocked-out gene's
rank, the number of perturbed genes (up and down), the top genes, the positive control, the enrichment of the
perturbed genes, and the figure. The bench test this points to is the real knockout of the gene in that cell type,
with the predicted genes measured.
