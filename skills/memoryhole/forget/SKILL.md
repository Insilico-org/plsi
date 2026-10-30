---
name: forget
description: Use as PLSI Memory Hole when PLSI relays the user's request to delete everything recorded about one person (the user or someone they added) for good.
---

# PLSI forget

Follow persona.md norms and `shared/team`. Owner: **PLSI Memory Hole**. Reply only in handoffs to PLSI; never message the user.

## When to use

- A `request` with skill `memoryhole/forget` naming one `instance`: the user wants that person's data gone.
- Withdrawing single items is PLSI Data Processor's (`processor/intake`, correct or retract), via PLSI; never delete
  for a correction.

## Steps

1. Check the instance exists and size what will go: the counts of observations, states, inbox files and work folders
   (from the request). For a patient (physician role: a row of `<PLSI_HOME>/work/panel/roster.json`), also count the
   files that name the patient's label outside the patient's instance: the physician's panel reports
   (`<PLSI_HOME>/<physician instance>/reports/*.html` rendered from a `panel.json`), the `panel.json` files and the
   `work/<thread>/` folders (visit briefs, messages) that hold it. Then look for copies outside `<PLSI_HOME>`: every
   bot shares this computer, so search the work areas (`/workspace`, each bot's home folder, `/tmp`; never the PLSI
   repo or another instance) for files that hold its subject id (`s_…`; the label too when it is not a common word
   such as `me`), or are byte copies of its inbox files, and count them by folder. Send ONE `question` to PLSI with the instance, its relation, the counts, the offer of an export, and the exact choice ("Delete everything recorded
   about <instance> for good? It cannot be undone." Export, then delete / Delete / Cancel). Skip this question when
   the request's `answers` already hold a PLSI card's delete question with the user's selection naming this
   instance (setup step 6, or a forget card): that selection is the user's explicit confirmation; go to step 2.

   ```bash
   plsi instances list
   ```

2. If the `answer` asks for an export, export first, outside the instance folder (deletion removes that folder), and
   put the path in `files` of the `result`.

   ```bash
   plsi export --instance <instance> --out <PLSI_HOME>/exports/<instance>
   ```

3. Delete only on the user's explicit words relayed unchanged in `answers`, from the user's answer to PLSI's card
   in the chat; never under a standing approval, never on PLSI's own judgment and never on a voice call relay (a
   `voice:<call>` ask, or words a voice agent passed on): then reply with a `question` that PLSI shows as the card. The command refuses unless `--confirm` repeats the instance name. If the command is
   missing or fails, delete nothing by hand (`shared/team` rule 12): reply with a failed `result`.

   ```bash
   plsi instances delete --instance <instance> --confirm <instance>
   ```

4. Then delete only the inbox files, `work/<thread>/` folders, the copies outside `<PLSI_HOME>` found in step 1
   and, for a patient, the panel reports and `panel.json`
   files counted in the confirmed question, and drop the instance from your memory. Never edit `roster.json` or
   anything inside another instance besides those reports: for a patient, the `result` names the work for Panel
   (`panel/roster`, via PLSI) to remove the row. Send one `result`: files and events removed, the export path if any, and that the
   deletion is final; never delete the export folder.

## Rules

- The confirmation reaches the user only as one PLSI question card: never ask, confirm or show a card in your own
  chat, also not "to be safe"; a doubt goes to PLSI as a `question` handoff.
- One instance per request.
- There is no backup and no undo; say so in the question.
- Only this skill runs `plsi instances delete`.
- Other bots hold only hashes and summaries; PLSI drops the instance from its own memory and tells the bots on the
  team to do the same. Afterwards no bot quotes a value or summary from before the deletion: a summary of a new
  instance comes only from that instance's records.
