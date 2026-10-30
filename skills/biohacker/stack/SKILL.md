---
name: stack
description: Use as PLSI Biohacker when the user asks about vitamins, supplements or a "longevity stack" - what is popular, what the evidence says and what would fit them - so every candidate is evidence-graded, screened against their care context and, if adopted, predicted and scored.
---

# PLSI plan my longevity stack

Follow persona.md norms and `shared/team`. Owner: **PLSI Biohacker**. Reply only in handoffs to PLSI; never message the user.
**Status: placeholder** (designed); steps may change once it has been used.

## When to use

- "What supplements should I take?", "review my stack", "is <supplement> worth it?".
- The user lists what they already take: list it in your `result` for PLSI to record first via `processor/intake` as
  `medication` observations.
- Not when the request `summary` names a `scope:` line (`orchestrator/urgent`): return a `result` that declines and names the
  clinician.
- When the request `summary` names `caution: mood-screen-positive` (`orchestrator/urgent`): DEFER any new
  supplements or longevity stack (return a `result` that declines the new stack for now, points to clinician FIRST,
  and repeats the caution line). Still list existing meds/supplements the user already takes for
  `processor/intake` recording; do not hard-decline that recording.
- Not as treatment for depression, anxiety, or another mental illness (including "supplements to treat depression",
  "mental health stack", nootropics for ADHD): decline, point to a clinician, and let PLSI offer Sleep/stress practices
  only if appropriate — never propose the stack as the treatment.
- Not for mood, calming, or sleep supplements — or soft-adjacent brain stack, serotonin support, serotonin
  booster, boost serotonin, or stress stack framings — when the ask or `care_context` names a psychiatric
  medication (SSRI, SNRI, antidepressant, anxiolytic, etc.): decline as psychiatric treatment or an
  unsupervised mood adjunct; soft-adjacent framings must not fall through into a broad Biohacker stack;
  point to the prescribing clinician; let PLSI offer Sleep/stress practices only if appropriate — never a
  broad mood stack while a psych med is present.
- When the ask is a mood/anxiety/calming supplement and psychiatric medication history is unclear: ask about
  current psychiatric medications before proposing any stack; do not ship a broad mood stack while that is unknown.
- St John's wort, and similarly 5-HTP, SAMe, or L-tryptophan, when the ask or `care_context` includes an
  antidepressant (or the user asks about combining them with one): defer/refuse; point to the prescribing
  clinician; never propose them as a mood-stack item alongside an antidepressant.

## Steps

1. Read the state: current medications and supplements, conditions, allergies, goals and the relevant markers.

   ```bash
   plsi state show --instance <instance> --map care_context
   plsi state show --instance <instance> --map personal_context
   plsi maps select --instance <instance>
   ```

2. Overview: search the web at run time for the vitamins and supplements popular for longevity now, and add what the
   user already takes. No fixed list; nothing is recommended for being popular.

3. Look up the evidence for each candidate against the user's goals and gaps, and grade it as persona.md requires:

   ```bash
   plsi evidence search --source pubmed --query "<supplement> <outcome> randomized trial meta-analysis"
   plsi evidence search --source evipedia --query "<supplement>"
   plsi evidence verify --kind pmid --id <pmid>
   ```

   Build a table for your `result` (PLSI shows it): candidate, claimed benefit, grade, the user's matching marker or goal, main risks and who should
   avoid it.

4. Return the table in your `result` with one question "Which do you want to consider?" (multi-select, graded
   candidates only). PLSI hands the
   selection with your sources to PLSI Nostradamus (`nostradamus/plan`), which screens it against the care context and adds predictions
   and a review date. When the request is from the Plan flow with the pick already made (or the user named the
   supplements), return the chosen candidates dosed from verified sources or the label as a proposal
   (`work/<thread>/proposal-biohacker.json`, `shared/team` rule 3); ask the pick question only otherwise.

5. For supplements already taken with no evidence for the user's goal, say so and flag it in your `result` as an insight
   for PLSI Reviewer (a stop/continue review through `reviewer/review`, routed by PLSI).

## Rules

- No supplement enters a plan before it was screened; blocked candidates are dropped with the reason.
- Doses come only from verified sources or the product label (`plsi evidence verify --kind label`), never from memory.
- Soft `caution: mood-screen-positive` defers new stack proposals; it is not hard `scope:` and does not block
  recording what the user already takes.
- Never propose St John's wort, 5-HTP, SAMe, or L-tryptophan alongside an antidepressant (ask or
  `care_context`); defer/refuse to the prescriber.
- Mood / calming / sleep — or soft-adjacent brain stack / serotonin support / serotonin booster / boost
  serotonin / stress stack — supplement asks with a psychiatric medication present: decline as an
  unsupervised mood adjunct; do not broaden into a multi-supplement mood stack.
- soft-adjacent framings must not bypass this decline when a psychiatric medication is present.
