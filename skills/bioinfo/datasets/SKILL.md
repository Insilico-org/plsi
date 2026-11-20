---
name: datasets
description: Use as PLSI Bioinformatician on demand, from bioinfo/analyze step 1 - find public datasets for a question, vet each one's labels, comparators, independence and size from its metadata alone, check it fits this computer, and write the eligibility table plsi bio datasets checks.
---

# Finding and vetting public datasets

Craft, read when planning. A README or data dictionary that comes with the inputs is metadata: read it first, and
say which facts came from it. Metadata only: no expression, count or outcome value is opened while a dataset is being
judged. A dataset is chosen for what its metadata say, never for what its data show.

## Where to look

| Kind | Sources |
|---|---|
| bulk expression | GEO (series matrix and supplementary files), ArrayExpress / BioStudies, recount3, ARCHS4 |
| single-cell | CELLxGENE Census, GEO supplementary matrices, the Human Cell Atlas portal, Single Cell Portal |
| cohorts with outcomes | GDC (TCGA, TARGET), cBioPortal, GEO series with survival in the characteristics |
| perturbation signatures | LINCS L1000 (SigCom LINCS, CLUE), CMap |
| drug-safety reports | FAERS quarterly ASCII files (FDA), the openFDA API for counts |
| regulons, gene sets | MSigDB, Reactome, GO, CollecTRI and DoRothEA (through OmniPath) |

Search GEO by blocks as in literature (the disease and its synonyms AND the tissue AND the platform kind), then
read each candidate's series page and its sample characteristics, not its title.

## What each dataset has to show

1. **The labels are written down.** Case and control, stage, phase or treatment from the sample characteristics,
   the paper's supplement or a title pattern you can state; a label you would have to infer is a `hold`.
2. **The comparator is the one the question needs.** Tissue-adjacent controls, diseased-but-unaffected tissue and
   healthy donors answer different questions; name which one, and drop a set whose controls may contain the
   disease (biopsies that can include lesion tissue are not controls).
3. **Counts per group** after the exclusions the protocol will apply (treatment, phase, age, platform subset), not
   the series total. Too few to carry the step's criterion is an `exclude` with that reason.
4. **The origin.** The lab, cohort or consortium the samples come from. Two series from one lab, one cohort or one
   biobank are not independent: discovery and replication need different origins (code refuses a replication
   that shares discovery's origin). Re-deposited or overlapping samples count as the same origin.
5. **The platform and the processing.** Raw counts or CEL files can be reprocessed alike; FPKM-only or
   normalised-only series limit the methods (say which). Note a platform subset (one GPL inside a series).
6. **What the data cannot answer.** No VDJ libraries means no clonotypes; 3' chemistry rarely calls TCR V genes; no
   phase label means no phase correction. Write it as the row's reason when it removes an aim.

## Fits this computer

Before including a large set, check it against the box: free RAM and disk (`free -g`, `df -h`), the download size
(HTTP `HEAD`), and the peak memory of loading its two largest samples. Download over HTTPS. A set that
cannot run here is `hold` with "needs a larger machine"; the `result` says so and offers a frozen script the
operator can run elsewhere, with a dry run on two small samples here.

## The table

`data/meta/eligibility.csv`, one row per dataset considered, kept or not:

```
accession,role,decision,origin,n_case,n_control,labels,platform,reason
```

`role`: `discovery`, `replication`, `exploratory` or `feasibility`; `decision`: `include`, `exclude` or `hold`;
`labels`: where the labels are written; `reason`: why, for every row. Then:

```bash
plsi bio datasets --file data/meta/eligibility.csv
```

It refuses an included row without its counts, labels, origin or platform, a replication set from discovery's
origin, and a table with no discovery set; it lists the holds. Every download goes in `data/meta/sources.csv` (URL,
size, checksum or integrity test, date, licence).

## Rules

- Prefer one well-labelled discovery set and two independent replication sets over one large pooled set.
- An exploratory set never decides a verdict; say so in its row.
- A dataset a paper or another bot suggests is added only by this table, before the freeze.
