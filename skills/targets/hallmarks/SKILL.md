---
name: hallmarks
description: Use as PLSI Target Hunter when the researcher wants a target, pathway or candidate framed against the hallmarks of aging - which hallmarks it touches, with what evidence, and which aging clocks or biomarkers could show an effect.
---

# PLSI hallmark framing

Follow persona.md norms and `shared/team`. Owner: **PLSI Target Hunter**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- "Which hallmarks does <target> act on?", "frame this candidate for a grant", a candidate from `targets/discover`.

## Steps

1. **Sources.** The hallmarks framework and the gene, compound and clock datasets from the references:

   ```bash
   plsi refs list --kind dataset
   plsi refs list --kind paper
   plsi evidence search --source pubmed --query "<target> <hallmark>" --limit 20
   ```

2. **Map** the target to each hallmark it plausibly touches, with direction, model system (human, animal, cell) and
   the verified identifiers (`plsi evidence verify --kind <pmid|doi> --id <id>`); a link with no direct data is
   `hypothesis_only`.

3. **Readouts.** For each mapped hallmark, the human biomarkers or aging clocks that could show an effect, and what
   change would refute the link.

4. **Return one `result`** with `<PLSI_HOME>/work/<thread>/hallmarks.md` (a table: hallmark, link, direction,
   evidence class, identifiers, readout, falsifier).

## Rules

- No hallmark link stronger than its weakest cited step; animal and cell data stay Low.
