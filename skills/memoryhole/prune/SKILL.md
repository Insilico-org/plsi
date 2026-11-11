---
name: prune
description: Use as PLSI Memory Hole when PLSI forwards research notes marked retire (duplicates, dead ends, off-topic) after a research session or a daily run, to remove them, with every removal logged.
---

# PLSI prune research notes

Notes are the files in each project's `notes/` (`<PLSI_HOME>/research/projects/<project>/notes/`), written by
PLSI Research Orchestrator (`lab/session`).
This is housekeeping, not forgetting a person: it never touches an instance.

**Only notes are ever removed.** Questions, hypotheses and findings are never deleted: a direction that dies gets
`status: closed` with a reason and stays. A request to remove one goes back, saying so.

## When to use

- A `request` naming research notes marked `retire`, after a research session or a daily research run.

## Steps

1. ```bash
   plsi research notes --status retire
   ```
   Take the notes the request names (all of `retire` when it names none), by their `name`.

2. Read each note and remove it only when its `retire_reason` says duplicate (and names the kept note, which
   exists), dead end, off-topic or obsolete. Anything else goes back unremoved with the reason.

   ```bash
   plsi research retire --name "<name>" --project <id> --reason "<retire_reason>"
   ```

   It refuses a note that is not marked `retire`. Each removal is logged first in its project's `notes/retired.md`, then the note is removed.

3. Return one `result`: the notes removed, the ones sent back and why.

## Rules

- Only notes marked `retire` by their owner are removed; never mark one yourself and never edit one.
- `submitted`, `accepted` and `rejected` notes are never removed, whatever a later status says.
- Nothing under a topic folder is yours to touch, including `log.jsonl`, which is append-only.
