---
name: tf-activity
description: Use as PLSI Bioinformatician on demand, for a transcription factor step - which factors' target genes are enriched in a gene list, or how active a factor is per sample or cell from its regulon, with the confidence levels, the direction of regulation and the checks that keep a factor call honest.
---

# Transcription factor enrichment and activity

Craft for one step of `bioinfo/analyze`. A factor is inferred from its **targets**, never from its own mRNA: many
factors are regulated by phosphorylation, localisation or partners, so their transcript says little about activity.

## Regulons

Freeze one regulon resource with its version: CollecTRI (signed, broad) or DoRothEA restricted to confidence levels
A-C. Signs matter: a target the factor represses counts against activity when it goes up. Keep the regulons on the
same symbol namespace as the data.

## Two questions, two methods

| Question | Method |
|---|---|
| which factors' targets are over-represented in my up (or down) genes? | `plsi bio enrich` with the regulons as a GMT, one set per factor and direction |
| how active is a factor in each sample or cell? | a univariate linear model per factor (decoupler `ulm`) on the expression statistic or the normalised matrix, in the script |

```bash
plsi bio enrich --genes results/up_genes.txt --sets data/meta/collectri_activated.gmt \
  --universe results/universe.txt --min-size 15
```

Write the GMT once from the frozen resource: for a signed resource, one set per factor of its activated targets and
one of its repressed targets, so a set means one direction. At least 15 targets in the universe per factor
(`--min-size 15`); a factor with fewer is not tested.

For activity, score on the differential statistic (t), compare the groups in the step's model, and report the
activity difference with its interval, BH across factors.

## Checks before naming a factor

- **Shared targets.** Factors of one family (the AP-1, NF-κB or E2F members) share targets, so they light up
  together; report the family unless the targets that separate them agree.
- **Proliferation and stress.** E2F, MYC, the interferon factors and the stress factors come up in many contrasts
  through cell cycle, immune infiltration or handling; check the matching gene sets in the same step before reading
  them as specific.
- **Composition.** In tissue, a factor specific to one cell type tracks that cell type's share; in single cell,
  score within one cell type.
- **The factor's own level** is a secondary line on the page, not the evidence.

## On the step page

The resource and version, the confidence levels, the minimum targets, the method, the top factors with their
direction, effect and adjusted p, the factor families named as families, and the checks above with what they
showed. A frozen criterion names the factor or the family before the data were read.
