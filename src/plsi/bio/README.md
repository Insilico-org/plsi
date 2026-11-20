# plsi.bio

Checks and calculators for the PLSI Bioinformatician (`skills/bioinfo/`). The analysis itself (R, Python,
Bioconductor) runs in each analysis folder's own scripts; `plsi bio` holds the arithmetic a verdict rests on and the
refusals that keep a step honest. Local files in, one JSON envelope out.

| Module | Command | What it does |
|---|---|---|
| `protocol.py` | `bio freeze`, `bio verify` | hash `protocol/` and `scripts/` into `protocol/MANIFEST.sha256`; criteria short enough for a step page; a re-freeze needs an amendment |
| `steps.py` | `bio step` | close an analysis step: short methods, key numbers, frozen criterion, verdict; writes `results/steps/<step>.md` |
| `datasets.py` | `bio datasets` | the eligibility table: complete included rows, one row per accession, independent replication |
| `pool.py` | `bio pool` | random-effects pooling, HKSJ (modified) or DerSimonian-Laird |
| `replicate.py` | `bio replicate` | discovery genes in an independent set: sign agreement, binomial p, Spearman |
| `enrich.py` | `bio enrich` | over-representation in pathways or TF regulons (GMT), BH, set-size bias, the full table |
| `signature.py` | `bio signature-null` | a signature against random or expression-matched same-size gene sets, and how the stat tracks expression |
| `survival.py` | `bio km` | Kaplan-Meier, log-rank, Peto hazard ratio |
| `pv.py` | `bio disproportionality`, `bio null-check` | ROR/PRR from 2x2 counts with the positive control checked; whether a permuted null is calibrated |
| `cells.py` | `bio composition`, `bio order-check` | single-cell label shares against frozen limits; pseudotime order stability |
| `knockout.py` | `bio knockout` | a virtual knockout's result (scTenifoldKnk): perturbed genes up and down, the knocked-out gene's own rank |
| `plot.py` | `bio plot nes`, `bio plot umap` | the standard figure for a script's own result: signed NES bars, a UMAP by gene or cell type |

Every check except freeze, verify, step and datasets takes `--figure <name>.png` and draws its standard plot
(`figures.py`: PNG at 300 dpi, SVG and PDF; matplotlib from the bot's environment); `bio enrich --out` writes every
tested set. A step lists its PNGs in `figures`, and the page shows them.

Shared pieces: `flags.py` (each check's flags, and `BLOCKING`, the flags that stop a step from being recorded as
supported), `tuning.py` (every threshold and cap), `tables.py` (CSV/TSV, gene lists, GMT), `stats.py` (ranks,
correlations, BH). Tail probabilities and quantiles come from `plsi.distributions`; the enums from `plsi.vocab.bio`.
