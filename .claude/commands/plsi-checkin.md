---
description: PLSI weekly check-in - due predictions, mid-plan checks, monthly wearables import
argument-hint: "[headless]"
---

Run the routine **PLSI check-in** exactly as `plsi.md` step 10 describes (starting with `plsi due --all`), conducted
with `skills/orchestrator/conduct/SKILL.md` and `claude-code/RUNTIME.md`. Nothing due and no active plan: stay quiet.

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: follow RUNTIME.md, Routines. Write what you
would tell the user to `<PLSI_HOME>/outbox/<UTC date>-checkin.md` (write nothing when you would stay quiet), and do
nothing that needs the user's consent; put the card you would have shown in that file instead.
