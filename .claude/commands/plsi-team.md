---
description: Add or remove a PLSI specialist, change role, or turn own-health tracking on or off
argument-hint: "add <bot> | remove <bot> | role <individual|physician|researcher> | own health on|off"
---

Change the PLSI team: $ARGUMENTS

Follow the section "Add or remove a specialist or a section" at the end of `plsi.md`, with `claude-code/RUNTIME.md`:
adding or removing a bot is `python claude-code/gen_agents.py --add|--remove <role>` plus the **Team** list in
`.plsi/memory.md` (role slugs and Display names are in `skills/shared/team/SKILL.md`; `gen_agents.py --list` shows
what is installed). An added bot loads after a restart or `/agents`. Routines that follow a bot (digest with
Explorer, the monthly import with Wearables) are enabled or disabled with `claude-code/routines.sh`.
