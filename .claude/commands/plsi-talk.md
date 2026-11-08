---
description: PLSI weekly talk - tell PLSI what changed; it becomes part of your record
argument-hint: "[headless]"
---

Run the routine **PLSI talk**: `skills/orchestrator/talk/SKILL.md` step 1 and on, in chat (no voice), with
`claude-code/RUNTIME.md`.

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: write the one-line invitation to talk to
`<PLSI_HOME>/outbox/<UTC date>-talk.md` ("It's time for our weekly talk: run /plsi-talk when you have a few
minutes.") and stop.
