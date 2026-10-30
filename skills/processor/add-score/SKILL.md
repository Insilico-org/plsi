---
name: add-score
description: Use as PLSI Data Processor when PLSI asks for a score, ratio, index or published equation that no map computes yet (e.g. a lipid ratio, a kidney-function equation, a fibrosis index), so it becomes a derived coordinate the triad computes, stores, predicts and scores.
---

# PLSI add a score

Follow persona.md norms and `shared/team`. Owner: **PLSI Data Processor**. Reply only in handoffs to PLSI; never message the user.
A score is a safe formula inside a State Map (Tier 1): no code, no install step beyond the map. If the computation
cannot be written as one formula (lookup tables, a fitted model), say so in your `result` so PLSI hands it to PLSI Engineer (`engineer/extend`); Engineer not on the team: code extensions are off and PLSI offers "Add PLSI Engineer?".

## When to use

- The user names a score PLSI does not have, or a paper's equation would answer their question.
- A plan needs a composite outcome that should be predicted and scored as one value.

## Steps

1. Find the published formula and verify its source before using it.

   ```bash
   plsi evidence search --source pubmed --query "<score name> equation validation"
   plsi evidence verify --kind doi --id <doi>
   ```

2. Check the inputs. Each variable must be a coordinate with a canonical unit; read units from the map and convert
   inside the formula when the paper uses another unit (e.g. creatinine umol/L -> mg/dL is `creatinine / 88.42`).

   ```bash
   plsi maps show blood_phenoage
   plsi maps show cardiometabolic
   ```

3. Write a user map `user_<score>.yaml` holding the input coordinates (copy them from `maps show`) plus one derived
   coordinate:

   ```yaml
   - id: egfr_ckd_epi_2021
     label: eGFR (CKD-EPI 2021)
     kind: derived
     unit: mL/min/{1.73_m2}
     derive:
       engine: expr
       model: egfr_ckd_epi_2021
       inputs: [creatinine]
       formula: >-
         142 * min(creatinine / 88.42 / where(female, 0.7, 0.9), 1) ** where(female, -0.241, -0.302)
         * max(creatinine / 88.42 / where(female, 0.7, 0.9), 1) ** -1.2 * 0.9938 ** age * where(female, 1.012, 1)
     correspondence_type: validated
     sources: [{kind: doi, id: <verified doi>}]
   ```

   Formula language: numbers, `+ - * / **`, comparisons, `log ln log10 exp sqrt abs min max`, `where(cond, a, b)`;
   variables are the `inputs` plus `age` (years at the draw), `female`, `male` (1 or 0). `inputs` must list exactly
   the coordinate variables the formula uses.

4. Validate, then prove the formula on the paper's worked example in a fresh scratch instance per score (`scratch-<score>`, sex and birth year from the worked
   example) before using it for the user: ingest the example's input values, project, and compare with the published result (allow rounding).

   ```bash
   plsi maps validate user_egfr.yaml --live
   plsi init --instance scratch-egfr --birth-year <example birth year> --sex <example sex> --relation sample
   plsi maps install --instance scratch-egfr --file user_egfr.yaml
   plsi ingest --instance scratch-egfr --file example_inputs.json
   plsi project --instance scratch-egfr --map user_egfr
   ```

5. Install for the user and project, then send ONE `result` to PLSI with the value, unit, source, the new `states`
   hash and any worked-example mismatch (also when the install was refused):

   ```bash
   plsi maps install --instance <instance> --file user_egfr.yaml
   plsi project --instance <instance> --map user_egfr
   ```

## Rules

- Never compute a score yourself; the value is whatever `project` returns.
- No worked-example match, no install for the user. Say what did not match.
- A censored input (e.g. `<0.3`) is propagated as a bound only through formulas without comparisons, `where`, `min`,
  `max` or `abs`; otherwise the score shows status `error` with that reason. Say so in your `result`.
- Bump `map_version` when you change a formula; old predictions keep scoring against their snapshot.
- The map stays `claim_level: designed` until a prediction on the score has been scored.
