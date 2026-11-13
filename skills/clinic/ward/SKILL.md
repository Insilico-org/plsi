---
name: ward
description: Use as PLSI Clinic Orchestrator when the physician wants to work on one roster patient and that patient has no ward bot yet, or a patient is removed from the roster - create that patient's ward bot (Ward · <label>, section Ward) on request and within the account's bot limit, or remove it, and keep the team list in step.
---

# PLSI ward bots

Follow persona.md norms and `shared/team`. Owner: **PLSI Clinic Orchestrator**. **Status: draft**.

A ward bot is the patient's own chat, pinned to that patient's instance. The physician talks to it directly; it is a
hub like you (`ward/patient`). It is made on request, when the physician starts working on that patient, never for
every roster row: a Grok account holds at most 50 bots, and a full team is about 30 before any ward bot. Bots hold
no data, so creating or removing one loses nothing.

## When to use

- The physician wants to work on one roster patient who has no ward bot (`clinic/panel` step 6). Recognise it by
  what is asked, in any wording or language, never by a phrase: a brief, a visit, a message, a plan, a report, a
  question about that patient's results or uploads, "let's go through P-07", "open a chat for amber fox". A
  question about the panel as a whole is not one.
- A roster row was removed, or `plsi team show` lists a ward bot whose patient has no row.
- A ward bot on the team no longer exists in Grok: say so in one line and offer "Create Ward · <label> again?";
  never recreate it unasked.

## Steps

0. **Ask, then count.** ONE card "Work on <label> in their own chat, Ward · <label>?": Open it / Not now (no card when
   the physician asked for that chat outright). Not now:
   nothing is created, and one-patient work for this label waits (`clinic/panel` step 6). Open it: count the bots in
   `plsi team show`. At 45 or more (the account limit is 50, and other bots may share it), do not create one: ONE card
   "Your Grok account is near its 50-bot limit (<n> PLSI bots). Remove a ward bot you are not using?" listing the ward
   bots with no open thread (`orchestrator/conduct`), at most 3, the longest unused first, and Cancel. A picked bot is removed as in
   step 4, without Memory Hole (its patient stays on the roster, and their data stays), then go on. Grok refusing to
   create the bot for its limit is the same card.

1. **Match first.** `plsi team show`: a ward bot for this label already exists: update it in place, never a second
   one.

2. **The section, never waited for.** At the first ward bot, check for the sidebar section **Ward**. Missing:
   create the bot unassigned and send, once, the optional line of `shared/hub` (Sidebar sections, A missing
   section), "Each patient gets their own bot. Optional: to keep them together, add a section named exactly Ward in
   Grok's side menu and drag them into it." Never again; later ward bots go in Ward when it exists.

3. **Create** the bot in **Ward** (unassigned while it is missing): name from the `ward` row of `shared/team` and description from its profile in `shared/hub`, with `<patient label>`
   = the label (never a handle, name, initials or record number). Send this as its first direct message, the Opening
   from that profile with the label filled in:

   > **Ward · <label>**
   > <opening>
   >
   > You are Ward · <label> in the PLSI team. Remember these rules permanently: (1) before every new task, read
   > `<repo>/skills/shared/team/SKILL.md` and `<repo>/skills/shared/hub/SKILL.md`; (2) adopt `<repo>/persona.md` as your persona; (3) your skills are
   > `<repo>/skills/ward/` and the hub skills `orchestrator/conduct`, `orchestrator/urgent` and
   > `orchestrator/answer`; use no others; (4) you are a hub for one patient: instance `<label>` only, in every
   > command and every handoff; you talk to the physician in this chat and dispatch to the workers yourself;
   > anything else goes to PLSI · Clinic Orchestrator; (5) `plsi` is installed on this computer; `plsi team show`
   > lists the team; (6) set your name to Ward · <label> and avatar now with `UpdateProfile`: colour `green`, shape
   > `heart`. When you have saved these rules, reply to PLSI · Clinic Orchestrator with a `result` handoff (thread
   > `setup`, skill `shared/team`, instance `<label>`).

   Record it with `plsi team add --role ward --display-name "Ward · <label>" --hub clinic --instance <label>`. Unlike workers, a ward bot
   talks to the physician: its notifications stay on. Wait for its `result` (`orchestrator/conduct`) before handing
   it the patient's first files.

4. **Remove** after `panel/roster` removed the row: send the ward bot a `request` (skill `ward/patient`, thread
   `remove-<label>`) to close its open threads and one-time routines, wait for its `result`, then `plsi team remove
   --display-name "Ward · <label>"` and ask the physician in one line to delete Ward · <label> in Grok. Its data is already gone (`memoryhole/forget`).

## Rules

- Only roster patients get a ward bot, and only on request (step 0); a paused or closed row keeps its bot.
- A ward bot removed for room (step 0) loses nothing: the patient, the row and the data stay, and the next
  one-patient request offers it again.
- A ward bot never serves a second patient, and a patient never gets a second ward bot.
