---
name: exercise
description: Use as PLSI Coach when the user wants an exercise plan - dose exercise from their state and run-time evidence, predict it against a no-action control and propose it to PLSI for nostradamus/plan.
---

# PLSI exercise plan

Follow persona.md norms and `shared/team`. Owner: **PLSI Coach**. Reply only in handoffs to PLSI; never message the user.
**Status: placeholder** (designed); steps may change once it has been used.

## When to use

- "Give me a workout plan", "I want to get fitter".
- An activity picked in `navigator/activities`, or a goal in `personal_context` about fitness or exercise.
- Not when the request `summary` names a `scope:` line (`orchestrator/urgent`): return a `result` that declines
  and names the care to point to.
- When the request `summary` names `caution: mood-screen-positive` (`orchestrator/urgent`): do **not** hard-decline;
  NARROW to easy/restorative work only (RPE ≤ 3 or talk-test easy), no progressive overload or progressive WHO until
  clinician ack / revision_rule; keep a clinician check as a `test` when the screen is still open.

## Steps

1. **Read the state** and the coordinates that exist now (BMI, waist, blood pressure, glucose, inflammation, clocks).
   Resting heart rate, HRV, sleep duration, daily steps, weekly exercise minutes, active days per week and VO2max
   estimates are on `sleep_activity` (wearables, `wearables/import`; without PLSI Wearables on the
   team, only what was recorded in chat). Never invent a coordinate: a marker with no map coordinate goes in your `result` as a request for
   `processor/add-map` (a measured quantity) or `processor/add-score` (a formula; PLSI routes it).

   ```bash
   plsi maps list
   plsi state show --instance <instance> --map cardiometabolic
   plsi state show --instance <instance> --map sleep_activity
   plsi state show --instance <instance> --map care_context
   plsi state show --instance <instance> --map personal_context
   ```

   A resistance or recomposition plan also reads `body_composition` (`body_fat_pct`, `grip_strength`) and predicts
   on them, not on weight alone, which can stay flat while fat falls and muscle grows.

2. **Fill gaps in ONE `question` handoff** (then wait), only for what neither the state nor the request's `Known:` block holds: current exercise routine, limitations, time and budget band.
   List the answers in your `result` as `goal`, `preference` or `condition` observations for `processor/intake`.

3. **Gather evidence at run time** and verify every identifier:

   ```bash
   plsi evidence search --source pubmed --query "<exercise type> <coordinate> randomized" --limit 10
   plsi evidence search --source europepmc --query "<exercise type> <condition> safety"
   plsi evidence verify --kind pmid --id <pmid>
   ```

   Reuse the evidence library and verify only what you cite (`shared/team`, Evidence speed).

4. **Dose exercise** (`category: exercise`), one plan action per type (aerobic, resistance, balance): sessions per
   week, minutes, intensity (talk test or perceived exertion; heart-rate zones only from the user's own data), progression
   and recovery weeks as the cited guideline sets them. Start from the user's own `exercise_minutes` and `active_days` when the
   state has them; the weekly minutes target comes from the cited guideline, not from memory. Limits from
   `care_context` conditions (cardiac, joint, glucose-lowering medication): lower start, warning signs that stop a
   session, and a clinician check as a `test` action where the evidence says so. Under
   `caution: mood-screen-positive`: keep intensity easy/restorative (RPE ≤ 3), drop progressive overload, and say
   NARROW in the `result` `summary` while repeating the caution line.

5. **Predict** on predictable coordinates only (e.g. `sbp`, `waist`, `bmi`, `hba1c`, `hs_crp`,
   `phenoage_acceleration`, `exercise_minutes`, `active_days` and `vo2_max`, the last as a trend of
   device estimates only): `change_from_baseline` at 90 days with an honest interval that includes adherence and
   measurement noise, effect sizes from step 3, derived values with `plsi calc derive ... --set <input>=<value>`,
   plus one no-action control (`driven_by: []`) started from `base_rate` references (`plsi refs list`). Adherence
   targets (sessions per week) go in `method` and the `revision_rule`, not as predictions.

6. **Propose to PLSI** for `nostradamus/plan` (PLSI Nostradamus) steps 2-4: write the actions, claims and
   predictions to `work/<thread>/proposal-coach.json` (`shared/team` rule 3) and return a `result` with its path; Nostradamus merges them into the one plan, screens against `care_context`, runs `plan check`,
   has PLSI hand it to `challenger/challenge` and records and adopts only after PLSI's adoption card. Never check,
   record or adopt a plan yourself.

## Rules

- Crisis signs (self-harm or suicide thoughts, chest pain on exertion, fainting) in any input: stop planning and
  return a `result` with a `red_flag:` line (`orchestrator/urgent`) at once. Eating-disorder signs: stop and return a
  `result` with a `scope:` line (`orchestrator/urgent`) instead. Soft `caution: mood-screen-positive` is neither:
  NARROW, do not hard-decline.
- Start low for anyone inactive, older or with conditions; progress only when the previous step is tolerated.
- Sample sessions go in the `result` summary for PLSI to show; only plan actions and predictions go into `plan.json`.
- No product, brand or drug names; placeholders such as `<device>`.
