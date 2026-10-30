---
name: brief
description: Use as PLSI Visit Prep when the physician has a visit coming with one patient on their panel - the pre-visit brief (what changed, gaps, plan status, questions to cover), drawn by PLSI Visualizer as a clinician brief.
---

# PLSI pre-visit brief

Follow persona.md norms and `shared/team`. Owner: **PLSI Visit Prep**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used. This is the clinician-facing twin of
`orchestrator/physicians` step 2: written for the physician about a patient, not by a patient for a physician.

## When to use

- "I see patient-07 on Thursday", "prepare my visits for tomorrow" (one request per patient), or a patient picked
  from `panel/overview`.

## Steps

1. **Collect** from the toolbelt, never from memory:

   ```bash
   plsi status --instance <label>
   plsi export --instance <label>
   plsi due --instance <label>
   plsi events list --instance <label> --kind intervention
   ```

   The last visit date comes from the request (the physician's or the roster's `last_update`); none: use 6 months.

2. **Write** `<PLSI_HOME>/work/<thread>/brief.md`, newest first, every value with unit and date:
   - **Changed since the last visit:** new results with the change from the previous one; new conditions,
     medications, side effects;
   - **Gaps:** coordinates of the patient's maps with no current value, tests overdue;
   - **Plans:** status exactly as recorded, each prediction (expected, interval, review date) and its score so far;
   - **To cover:** 3-7 questions tied to the above (unexplained changes, overdue tests, plan safety cautions from
     the recorded screening, as written).

3. **Return one `result`**: `brief.md` in `files`, a 3-line summary, the work for Visualizer
   (`visualizer/dashboard`, scope **clinician brief**) and any evidence question for Clinical Evidence
   (`clinev/review`), each naming its skill path.

## Rules

- The brief reports; it never diagnoses, orders or recommends. Item labels and plan status exactly as recorded.
- One patient per brief; labels, never names.
