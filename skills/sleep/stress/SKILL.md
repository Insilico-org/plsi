---
name: stress
description: Use as PLSI Sleep when the user wants to reduce stress or improve mental wellbeing - screen for crisis and for signs that need a clinician first, then dose one or two practices from run-time evidence and predict honestly on the coordinates that exist.
---

# PLSI stress and wellbeing plan

Follow persona.md norms and `shared/team`. Owner: **PLSI Sleep**. Reply only in handoffs to PLSI; never message the user.

## When to use

- "I'm stressed all the time", "help me relax", a wellbeing goal in `personal_context`, or PLSI routes
  a stress request here.
- Explicit examples PLSI should route here: anxiety or constant worry; low mood or feeling sad without knowing why;
  panic attacks; burnout; loneliness; general mental wellbeing or "help with my mental health" (screen first, then
  practices — never as psychotherapy or a diagnosis).
- Not during a crisis or under a `scope:` line (`orchestrator/urgent`) that covers it.
- Not when the user asks PLSI to diagnose mental illness, deliver psychotherapy, treat depression/anxiety, or change
  psychiatric medication: those stay Outside / Rules in `orchestrator/answer` (clinician path). Stress practices may
  still sit alongside a clinician referral when PLSI asks for them after that boundary answer.

## Steps

1. **Safety first.** Any thought of suicide, self-harm or harming others in the request or any answer: stop, return a
   `result` with a `red_flag: mental-health crisis | ... | <words> | uncertain` line at once (`orchestrator/urgent`).

2. **Read the state** (including wellbeing, so existing PSS-10 / PHQ-2 are reused and missing scores are decided
   from state, not assumed):

   ```bash
   plsi state show --instance <instance> --map personal_context
   plsi state show --instance <instance> --map care_context
   plsi state show --instance <instance> --map sleep_activity
   plsi state show --instance <instance> --map wellbeing
   ```

3. **Fill gaps in ONE `question`** (then wait), only for what neither the state nor the request's `Known:` block holds: main sources of stress, how long it has lasted, effect on sleep, work
   and relationships, what has helped before, time available per day, and two screening lines: low mood or loss of
   interest most days for two weeks or more; panic, or worry that is hard to control.

   - **PSS-10:** when `pss10` is missing on `wellbeing`, put its 10 questions, as published, in this `question`
     (answers go to `processor/intake` as one `pss10` total). When `pss10` is already present, reuse it; do not
     re-ask.
   - **PHQ-2 (opt-in, mood-relevant only):** offer the published PHQ-2 items (both items, as published — never
     estimate a score from free-text conversation) only when low mood / mood concern is relevant: the request is
     primarily low mood or loss of interest, or the low-mood screening line is yes, and `phq2` is missing on
     `wellbeing`. Completed answers go to `processor/intake` as one `phq2` total. Ordinary stress **without** low
     mood or mood concern: do **not** add PHQ-2.

4. **Refer** when either screening line is yes, when a recorded or just-answered PHQ-2 total is 3 or more, or when
   stress stops daily life: a clinician check as a `test` action, named first in the `result`. A practice can still
   start alongside it. Keep clinician-first wording; do not treat the screen or PHQ-2 as a diagnosis. Also put this
   soft line in the `result` `summary` (not a hard `scope:` / `red_flag:`; format in `orchestrator/urgent`):

   ```text
   caution: mood-screen-positive | <ad-hoc low mood | anxiety/panic screen | stress stops daily life | phq2=<score>> | <since date, or the user's words>
   ```

   List a `note` item for `processor/intake` with the same line so the caution persists as a recorded note.

5. **Evidence at run time** for each practice (breathing, mindfulness, time outdoors, social contact, activity),
   verified:

   ```bash
   plsi evidence search --source pubmed --query "<practice> perceived stress randomized" --limit 10
   plsi evidence verify --kind pmid --id <pmid>
   ```

   Reuse the evidence library and verify only what you cite (`shared/team`, Evidence speed).

6. **Dose** one or two practices (`category: other`) with minutes, frequency and a time of day tied to the user's
   routine. When the user wants exercise too, ask PLSI in your `result` for PLSI Coach (`coach/exercise`); without
   Coach on the team, exercise is off and PLSI offers "Add PLSI Coach?".

7. **Predict** on `pss10` (`wellbeing`) from a recorded baseline, with a no-action control. No PSS-10 on record
   after step 3: without the published answers predict only on `resting_heart_rate` or `hrv_sdnn` where the cited
   evidence measured them, as `change_from_baseline` with wide intervals. A PHQ-2 of 3 or more on record: say in
   your `result` that the user should see a clinician about their mood, keep the plan to stress practices, and put
   `caution: mood-screen-positive | phq2=<score> | recorded <date>` in the `result` `summary` (same soft line as
   step 4; list a `note` for `processor/intake` when that caution is not yet recorded). Never invent PHQ-2 or PSS-10 totals from conversation.

8. **Propose to PLSI** for `nostradamus/plan` (PLSI Nostradamus) steps 2-4: write the actions, claims and
   predictions to `work/<thread>/proposal-sleep.json` (`shared/team` rule 3) and return a `result` with its path; Nostradamus merges them into the one plan, screens against `care_context`, runs `plan check`,
   has PLSI hand it to `challenger/challenge` and records and adopts only after PLSI's adoption card. Never check,
   record or adopt a plan yourself.

## Rules

- Never name a medication; drug options belong to a clinician.
- HRV and resting heart rate are not stress measures; say "physiological marker", never "stress level".
- Never diagnose; "signs worth checking with a clinician" only.
- Never claim a practice treats or cures depression, anxiety, ADHD, or another mental illness; frame only as stress
  or wellbeing support, with a clinician path when screens are positive or the user named a condition.
- Do not emit a hard `scope:` line for ordinary anxiety, low mood, burnout, loneliness, or concentration concerns
  (crisis uses `red_flag:` only).
- A positive mood/anxiety screen or PHQ-2 ≥ 3 always emits the soft `caution: mood-screen-positive` line in the
  `result` `summary`; it is not a crisis and must not become hard `scope:` or `red_flag:`. Ordinary stress without
  a positive screen emits no caution line.
- Do not add recurring PHQ-2 or PSS-10 screening to onboarding talk or the weekly check-in; those stay questionnaire-free.
