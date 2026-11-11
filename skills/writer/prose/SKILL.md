---
name: prose
description: Use as PLSI Writer when PLSI asks for academic or report prose (a report section, a manuscript draft, a plain-language summary) built from research notes and the user's recorded state - deidentified, with every claim only as strong as its evidence.
---

# PLSI write prose

**Status: placeholder**

## Intended scope

- Inputs from the request: research notes (`research-note_*.md`, `lab/session`), state documents cited by hash, the
  audience (the user's own report or a manuscript) and the length.
- Read the state only through `plsi state show --instance <instance> --map <id>`; check sources with
  `plsi evidence verify`. Never open inbox files or record text.
- Every claim keeps the grade and evidence class of its note; no claim stronger than its source, model output stays
  `model_derived`, and each claim cites its identifiers.
- Deidentified: no names, exact dates, places finer than a region or record numbers; anything meant to leave the
  computer goes back to PLSI for `controller/egress`.
- Return the draft as a file under `<PLSI_HOME>/work/<thread>/` in one `result`.

