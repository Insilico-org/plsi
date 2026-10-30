---
name: graph
description: Use as PLSI Citizen Researcher to keep the user's research graph navigable - after every research session and daily research run, and when PLSI asks what the research holds - by cataloguing projects, writing and linking items, indexing, merging duplicates and marking dead items for PLSI Memory Hole to remove.
---

# PLSI research graph

Follow persona.md norms and `shared/team`. Owner: **PLSI Citizen Researcher**. Reply only in handoffs to PLSI; never message the user.
The graph is `<PLSI_HOME>/research/`: one folder per project, one Markdown file per item, `[[id]]` links between
them. It is the memory of the research: read it before every dig, so no question is asked twice and no refuted idea
comes back. It opens as an Obsidian vault as it is. `plsi research index` checks it and writes `index.md`.

## When to use

- The end of every `researcher/research` session (daily or asked): file what it found.
- PLSI asks what the research holds, or what is ready, open or stuck.
- The start of a daily run: pick what to work on.

## Items

`<PLSI_HOME>/research/<project>/<id>.md`; the id is the file name, lowercase with dashes, unique in the whole graph
(prefix by kind: `q-`, `h-`, `e-`, `n-`; the project page's id is the project's folder name):

```markdown
---
kind: hypothesis        # project | question | hypothesis | evidence | note
title: Low-dose <compound class> improves deep sleep in older adults
status: active          # open | active | parked | supported | refuted | ready | submitted | accepted | rejected | retire
grade: Low              # persona.md grade, for hypothesis, evidence and note
evidence_class: hypothesis_only
sources: [{kind: pmid, id: '<id>'}]
updated: <YYYY-MM-DD>
---
Answers [[q-deep-sleep]]. Supported by [[e-trial-a]]; against [[e-cohort-b]]. Falsified by: <result>.
```

- **project** (one per folder): the question in one line, why it matters to the user in generic words ("a condition
  in the family", never their records), what "done" looks like, and links to its main questions and hypotheses.
- **question**: one open question, linked to the hypotheses that answer it.
- **hypothesis**: one claim, linked to its evidence for and against; the falsifier in the body.
- **evidence**: one source read (identifier verified with `plsi evidence verify`), what it shows in 1-3 lines, and
  which hypotheses it supports or contradicts (`Supports [[h-..]]`, `Against [[h-..]]`).
- **note**: a research note in the `researcher/research` step 5 shape; the unit PLSI Challenger evaluates and the
  Mothership receives. It links to the hypothesis it states.

## Steps

1. **Read.** `plsi research index`, then `plsi research list --project <project>` for the project you work on. Read
   the project page and the items you will touch.

2. **File** what the session found: new items, or edits to existing ones (a new source on an existing hypothesis is
   an evidence item and a link, not a second hypothesis). Set `updated` on every item you change. Status moves with
   the evidence: `supported` or `refuted` only from verified sources; `parked` names in its body what it waits for.

3. **Link.** Every item links to at least one other; every evidence item to the hypotheses it bears on; the project
   page to its live questions and hypotheses. Use `[[id]]` or `[[id|words]]`.

4. **Clean up** with the index's `problems`:
   - `broken_link`: fix the id or remove the link;
   - `orphan`: link it where it belongs, or mark it `retire`;
   - `bad_frontmatter`, `bad_item`, `no_project_page`: fix the file;
   - two items saying the same thing: keep the better one, move its links over, mark the other `retire` with
     `retire_reason: duplicate of <id>`;
   - `stale` (open or active, no update in 30 days): `parked` with what it waits for, or `retire` with
     `retire_reason: dead end` or `off-topic`.
   Never delete a file yourself: PLSI has PLSI Memory Hole remove the `retire` items (`memoryhole/prune`). Refuted,
   submitted, accepted and rejected items are kept; they are the record of what was tried.

5. **Ready.** A note item is `ready` when it has a claim, a grade with its evidence class, at least one verified
   identifier, Against filled (or "none found" with the queries), Risks, a falsifier and a next step, and nothing
   about the user. PLSI sends `ready` notes to PLSI Challenger (Note mode). Objections that come back go into the
   note's body under `## Objections`, with status `active` until they are answered.

6. Run `plsi research index` again until `problems` is empty, and return one `result`: in `summary` the items made,
   changed and marked retire, the `ready` notes, and the next item to work on (the project's most open question or
   least-tested hypothesis), so the next daily run starts there.

## Rules

- Titles say what the item claims or asks, in plain words; one claim per hypothesis, one source per evidence item.
- Nothing about the user in any item: no records, values, dates of their life or plans; the project's personal
  reason is a generic line.
- A submitted note is never edited; a follow-up is a new note that links to it.
