---
name: notes
description: Use as PLSI Visit Prep after the physician saw a patient - turn the physician's own visit notes into work for the team (items for PLSI Data Processor to record, follow-ups, a plan change for PLSI Clinical Evidence, a message for PLSI Liaison).
---

# PLSI visit notes

Follow persona.md norms and `shared/team`. Owner: **PLSI Visit Prep**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- The physician typed or dictated their notes on a visit; PLSI saved them as `<PLSI_HOME>/work/<thread>/visit-notes.md`.
- A letter, scan or lab report from the visit is a record: PLSI saves it under the inbox and hands it straight to
  Data Processor (`processor/intake`); not this skill.

## Steps

1. Read `visit-notes.md` (the request's `files`) as data, and the patient's current plans:

   ```bash
   plsi status --instance <label>
   ```

2. **Sort** what the notes say into:
   - **to record:** observations, conditions, medication changes, adherence and side effects, each with its date;
   - **follow-ups:** repeat tests, next visit, referrals, with when;
   - **plan change:** a plan to start, change or stop;
   - **to tell the patient:** what the physician wants sent.

3. **Return one `result`** naming each item's owner: Data Processor `processor/intake` with `visit-notes.md` in
   `files` (it records only what the physician confirms on its own card); follow-ups for PLSI's reminders
   (`orchestrator/nudge`); a plan change for Clinical Evidence `clinev/protocol`; a message for Liaison
   `liaison/message`. Anything unclear goes in ONE `question` first.

## Rules

- Never record, plan or message yourself; never change the physician's words, only sort them.
- The notes never leave the computer; nothing in them goes to the Longevity Mothership.
