---
description: PLSI home dashboard - everything at a glance (attention, your health, people, plans, team, routines)
argument-hint: "[open]"
---

Build PLSI's home dashboard: `python claude-code/home.py` (with `--open` when the arguments say `open`: $ARGUMENTS).
It is read-only: it changes nothing and needs no consent.

Then, in a few lines: the items of `attention` from its JSON output (or "All clear"), and the file to open, as the
`path` it printed (`open <path>` on macOS, `xdg-open <path>` on Linux, `start <path>` on Windows). When a blood-test
age or another score from the dashboard is mentioned in the reply, add persona.md's output notice beneath it.

For a deeper dashboard on one topic (state now, a plan review, a forecast, the life arrow), the Visualizer builds it
(`visualizer/dashboard`), as `shared/team` describes; offer that when the user asks about one area.
