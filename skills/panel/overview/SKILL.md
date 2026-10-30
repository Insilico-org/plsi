---
name: overview
description: Use as PLSI Panel when the physician asks how their patients are doing - across the panel, who is due, out of range, off plan or without new data, ranked for the physician's attention and drawn by PLSI Visualizer.
---

# PLSI panel overview

Follow persona.md norms and `shared/team`. Owner: **PLSI Panel**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- "How are my patients doing?", "who needs attention?", "who is due this month?".
- The physician's weekly check-in (PLSI's routine sends the request when the role is physician).

## Steps

1. **Collect** for every `active` row of `<PLSI_HOME>/work/panel/roster.json` (`panel/roster`):

   ```bash
   plsi due --all
   plsi status --instance <label>
   plsi state show --instance <label> --map <map_id>
   ```

   `due --all` once; per active row `status` once, then `state show` for each map in its `states`; off plan comes
   from `status`'s `plans`. A state not `current`: list it as "needs re-projection" (Data Processor, via PLSI).

2. **Sort** each patient into at most one row, first match wins:
   - **red flag**: a lab-flagged critical value or a `red_flag:` in a recent result; add the `red_flag:` line
     (`orchestrator/urgent`) to your `summary` at once;
   - **due**: predictions or follow-ups due or overdue;
   - **out of range**: a current coordinate outside its reference range;
   - **off plan**: an adopted plan with missing adherence answers, a reported side effect or an overdue review;
   - **quiet**: no new data for 6 months or more;
   - **on track**.

3. **Write** `<PLSI_HOME>/work/<thread>/panel.json`: `{"as_of": "2026-10", "rows": [{"label", "group", "reason",
   "since", "next"}]}`, the reason in clinical terms with value, unit and date, `next` one step ("prepare a visit
   brief", "ask for the repeat lipid panel"). Write each panel into its own thread folder, never into
   `work/panel/`, so that `memoryhole/forget` can find and delete every panel that names a patient.

4. **Return one `result`**: `panel.json` in `files`, the top 10 rows in `summary` (red flags first) and the work for
   Visualizer (`visualizer/dashboard`, scope **panel**). A patient the physician picks goes to `visitprep/brief`.

## Rules

- You report; you never recommend a treatment, diagnose or order. Plan changes go through `clinev/protocol` and
  Nostradamus.
- Labels only, never names; no patient's data in another patient's row.
- Only roster rows are patients; an instance with relation `other` and no row is never collected.
