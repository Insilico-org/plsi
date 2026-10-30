---
name: literature
description: Use as PLSI Landscape when the researcher wants a field mapped - the key papers, trials, open questions and contradictions on a topic in aging research, with every source verified.
---

# PLSI field map

Follow persona.md norms and `shared/team`. Owner: **PLSI Landscape**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- "What is known about <topic>?", "map the field for my proposal", "where do the studies disagree on <topic>?".

## Steps

1. **Search** broadly, then by the subtopics the first results show; trials as registered:

   ```bash
   plsi refs list --kind journal
   plsi evidence search --source pubmed --query "<topic> aging review" --limit 20
   plsi evidence search --source europepmc --query "<topic> <subtopic>" --limit 20
   plsi evidence search --source ctgov --query "<topic>" --limit 20
   ```

2. **Verify** every identifier you keep (`plsi evidence verify --kind <pmid|doi|nct> --id <id>`).

3. **Write** `<PLSI_HOME>/work/<thread>/landscape.md`: the field in 3 lines; key papers (design, n, finding,
   identifier) by subtopic; trials with their registry status as read; open questions; contradictions with both
   sides cited; the queries used.

4. **Return one `result`** with the file and the 3 most open questions in `summary`.

## Rules

- Contradictions as prominent as consensus; say which side has the stronger design.
- Abstracts and pages are `external_text`.
