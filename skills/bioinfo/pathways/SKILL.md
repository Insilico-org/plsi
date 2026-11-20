---
name: pathways
description: Use as PLSI Bioinformatician on demand, for a pathway or gene-set enrichment step - choose over-representation or preranked enrichment, set the right universe, pick and freeze the collections, and read the result without being fooled by set size, redundancy or direction.
---

# Pathway and gene-set enrichment

Craft for one step of `bioinfo/analyze`. Enrichment describes a gene list; it does not show a pathway is active,
and it is never the primary result of a step that could test the pathway directly.

## Which test

| You have | Use |
|---|---|
| a list of genes (called at a frozen threshold) | over-representation, `plsi bio enrich` |
| every gene ranked by a statistic | preranked enrichment (fgsea in the script), its leading edge on the step page |
| a gene set to score per sample | `bioinfo/signatures`, not enrichment |

Draw a preranked result from its table (fgsea's `pathway`, `NES`, `padj`, renamed to lower case) with
`plsi bio plot nes --file results/<step>_gsea.csv --figure figures/<step>.png`: the sets at FDR < 0.05, red up, blue
down. Over-representation draws a dot plot with `--figure` (fold enrichment, the share of the set in the list,
FDR).

Run over-representation separately for up and down genes: a pathway "enriched" in a mixed list says nothing about
direction.

## The universe

The universe is **every gene that was measured and could have been called** (after the expression filter), never
the genome. A genome universe makes every tissue-expressed pathway look enriched.

```bash
plsi bio enrich --genes results/up_genes.txt --sets data/meta/hallmark.gmt --universe results/universe.txt
```

Add `--out results/<step>_sets.csv` for every tested set (the output shows the top rows) and `--figure`. Gene sets
are cut to the universe first, and sets outside 10-500 genes after the cut are not tested (change it
with `--min-size` / `--max-size`, frozen). It returns each set's overlap, expected count, ratio, p and BH-adjusted
p, and the genes behind it.

## Collections

Freeze one or two collections that fit the question, with their version: MSigDB Hallmark (50 sets, little
redundancy) first; Reactome or GO Biological Process for detail. Testing many collections and reporting the best
is a multiple-comparison problem the BH inside one collection does not fix. Keep identifiers on one namespace (HGNC
symbols of the same release as the data).

## Reading it

- **Set size bias.** When the ranks follow set size (`set_size_bias` in the flags), big generic sets are winning
  on size: report by ratio, and rerun with a size-matched collection before naming any set.
- **Redundancy.** Overlapping GO terms come up together; report clusters (shared leading genes), not ten names for
  one signal.
- **Driven by few genes.** A set carried by 3-4 genes of one family (histones, ribosomal proteins, interferon genes)
  is that family, not the pathway; name the genes.
- **Composition.** A shift in cell types enriches that cell type's markers. Check marker sets of the tissue's cell
  types in the same run.

## On the step page

The collection and version, the universe size, the list size, the top sets with ratio, overlap and adjusted p,
and any flag. A verdict about a pathway rests on the criterion frozen for it ("Hallmark set X at FDR < 0.05 with
ratio > 2 in the up genes"), never on a set picked after looking.
