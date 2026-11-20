---
name: survival
description: Use as PLSI Bioinformatician on demand, for a survival step on a public cohort - Kaplan-Meier curves and the log-rank test for groups split by a rule frozen before the outcome was read, Cox models with their assumptions checked, and the traps (optimal cut-points, immortal time, too few events) that make survival results look stronger than they are.
---

# Survival analysis

Craft for one step of `bioinfo/analyze`. Public cohorts with outcomes (TCGA through GDC or cBioPortal, GEO series
with survival in the characteristics) are observational: a survival difference is an association, never an effect
of the gene or score.

## Before the outcome is read

Freeze in `protocol.json`:

- **The endpoint** and its source: overall survival, disease-specific survival or progression-free interval (for
  TCGA, the curated clinical endpoints, which recommend the endpoint per cancer type), the time unit and the
  administrative censoring time.
- **The grouping rule.** A median split, tertiles or a pre-specified clinical cut-point, computed without the
  outcome. **Never the "optimal" cut-point** (maxstat, the best p over all cuts): it inflates the evidence and does
  not replicate. A continuous score is better analysed continuously in Cox.
- **Covariates** for the Cox model (age, stage, sex, the cohort's known prognostic factors) and the cohort
  exclusions.

## Kaplan-Meier and log-rank

One row per patient, `time,event,group` (event 1 = the event, 0 = censored):

```bash
plsi bio km --file results/surv_groups.csv --at 12 36 60 --reference low --out results/km_curves.csv \
  --figure figures/<step>.png
```

It returns per group the n, events, median, survival at the times asked with Greenwood log-log
intervals and the number at risk, the log-rank χ² and p, and for two groups the Peto hazard ratio of the second
group against the reference. A group under 10 events is `few_events`: the comparison is not carried by it, and the
step still reports the hazard ratio with its interval, whose width shows why. The figure draws the curves with the
numbers at risk under the axis; `--out` keeps them as a table.

## Cox models

In the script (R `survival::coxph`, or lifelines): the hazard ratio per unit or per SD of the score with its 95%
interval, adjusted for the frozen covariates. Check proportional hazards (`cox.zph`); when it fails, report a
time-split or a restricted mean survival time instead of one hazard ratio. Keep about 10 events per covariate.

## Traps

- **Immortal time.** A group defined by something that happens after time zero (a later treatment, a second
  sample) gets the survival time before it for free. Define groups at time zero.
- **Many genes, one cohort.** Testing every gene and reporting the best is a discovery step; its hits need a second
  cohort with the same frozen cut rule.
- **Stage and purity.** A score that tracks tumour stage or purity tracks prognosis through them; adjust for both
  before reading it as the score's own.
- **Different endpoints across cohorts** are not pooled as one.

## On the step page

The endpoint, the cohort with its n and events, the grouping rule, the medians and log-rank p, the hazard ratio
with its interval (adjusted and unadjusted), the proportional-hazards check and any flag. Replication in a
second cohort uses the cut rule frozen for discovery, never a new one.
