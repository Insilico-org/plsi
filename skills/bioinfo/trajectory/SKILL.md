---
name: trajectory
description: Use as PLSI Bioinformatician on demand, for a trajectory step on single-cell data - decide whether a continuous process is there to order, infer pseudotime with a frozen root, show the order is stable across roots, seeds and subsamples, and test genes along it without reading an order the data do not support.
---

# Pseudotime and trajectories

Craft for one step of `bioinfo/analyze`, after `bioinfo/single-cell` QC and annotation. Every method returns an
ordering, even of cells that form no process; the step's job is to show this one is real.

## When a trajectory is a question

Only for cells expected to lie on a continuous process (differentiation, activation, a senescence programme, a
cycle), within one lineage. Disconnected clusters, different donors' cells or distinct cell types are not a
trajectory; mixing them gives an order of batch or cell type.

## Freeze before running

- The cells (the lineage and the QC), the method and its parameters, the embedding it runs on.
- **The root**, from biology and markers named in advance (a progenitor marker, the untreated state), never chosen
  after seeing the curve.
- The genes or programme expected to change along it, with their direction: the positive control.

| Method | Use |
|---|---|
| diffusion pseudotime (scanpy `dpt`) | one path from a root |
| Slingshot | branching lineages on a clustered embedding |
| Monocle 3 | graphs with branches and loops |
| RNA velocity (scVelo) | direction from spliced/unspliced counts; often unreliable in mature or slowly changing cells, so a supporting line, never the order |

## Is the order stable?

Run the ordering twice with a change that should not matter (a second plausible root, another seed, an 80% subsample
of the cells, a second method), join the two pseudotimes per cell as columns `a` and `b`, and check:

```bash
plsi bio order-check --file results/pseudotime_root2.csv
```

A Spearman under 0.8 is `order_unstable`: the order is not a result, blocks `supported` and is not sent as a file; a strong negative value
means the two runs ran the process in opposite directions (fix the root, then check again). Report every check run,
not the one that agreed.

Draw the ordering on the embedding (`plsi bio plot umap` with pseudotime as `value`) beside the order check's
scatter.

## Genes along pseudotime

Test with a method built for it (tradeSeq `associationTest`, or a GAM per gene), with donor in the model where the
design allows. The positive-control genes have to move the expected way first. Pseudotime is inferred from the same
genes being tested, so a gene "changing along pseudotime" is partly circular: report it as description, with the
frozen positive controls as the check.

## Conditions

Comparing conditions along a trajectory (the distribution of cells along it per condition, condiments' tests)
compares donors, as for composition. A shift in where cells sit is a finding only with every donor's
distribution shown.

## On the step page

The cells and lineage, the method and root, the stability checks with their Spearman values, the positive
controls' behaviour, and the genes or programmes along the order with their effect and adjusted p.
