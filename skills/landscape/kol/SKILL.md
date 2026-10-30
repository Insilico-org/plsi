---
name: kol
description: Use as PLSI Landscape when the researcher wants to know who works on a topic - key opinion leaders and groups ranked from public publication and trial records only, for collaboration or review.
---

# PLSI key opinion leaders

Follow persona.md norms and `shared/team`. Owner: **PLSI Landscape**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- "Who are the leading groups on <topic>?", "possible collaborators or reviewers for <topic>".

## Steps

1. **Collect** authors and investigators from public records only: papers and registered trials on the topic.

   ```bash
   plsi evidence search --source pubmed --query "<topic>" --limit 20
   plsi evidence search --source ctgov --query "<topic>" --limit 20
   ```

2. **Rank** 5-10 people or groups by recent, topic-specific output (papers as first or last author in the last 5
   years, trials as investigator), with their affiliation as published and 2-3 verified identifiers each
   (`plsi evidence verify --kind <pmid|nct> --id <id>`).

3. **Return one `result`** with `<PLSI_HOME>/work/<thread>/kol.md` and the ranking rule in `summary`.

## Rules

- Public professional records only: no contact details, social profiles or private information, and never contact
  anyone. Output counts, not a quality judgement of a person.
