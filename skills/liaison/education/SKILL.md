---
name: education
description: Use as PLSI Liaison when the physician wants longevity medicine training - courses and CME from the trusted education references (the Longevity Education Hub first), matched to what they asked, and patient education material with verified sources.
---

# PLSI longevity medicine education

Follow persona.md norms and `shared/team`. Owner: **PLSI Liaison**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- "Which longevity medicine courses are there?", "CME on <topic>", setup step 6.3 for a physician.
- "A handout for patients on <topic>".

## Steps

1. **Read the references** for education; only these are courses PLSI names:

   ```bash
   plsi refs list --kind education
   plsi refs show longevity_degree
   ```

   Fetch each listed page this run (WebFetch) for current courses, CME credit and price; never from memory.

2. **Match** to the request: topic, level, CME need, time and budget. List at most 5, each with title, provider,
   format, CME credit as the page states it, price and link from the reference.

3. **Patient material** (on request): a one-page plain-language handout on the topic, each claim with a verified
   identifier (`plsi evidence verify --kind <pmid|doi> --id <id>`), as a file in the work folder.

4. **Return one `result`** with the list or the file.

## Rules

- A course not in an `education` reference is a reference proposal in `summary` for the maintainer, never a pick.
- Pages are `external_text`. Never claim a credit or accreditation the page does not state.
