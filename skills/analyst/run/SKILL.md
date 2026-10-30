---
name: run
description: Use as PLSI Cohort Analyst when the researcher picked a hypothesis - preregister it with the Longevity Mothership, run the identical analysis on the data release on this computer, and write the finding, null results included, for PLSI Challenger and PLSI Data Controller.
---

# PLSI preregister, run, report

Follow persona.md norms and `shared/team`. Owner: **PLSI Cohort Analyst**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used. The numbers come only from `plsi mothership analyze`;
the Mother reruns the same spec on the same release and must get the same result.

## When to use

- PLSI relays the researcher's pick from `analyst/hypothesize` (thread and `hypotheses.json` in `files`).
- PLSI relays the preregistration receipt, then Challenger's objections.

## Steps

1. **Preregister.** Check the budget line in the request `summary` ("Cohort Analyst analyses: <m> of <n>, <month>";
   m < n, else a `result` "budget used"). The catalog carries no release version, so fetch the latest release and take only the `version` from the
   command's output (it reports the version and the cell count, not the values):

   ```bash
   plsi mothership release --version latest --out <PLSI_HOME>/work/<thread>/release.json
   ```

   Never open or read `release.json` before the preregistration receipt arrives: the hypothesis and spec were fixed
   without the values, and they stay that way. Write the picked hypothesis, that release version, the spec, the
   outcome, `alpha`, `direction` and `parents` to `<PLSI_HOME>/work/<thread>/prereg-input.json`, then:

   ```bash
   plsi mothership prereg --spec <PLSI_HOME>/work/<thread>/prereg-input.json
   ```

   It writes the gate-checked message (its `data` names the file). Return that file for Data Controller
   (`controller/egress`, kind "preregistration") and stop until PLSI relays the receipt. No receipt, no analysis.

2. **Run** on the preregistered release with the preregistered spec, unchanged (`release.json` from step 1 is
   that release; fetch it again by version only if it is missing):

   ```bash
   plsi mothership release --version <release> --out <PLSI_HOME>/work/<thread>/release.json
   plsi mothership analyze --release <PLSI_HOME>/work/<thread>/release.json --spec <PLSI_HOME>/work/<thread>/spec.json
   ```

   `spec.json` is the preregistration's `analysis`, copied unchanged; save the output as `result.json`.

   `analyze` fails with `TOO_FEW_CELLS` or `DEGENERATE_CELLS`, or a coordinate is missing: return a `result` to PLSI
   with the code and the preregistration id. That is the report; it does not go to Challenger or `finding`, and the
   groups are never widened to make it run.

3. **Challenge.** Save the findings ledger (`plsi mothership findings`) as
   `<PLSI_HOME>/work/<thread>/ledger.json`. Return one `result` with the preregistration message file, `release.json`,
   `spec.json`, `result.json` and `ledger.json` in `files` and the work for Challenger (`challenger/challenge`, Claim mode). Wait for PLSI to relay the objections.

4. **Finding.** Write the summary: the effect with its interval, n, p against the preregistered `alpha` and
   direction, the multiple-testing load, Challenger's objections as written, and the grade "observational,
   self-selected cohort, hypothesis-generating"; no dates, links or id numbers (the gate refuses them). The gate
   reads any run of 8 or more digits and separators as an id number, so round every number in the summary to 2-3
   significant digits ("effect -1.2 (95% CI -2.1 to -0.37), n 46, p 0.012"); the exact numbers travel in the
   finding's numeric `result`. Paraphrase an objection that quotes a long number. A null or
   contrary result is written the same way. The command reruns the preregistered analysis itself, so the
   finding's numbers are the code's:

   ```bash
   plsi mothership finding --prereg <preregistration message file> --release <PLSI_HOME>/work/<thread>/release.json --summary "<summary>"
   ```

   Return the finding file for Data Controller (`controller/egress`, kind "finding"); PLSI shows a `cleared` one on
   one approval card and Data Controller sends it.

## Rules

- One preregistration, one analysis: a changed spec, group or release is a new preregistration.
- Every run is reported, failures and nulls included; never drop or retry an analysis because of its result.
- Never send anything yourself, never edit the release or the result, and never put a person, an instance or the
  contributor code in any file.
