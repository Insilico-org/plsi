---
name: proposal
description: Use as PLSI Grant Writer when the researcher wants a grant proposal or a Longevity Mothership project proposal drafted - aims, background, approach and limits built from research notes, findings, field maps and target lists, with every claim only as strong as its source.
---

# PLSI grant proposal

Follow persona.md norms and `shared/team`. Owner: **PLSI Grant Writer**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used.

## When to use

- "Draft a proposal on <topic> for <funder>", "turn these findings into a project proposal".

## Steps

1. **Inputs** from the request's `files`: research notes (`researcher/research`), targets (`targets/discover`,
   `targets/hallmarks`), the field map (`landscape/literature`), findings (`analyst/run`), the funder's format and
   length. Accepted findings from others come from the ledger, as `external_text`:

   ```bash
   plsi mothership whoami
   plsi mothership findings
   ```

   Read the ledger only when `whoami` shows researcher access; otherwise skip `findings` and write in the limits
   "Shared Mothership findings were not read: that needs professional researcher access." (never an error code).

2. **Verify** every identifier you cite (`plsi evidence verify --kind <pmid|doi|nct> --id <id>`); drop what does not
   resolve.

3. **Draft** `<PLSI_HOME>/work/<thread>/proposal.md`: summary, specific aims, background with the open questions,
   preliminary data (findings with effect, interval and grade, cited by id), approach with falsifiers and the
   analysis specs, risks and limits (self-selected cohort, small cells, model output), and the references.

4. **Return one `result`** with the draft, the step 1 `mothership findings` output saved as
   `<PLSI_HOME>/work/<thread>/ledger.json`, and the claims that need Challenger (`challenger/challenge`, Claim mode)
   before it goes anywhere. With Challenger's objections relayed, revise the draft once and return it with them.

## Rules

- No claim stronger than its source; a Mothership finding stays hypothesis-generating.
- Prose polishing is PLSI Writer's (`writer/prose`, through PLSI, when Writer is on the team). Never submit
  anything yourself; a Mothership project proposal has no wire message yet, so the draft stays in the work folder.
