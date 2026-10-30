---
name: roster
description: Use as PLSI Panel when the physician adds, lists, pauses or closes a patient on their panel, or a patient shared their PLSI data with the physician - keep the roster (one row and one instance per patient) and the status of each.
---

# PLSI patient roster

Follow persona.md norms and `shared/team`. Owner: **PLSI Panel**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used. The user here is a physician; a patient is a person who
chose to send the physician their data.

## When to use

- A patient shared data with the physician (a PLSI export, records, a letter), and PLSI saved it unopened.
- "Who is on my panel?", "add a patient", "pause / close <label>".
- Not for the physician's own health (their `self` instance) or family members.

## Steps

1. **Role and panel.** Only for the physician role; anything else: a `result` "the panel is for the physician role".

   ```bash
   plsi role show
   plsi instances list
   ```

   The panel is `<PLSI_HOME>/work/panel/roster.json` alone, one row per patient (each patient's instance has relation
   `other`, but an `other` instance with no row, such as a friend the physician tracks, is not a patient):
   `{"label": "patient-07", "status": "active|paused|closed", "shared": ["labs", "plans"], "since": "2026-10",
   "last_update": "2026-10"}`. Labels are neutral (`patient-07`), never names, initials or record numbers; the
   physician keeps the link to the person in their own records.

2. **New patient.** Never open the shared files. Put in ONE `question`: the label to use, sex and birth year (or
   none), and the physician's confirmation that the patient agreed to share exactly what was sent. After the
   `answer`, return a `result` with the work for Data Processor (via PLSI): `init` with `--relation other` for the
   new label, then `processor/intake` with the file paths. Add the row once Data Processor's `result` arrives.

3. **Pause, close or remove.** Pause and close change the row only. Deleting a patient's data is Memory Hole's
   (`memoryhole/forget`, through PLSI, on the physician's explicit words); it deletes the patient's instance and the
   panel reports and work files naming the label. Say so in the `result`, and remove the row from `roster.json` only
   once Memory Hole's `result` arrives (relayed by PLSI).

4. **Return one `result`**: the roster (label, status, shared, since, last update, open plans from `plsi status
   --instance <label>`) and what changed.

## Rules

- Patient data enters only from what the patient chose to send; never look for more.
- Never contact a patient (that is `liaison/message`), never record anything yourself, never move data between
  instances. Patient instances are never sent to the Longevity Mothership.
- A handoff about one patient names that patient's instance; a panel-wide one names the physician's own and lists the
  labels in `summary`.
