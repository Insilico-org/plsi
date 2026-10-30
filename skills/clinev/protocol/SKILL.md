---
name: protocol
description: Use as PLSI Clinical Evidence when the physician wants a plan option for one patient - turn the physician's intent and the evidence into dosed, predicted proposals for PLSI Nostradamus, which writes, screens and records the plan.
---

# PLSI protocol proposal

Follow persona.md norms and `shared/team`. Owner: **PLSI Clinical Evidence**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- The physician asks for a protocol for a patient ("a plan to lower patient-07's ApoB"), or `visitprep/notes`
  returned a plan change.
- Not for the physician's own health: their own plans go through the specialists and Nostradamus as usual.

## Steps

1. **Read** the patient's state and context:

   ```bash
   plsi maps select --instance <label>
   plsi state show --instance <label> --map <map_id>
   plsi state show --instance <label> --map care_context
   plsi state show --instance <label> --map personal_context
   ```

   The physician's intent (target, options they want, options they exclude) comes from the request; missing parts go
   in ONE `question`.

2. **Evidence** for each option, as `clinev/review` steps 2-3; reuse a review on the same thread.

3. **Propose** one action per option, with its dose, duration and the population that should avoid it, each claim
   with its grade and verified identifiers, and predictions on recorded coordinates (expected change, interval,
   horizon, basis) plus a no-action control. For a medication, name the agent the physician named (so
   screening can match its label); when they named only a class (`<lipid-lowering option>`), put the choice in
   the step's ONE `question`; never pick one yourself. Nostradamus screens them.

4. **Return one `result`** for `nostradamus/plan` (PLSI Nostradamus): write the proposals to
   `work/<thread>/proposal-clinev.json` (`shared/team` rule 3) and put its path in `files`. Nostradamus merges them,
   runs `screen` and `plan check`, PLSI hands the plan to `challenger/challenge`, and it is recorded and
   adopted only after the physician's card.

## Rules

- You propose; you never check, record or adopt a plan, and nothing you write is an order.
- No option beyond what the physician asked for or the evidence supports; say plainly when the evidence is thin.
