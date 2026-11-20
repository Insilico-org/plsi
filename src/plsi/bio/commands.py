"""The `plsi bio` command table: the Bioinformatician's checks and calculators, on local files only."""

from __future__ import annotations

from plsi.cmdspec import FILE, A, Cmd, V
from plsi.vocab.bio import FreezeStage, NullModel, PoolModel

DIR = A("--dir", required=True, help="the analysis folder (holds protocol/, scripts/, results/)")
ALPHA = A("--alpha", type=float, help="significance level (default 0.05)")
FIGURE = A("--figure", help="draw the standard figure to this .png (the .svg and .pdf beside it)")

COMMANDS: dict[str, Cmd] = {
    "bio freeze": Cmd("plsi.bio.protocol:freeze",
                      (DIR, A("--stage", choices=V(FreezeStage), help="protocol (default) or discovery")),
                      "hash protocol/ and scripts/ into protocol/MANIFEST.sha256; post the returned hash before "
                      "any held-out data are read", ("plsi bio verify --dir {dir}",)),
    "bio verify": Cmd("plsi.bio.protocol:verify", (DIR,),
                      "recompute the manifest: GATE_FAILED names every frozen file changed, missing or added"),
    "bio step": Cmd("plsi.bio.steps:step", (DIR, FILE),
                    "close one analysis step: short methods, key numbers, the frozen criterion and the verdict, "
                    "checked and written to results/steps/<step>.md (the chat block is in data.chat)"),
    "bio datasets": Cmd("plsi.bio.datasets:datasets", (FILE,),
                        "check the eligibility table (one row per public dataset) before any dataset is opened"),
    "bio pool": Cmd("plsi.bio.pool:pool", (FILE, A("--model", choices=V(PoolModel), help="hksj (default) or dl"), FIGURE),
                    "pool per-study effects (study, effect, se): random effects with tau², I² and the CI"),
    "bio replicate": Cmd("plsi.bio.replicate:replicate",
                         (A("--discovery", required=True, help="gene, effect[, padj] table"),
                          A("--replication", required=True, help="gene, effect[, padj] table"), ALPHA, FIGURE),
                         "discovery genes in an independent set: sign agreement, its binomial p, Spearman"),
    "bio enrich": Cmd("plsi.bio.enrich:enrich",
                      (A("--genes", required=True, help="the gene list, one per line"),
                       A("--sets", required=True, help="pathways or TF regulons as a GMT file"),
                       A("--universe", required=True, help="every gene measured, one per line"),
                       A("--min-size", dest="min_size", type=int), A("--max-size", dest="max_size", type=int),
                       A("--top", type=int), A("--out", help="write every tested set to this CSV"), FIGURE),
                      "over-representation (hypergeometric, BH) of a gene list in pathways or regulons"),
    "bio signature-null": Cmd("plsi.bio.signature:signature_null",
                              (A("--stats", required=True, help="gene, stat[, mean_expr] table"),
                               A("--up", required=True, help="up genes, one per line"),
                               A("--down", help="down genes, one per line"),
                               A("--null", choices=V(NullModel), help="matched (default) or random"),
                               A("--draws", type=int), A("--seed", type=int), FIGURE),
                              "a signature's score against same-size random or expression-matched gene sets; a matched run also gives "
                              "the random p and how the stat tracks mean expression"),
    "bio km": Cmd("plsi.bio.survival:km",
                  (FILE, A("--at", type=float, nargs="+", help="times to read survival at"),
                   A("--reference", help="the reference group for the hazard ratio"),
                   A("--out", help="write the curves as CSV here"), FIGURE),
                  "Kaplan-Meier per group (time, event, group), medians with CIs, the log-rank test, Peto HR"),
    "bio disproportionality": Cmd("plsi.bio.pv:disproportionality",
                                  (FILE, ALPHA, A("--out", help="write every pair to this CSV"),
                                   A("--control", help="the frozen positive control as '<drug>:<event>'"), FIGURE),
                                  "ROR, PRR and chi-square per drug-event pair from deduplicated 2x2 counts"),
    "bio null-check": Cmd("plsi.bio.pv:null_check",
                          (FILE, ALPHA, A("--column", help="the p-value column (default p)"), FIGURE),
                          "is a permuted null calibrated? the share flagged against alpha"),
    "bio composition": Cmd("plsi.bio.cells:composition",
                           (FILE, A("--limit", action="append", help="a frozen limit such as 'NK cells<=0.25'; repeat"),
                            FIGURE),
                           "label shares per cell table, overall and per sample, against frozen limits"),
    "bio plot nes": Cmd("plsi.bio.plot:nes",
                        (FILE, A("--figure", required=True, help="the .png to draw (the .svg and .pdf beside it)"), ALPHA,
                         A("--title")),
                        "signed NES bars from a preranked enrichment table (pathway, nes, padj), e.g. fgsea's output"),
    "bio plot umap": Cmd("plsi.bio.plot:umap",
                         (FILE, A("--figure", required=True, help="the .png to draw (the .svg and .pdf beside it)"),
                          A("--title")),
                         "cells on an embedding (umap1, umap2, value or label[, group]): a gene in viridis, zeros grey"),
    "bio knockout": Cmd("plsi.bio.knockout:knockout",
                        (FILE, A("--gene", required=True, action="append", help="a knocked-out gene; repeat for several"),
                         ALPHA, FIGURE),
                        "a virtual knockout's diffRegulation table (scTenifoldKnk): perturbed genes, up and down, and "
                        "whether the knocked-out gene tops its own list"),
    "bio order-check": Cmd("plsi.bio.cells:order_check", (FILE, FIGURE),
                           "do two pseudotime orderings (columns a, b) of the same cells agree?"),
}
