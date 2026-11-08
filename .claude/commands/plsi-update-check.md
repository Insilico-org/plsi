---
description: PLSI update check - new releases and persona updates (offers, never updates without your yes)
argument-hint: "[headless]"
---

Run the routine **PLSI update check** exactly as `plsi.md` step 10 describes (the four git/plsi commands, then the
cases), with `claude-code/RUNTIME.md`. Ignore these paths in `git status --porcelain` when deciding whether the
checkout has local changes: `.plsi/`, `.claude/agents/plsi-*.md`, `.claude/settings.local.json`, `.venv/`,
`instances/`. The update itself runs `.venv/bin/python -m pip install -q -e .`, then applies the migration sections,
then `python claude-code/gen_agents.py --sync` so the workers follow the new roster. Then the persona check
(`plsi.md` step 4.2): a changed `plsi-persona` marker is a question "PLSI persona X.Y.Z is available. Adopt it?"; after
"Adopt", update `Persona:` in `.plsi/memory.md` (workers read `persona.md` themselves).

If the arguments contain `headless` ($ARGUMENTS), this is a scheduled run: never update; write the update or persona
offer you would have shown to `<PLSI_HOME>/outbox/<UTC date>-update-check.md`, or nothing when there is none.
