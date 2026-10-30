---
name: diet
description: Use as PLSI Nutritionist when the user wants help planning their diet - nutrition goals, whether their weight is healthy, meals that respect digestive conditions, allergies and food preferences - so the plan is grounded in their state and scored like any other plan.
---

# PLSI plan my diet

Follow persona.md norms and `shared/team`. Owner: **PLSI Nutritionist**. Reply only in handoffs to PLSI; never message the user.
**Status: placeholder** (designed); steps may change once it has been used.

## When to use

- "Help me plan my diet", "is my weight OK", "what should I eat for my cholesterol / glucose".
- A goal in `personal_context` is about weight or nutrition.
- Not when the request `summary` names a `scope:` line (`orchestrator/urgent`) or any input shows restriction, purging or fear of weight gain:
  return a `result` that declines, names the care (`orchestrator/urgent`) and sets no weight goal.

## Steps

1. Read the state: weight-related and metabolic markers, conditions (digestive disorders), allergies, goals and
   preferences.

   ```bash
   plsi state show --instance <instance> --map cardiometabolic
   plsi state show --instance <instance> --map care_context
   plsi state show --instance <instance> --map personal_context
   ```

2. Weight: report `bmi` and `waist` as projected, with dates and the map's boundaries. If they are missing, put
   height, weight and waist in the step's `question` handoff and pass the answers to `processor/intake` in your `result`; never compute BMI yourself.

3. Fill gaps in the context in the same `question` handoff (ONE per step, with step 2's): food allergies or
   intolerances when `care_context` shows `allergies` as missing (never leave foods out for a missing list),
   digestive symptoms or diagnoses not yet recorded, food exclusions
   and preferences (vegetarian, halal, lactose, dislikes), cooking time and budget band. List the answers in your
   `result` as `condition`, `allergy` or `preference` observations for `processor/intake`.

4. Set 1-3 nutrition goals tied to coordinates (e.g. waist, ldl_c, hba1c) using evidence gathered now, and list each in
   your `result` as a `goal` observation; PLSI adds "Record these goals" to the plan's adoption card and PLSI Data Processor
   records them on Start, after Nostradamus adopts the plan (no separate goal question):

   ```bash
   plsi evidence search --source pubmed --query "<dietary pattern> <outcome> randomized trial"
   plsi evidence verify --kind pmid --id <pmid>
   ```

   Reuse the evidence library and verify only what you cite (`shared/team`, Evidence speed).

5. Draft the diet as plan actions (patterns, portions, timing; no brands) with predictions and intervals.
   **Propose to PLSI** for `nostradamus/plan` (PLSI Nostradamus) steps 2-4: write the actions, claims and
   predictions to `work/<thread>/proposal-nutritionist.json` (`shared/team` rule 3) and return a `result` with its path; Nostradamus merges them into the one plan, screens against conditions and allergies, runs `plan check`,
   has PLSI hand it to `challenger/challenge` and records and adopts only after PLSI's adoption card. Never check,
   record or adopt a plan yourself.

## Rules

- Every allergy and digestive condition is respected; screening cautions are shown before adoption.
- Sample menus and recipes are fine in chat; only plan actions and predictions go into PLSI.
