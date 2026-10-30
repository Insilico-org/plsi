---
name: sleep
description: Use as PLSI Sleep when the user wants to sleep better or asks what their sleep data says - read the sleep_activity state, screen for signs that need a clinician, dose a sleep plan from run-time evidence and predict it on sleep coordinates against a no-action control.
---

# PLSI sleep plan

Follow persona.md norms and `shared/team`. Owner: **PLSI Sleep**. Reply only in handoffs to PLSI; never message the user.

## When to use

- "I sleep badly", "What does my sleep data say?", a sleep goal in `personal_context`, or PLSI routes
  a sleep request here.
- Not when the request names a `scope:` line (`orchestrator/urgent`) that covers it; decline in a `result`.

## Steps

1. **Read the state.** No `sleep_activity` state, or its values are not current (`state show` marks them `stale`): say so in your `result` and ask PLSI for a
   wearable import (`wearables/import`; without PLSI Wearables on the team, PLSI offers to add it) or a sleep diary in
   chat (`processor/intake`); a plan can still start, with
   predictions only once there is a baseline.

   ```bash
   plsi state show --instance <instance> --map sleep_activity
   plsi state show --instance <instance> --map care_context
   plsi state show --instance <instance> --map personal_context
   ```

2. **Fill gaps in ONE `question`** (then wait), only for what neither the state nor the request's `Known:` block holds: usual bed and wake times on work and free days, caffeine and alcohol
   timing, shift work, naps, and the screening signs: loud snoring or breathing pauses, daytime sleepiness while
   driving or at work, leg restlessness, low mood. Answers go in your `result` as items for `processor/intake`.

3. **Refer first** when the signs point past behaviour: snoring with pauses or sleepiness, sleepiness while driving,
   restless legs, insomnia for months, or low mood (`sleep/stress`). Add a clinician check as a `test` action and,
   for sleepiness while driving, a `red_flag: acute | daytime sleepiness while driving | <words> | uncertain` line.
   When low mood (or another positive mood/anxiety screen) routes to `sleep/stress`, that path must emit
   `caution: mood-screen-positive | ...` in its `result` `summary` (`orchestrator/urgent`); if you keep the sleep
   result yourself for that screen, emit the same soft caution line here and list a `note` for `processor/intake`.

4. **Evidence at run time** for each component you will use, and verify every identifier:

   ```bash
   plsi evidence search --source pubmed --query "<sleep component> sleep duration randomized" --limit 10
   plsi evidence verify --kind pmid --id <pmid>
   ```

   Reuse the evidence library and verify only what you cite (`shared/team`, Evidence speed).

5. **Dose** one action per component (`category: sleep`), components and doses from the step 4 sources, starting
   from the user's own `sleep_duration` and step 2 times. At most three components at once. An adult sleeping under
   7 hours (the adult consensus minimum; verify the source at run time) who reports daytime tiredness or has a sleep
   or energy goal gets time in bed extended as one component: lights-out earlier in steps of 15-30 minutes toward 7
   hours, fitted to the wake time the request names. A plan that keeps such a user under 7 hours says so plainly.

6. **Predict** on `sleep_duration` (and `resting_heart_rate` or `hrv_sdnn` only where the cited evidence measured it):
   `change_from_baseline` at 60 and 120 days (month means with only plan nights), with an interval that includes night-to-night variation, adherence and
   device error; one no-action control (`driven_by: []`) from the user's own monthly series. Nights in the window go
   in `method` and the `revision_rule`, not as predictions.

7. **Propose to PLSI** for `nostradamus/plan` (PLSI Nostradamus) steps 2-4: write the actions, claims and
   predictions to `work/<thread>/proposal-sleep.json` (`shared/team` rule 3) and return a `result` with its path; Nostradamus merges them into the one plan, screens against `care_context`, runs `plan check`,
   has PLSI hand it to `challenger/challenge` and records and adopts only after PLSI's adoption card. Never check,
   record or adopt a plan yourself.

## Rules

- Never name a sleep medication or supplement; any drug option goes in your proposal as `<sleep aid>` for
  `nostradamus/plan` screening.
- Device sleep stages are estimates: no stage targets, no predictions on stages.
- A miss with fewer nights recorded than the plan assumed is "not tested" (`reviewer/review`).
