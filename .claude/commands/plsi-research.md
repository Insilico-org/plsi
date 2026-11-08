---
description: PLSI daily research - one Research Autopilot run on your current topic, within your cap
argument-hint: "[headless]"
---

Run one run of the routine **PLSI research** as `plsi.md` step 11 and `skills/orchestrator/research/SKILL.md`
(Daily research) describe: one `autopilot/run` request to the subagent `plsi-autopilot`, thread `research-<UTC date>`, conducted with `skills/orchestrator/conduct/SKILL.md` and
`claude-code/RUNTIME.md`. Respect the daily cap in research runs from `.plsi/memory.md` (RUNTIME.md, Outside
services): at the cap, do nothing.

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: write the run's short report to
`<PLSI_HOME>/outbox/<UTC date>-research.md`; a "write this up?" offer goes in that file as the question for the next
session.
