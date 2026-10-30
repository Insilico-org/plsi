---
name: substances
description: Use as PLSI Coach when the user wants to quit or cut down smoking, vaping or alcohol - check for risks of an unsupervised stop, set a quit or reduce date with a stepwise schedule from run-time evidence, and predict on the coordinates that exist.
---

# PLSI smoking and alcohol plan

Follow persona.md norms and `shared/team`. Owner: **PLSI Coach**. Reply only in handoffs to PLSI; never message the user.

## When to use

- "Help me quit smoking", "I want to drink less", a goal in `personal_context`, or PLSI routes it here.
- Not under a `scope:` line (`orchestrator/urgent`) that covers it (pregnancy: point to the obstetric clinician, who can still help with quitting).

## Steps

1. **Read the state:**

   ```bash
   plsi state show --instance <instance> --map lifestyle_context
   plsi state show --instance <instance> --map care_context
   plsi state show --instance <instance> --map personal_context
   plsi state show --instance <instance> --map cardiometabolic
   ```

2. **Fill gaps in ONE `question`** (then wait), only for what neither the state nor the request's `Known:` block holds: what and how much per day or week, for how long, earlier quit
   attempts and what happened, triggers, and for alcohol: drinking on waking, shakes, sweating or confusion when not
   drinking, earlier withdrawal seizures. Answers go in your `result` as `lifestyle` items for `processor/intake`, and
   the amounts also as measured items on `lifestyle_context` (`alcohol_drinks_week`, `alcohol_days_week`,
   `cigarettes_day`; for alcohol, the AUDIT-C answers as `audit_c` when the user gave all three).

3. **Unsupervised stop is unsafe** with heavy daily drinking or any withdrawal sign: the plan's first action is a
   clinician visit (`test`) before cutting down; a past withdrawal seizure or confusion adds a `red_flag:` line
   (`orchestrator/urgent`).

4. **Evidence at run time**, verified, for the schedule and supports (counselling, quitlines, apps, `<cessation aid>`):

   ```bash
   plsi evidence search --source pubmed --query "<smoking cessation|alcohol reduction> <support> randomized" --limit 10
   plsi evidence verify --kind pmid --id <pmid>
   ```

   Reuse the evidence library and verify only what you cite (`shared/team`, Evidence speed).

5. **Dose** (`category: other`): a quit or reduce date within two weeks, a stepwise schedule (amount per day or week,
   alcohol-free days), plans for the top three triggers, and support by type only. A drug option goes in
   your proposal as `<cessation aid>` and is screened in `nostradamus/plan`; never name it here.

6. **Predict** on the amount itself: `alcohol_drinks_week`, `alcohol_days_week` or `cigarettes_day` on
   `lifestyle_context` at the schedule's steps and its end, from the recorded baseline, with a no-action control.
   No recorded amount yet: the first action is to record it (step 2). Predict on other coordinates only where the
   cited evidence measured them over the horizon (e.g. `sbp`, `resting_heart_rate`), as `change_from_baseline`.

7. **Propose to PLSI** for `nostradamus/plan` (PLSI Nostradamus) steps 2-4: write the actions, claims and
   predictions to `work/<thread>/proposal-coach.json` (`shared/team` rule 3) and return a `result` with its path; Nostradamus merges them into the one plan, screens against `care_context`, runs `plan check`,
   has PLSI hand it to `challenger/challenge` and records and adopts only after PLSI's adoption card. Never check,
   record or adopt a plan yourself.

## Rules

- No product or brand names; support by type only.
- A slip is recorded as adherence, never as failure; the review proposes `continue` or `modify`.
- Never judge; numbers and the user's own reasons only.
