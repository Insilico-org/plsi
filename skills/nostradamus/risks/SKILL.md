---
name: risks
description: Use as PLSI Nostradamus when PLSI asks for the future part of the life arrow or for the user's main health risks - pick the 3-7 events that matter most, each with a window and a sourced absolute risk from risk equations, base-rate tables or cohort papers.
---

# PLSI risks

Follow persona.md norms and `shared/team`. Owner: **PLSI Nostradamus**. Reply only in handoffs to PLSI; never message the user.

## When to use

- PLSI hands over PLSI Data Processor's `processor/history` result for the life arrow (`orchestrator/arrow`).
- The user asks "what are my main risks" or "what is likely ahead for me".

## Steps

1. **Read the state** cited in the request, the care and personal context, and what is already planned:

   ```bash
   plsi state show --instance <instance> --map <map_id>
   plsi state show --instance <instance> --map care_context
   plsi due --instance <instance>
   plsi plan list --instance <instance>
   ```

2. **Pick 3-7 events** from the user's own state, gaps, history (resolved conditions too: `plsi events list
   --instance <instance> --kind condition`) and family history: the ones that are likely within
   the window, or severe and modifiable. No fixed list. Each is an event or diagnosis that can be dated, not a
   process ("harm building", "features building").

3. **Source each probability**, in this order; stop at the first that fits:
   - a risk equation in a published state; if no map has it, put a `processor/add-score` request in your `result`;
   - a `base_rate` table for the person's age, sex, country and period (`plsi refs list`), cited with its year;
   - a verified cohort paper:

     ```bash
     plsi refs list
     plsi evidence search --source pubmed --query "<event> absolute risk <risk factors> cohort"
     plsi evidence verify --kind pmid --id <pmid>
     ```

     Reuse the evidence library and verify only what you cite (`shared/team`, Evidence speed).

   - otherwise no number: a level only, `"basis": "hypothesis_only"`.

   The source must match what is recorded: when symptoms or findings raise the risk (witnessed breathing pauses, a
   raised marker), use a rate for people with those findings, never the general-population rate.

   Risk from an equation or with what-if inputs comes from `plsi calc derive`, never by hand.

4. **Level** each event: `high` (likely within the window, or severe and modifiable), `watch` (raised vs the matching
   group), `info`. Add scheduled re-measurements and recorded plan predictions (step 1) as `info` events.

5. **Return ONE `result`**: per event the window, label, level, probability (or none), basis and link; the top
   modifiable risk named first. With an adopted plan, add `nostradamus/trajectory`'s two courses.

## Rules

- No probability without a source; relative risks are turned into absolute ones only against a cited base rate.
- Name no intervention as a cure; changes of course come only from plans that passed `plsi screen`.
- Rank by what matters to this person, not by how alarming an event sounds.
- A condition whose signs are present now (snoring with witnessed pauses and daytime sleepiness) is a "check now"
  item, not a future event.
- A care step (a visit, a test) carries a time frame from a cited guideline; never a later one.
