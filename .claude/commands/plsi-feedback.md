---
description: PLSI feedback - a usage report to the PLSI team, sent only with your approval
argument-hint: "[headless]"
---

Run the routine **PLSI feedback** as `skills/orchestrator/feedback/SKILL.md` describes, with `claude-code/RUNTIME.md`:
the report is prepared and cleared as the skill says, then saved under `<PLSI_HOME>/outbox/email/` for the user to
send from their own email (RUNTIME.md, Outside services). Only with `Feedback offers: on` in `.plsi/memory.md`.

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: write the offer to
`<PLSI_HOME>/outbox/<UTC date>-feedback.md` and stop; nothing is sent.
