---
name: roster
description: Use as PLSI Panel when the physician adds, lists, pauses, closes or removes a patient on their panel, or a patient shared their PLSI data with the physician - keep the roster (one row and one instance per patient) and the status of each.
---

# PLSI patient roster

**Status: draft**. The user here is a physician; a patient is a person who
chose to send the physician their data.

## When to use

- A patient shared data with the physician (a PLSI export, records, a letter, mail to the `+patients` address), and
  PLSI saved it unopened.
- "Who is on my panel?", "add a patient", "pause / close / remove <label>".
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
   "last_update": "2026-10"}`, plus `"inbox"` and `"shared_folder"` Drive folder ids once `panel/clinic` set them
   up (`"shared"` stays the list of what the patient shared), `"patient_access"` (`none` until the patient is invited,
   then `shared`) with `"patient_id"` (the invited person's Drive permission id, never their address), and
   `"reviewed"` (the as-of date of the last report the patient received); `plsi clinic` commands write these.
   Labels are neutral (`patient-07`), never names, initials or record numbers: the patient sees theirs in their
   Drive folders. The optional `"handle"` is the physician's own name for the patient, shown to the physician as
   "JD (patient-07)": a first name, initials or nickname, at most 40 characters, never a full name, record number or
   birth date, and never another patient's handle or label (`plsi clinic check` refuses a roster where two
   patients could be confused, ignoring case, spaces and dots). It stays in the roster and the physician's chat:
   never in a Drive folder name, a report, a message,
   a handoff to another bot or anything that leaves.

2. **Whose files.** Never open the shared files. Files or mail with no label yet: ONE `question`, a patient on the
   roster (the labels with handles) or a new one. A roster patient: return a `result` naming the label; PLSI hands
   the files to that patient's ward bot.

3. **New patient.** Put in ONE `question`: the label to use, a handle if the physician wants one (with three random
   two-word suggestions such as "amber fox"), sex and birth year (or none), and the physician's confirmation that
   the patient agreed to share exactly what was sent. After the `answer`, return a `result` with the work for Data
   Processor (via PLSI): `init` with `--relation other` for the new label, in a request that names the physician's
   own instance (`shared/team`, The instance exists first). Add the row once Data Processor's `result`
   arrives, and return the work for PLSI: the file paths for `processor/intake` on the new label (a ward bot is made
   later, on request, `clinic/ward`).

4. **Pause, close or remove.** Pause and close change the row only. Deleting a patient's data is Memory Hole's
   (`memoryhole/forget`, through PLSI, on the physician's explicit words); it deletes the patient's instance and the
   panel reports and work files naming the label. Say so in the `result`, and remove the row from `roster.json` only
   once Memory Hole's `result` arrives (relayed by PLSI); then return the work for PLSI: remove the ward bot,
   if the patient has one (`clinic/ward`).

5. After any change to `roster.json`, when `<PLSI_HOME>/work/clinic-dashboard/dashboard.html` exists, run `plsi
   clinic dashboard` (`panel/clinic` step 6).

6. **Return one `result`**: the roster (label, status, shared, since, last update, open plans from `plsi status
   --instance <label>`) and what changed.

## Rules

- Patient data enters only from what the patient chose to send; never look for more.
- Never contact a patient (that is `liaison/message`), never record anything yourself, never move data between
  instances. Patient instances are never sent to the Longevity Mothership.
- A handoff about one patient names that patient's instance; a panel-wide one names the physician's own and lists the
  labels in `summary`.
