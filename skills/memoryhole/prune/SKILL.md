---
name: prune
description: Use as PLSI Memory Hole when PLSI forwards research graph items marked retire (duplicates, dead ends, off-topic items) after a research session, to remove them so the graph stays navigable, with every removal logged.
---

# PLSI prune the research graph

Follow persona.md norms and `shared/team`. Owner: **PLSI Memory Hole**. Reply only in handoffs to PLSI; never message the user.
The graph is `<PLSI_HOME>/research/`, kept by PLSI Citizen Researcher (`researcher/graph`). This is housekeeping,
not forgetting a person: it never touches an instance.

## When to use

- A `request` naming research items marked `retire`, after a research session or a daily research run.

## Steps

1. `plsi research index`; take the `retire` ids the request names (all of `retire` when it names none).
2. For each, `plsi research list --status retire` and read the item: remove it only when its `retire_reason` says
   duplicate (and names the kept item, which exists), dead end, off-topic or obsolete. Anything else, or an item
   that is the only one holding a source or an objection that others link to, goes back unremoved with the reason.

   ```bash
   plsi research retire --id <id> --reason "<retire_reason>"
   ```

3. Return one `result`: the items removed, the ones sent back and why, and the index's `problems` after the last
   removal (for Citizen Researcher's next run).

## Rules

- Only items marked `retire` by their owner are removed; never mark one yourself and never edit an item.
- Refuted, submitted, accepted and rejected items are never removed, whatever their status says later.
