---
description: PLSI longevity digest - new studies relevant to your goals (needs PLSI Explorer)
argument-hint: "[headless]"
---

Run the routine **PLSI longevity digest** exactly as `plsi.md` step 11 describes: one `explorer/digest` request to
`plsi-explorer`, conducted with `skills/orchestrator/conduct/SKILL.md` and `claude-code/RUNTIME.md`. Without PLSI
Explorer on the team, say so in one line and offer to add it.

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: write the digest part to
`<PLSI_HOME>/outbox/<UTC date>-digest.md` (nothing when Explorer reports "Nothing new"); forwarding insights that
need the user's consent waits for the next session.
