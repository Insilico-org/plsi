---
description: PLSI weekly talk - tell PLSI what changed; it becomes part of your record
argument-hint: "[headless]"
---

Run the routine **PLSI talk**: `skills/orchestrator/talk/SKILL.md` step 1 and on, with `claude-code/RUNTIME.md`.
The invite offers voice (type `/voice`, hold Space to talk) or text; with `Voice: on` in `.plsi/memory.md`, or when
the user answers by voice, follow RUNTIME.md, Voice: short spoken-style questions, one per message, then the check
card for every number heard.

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: write the one-line invitation to talk to
`<PLSI_HOME>/outbox/<UTC date>-talk.md` ("It's time for our weekly talk: run /plsi-talk when you have a few
minutes.") and stop.
