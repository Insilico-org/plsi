---
description: PLSI Mothership sync - send your weekly deidentified package (only if you joined)
argument-hint: "[headless]"
---

Run the routine **PLSI Mothership** exactly as `skills/orchestrator/mothership/SKILL.md` step 3 describes, with the
choices recorded in `.plsi/memory.md` (`Mothership:` line), conducted with `skills/orchestrator/conduct/SKILL.md` and
`claude-code/RUNTIME.md`; Data Controller (`plsi-controller`) clears and sends. Not joined: say so in one line.

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: send only what the user's recorded send
mode already approves without asking; anything that needs their approval goes to
`<PLSI_HOME>/outbox/<UTC date>-mothership.md` as the question for the next session.
