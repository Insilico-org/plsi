---
name: extend
description: Use as PLSI Engineer when PLSI asks for something the user needs that no map or formula can do - an input format it cannot read, a computation that is not one formula, or a source of evidence it cannot search - so a tested code extension adds the operation.
---

# PLSI extend

Follow persona.md norms and `shared/team`. Owner: **PLSI Engineer**. Reply only in handoffs to PLSI; never message the user.
Extensions ADD operations; they never replace the core (gates, deid, scoring, the event log).

## When to use

Pick the lowest tier that closes the gap; a map or formula gap goes back in your `result` for PLSI to hand to its
owner:

| Gap | Tier | Skill |
|---|---|---|
| A new area to describe (coordinates, codes) | map | PLSI Data Processor, `processor/add-map` |
| A value computable by one formula | formula | PLSI Data Processor, `processor/add-score` |
| An input format, a non-formula computation, a new evidence source | extension | this skill |

## Steps

1. Name the gap in one line and the extension kind: `importer` (a file format -> observations), `deriver` (a derived
   value from coordinates) or `evidence_source` (search results for `plsi evidence search`).

2. Create the package in the workspace, outside the plsi repo:

   ```
   my_ext/
     plsi_extension.yaml   # id, version (semver), kind, entrypoint main:run, summary, monotone (derivers)
     main.py               # def run(...)
     tests/test_main.py    # tests with synthetic data only
   ```

   Entry points:
   - importer: `def run(data: bytes) -> list[dict]`, items are ObservationInput dicts (`contracts/ObservationInput.schema.json`); `origin` is filled in. Lifestyle items: stable habit name in `original_text`, quantity/frequency in `dose`.
   - deriver: `def run(inputs: dict[str, float], *, age: float | None, sex: str) -> float` (inputs keyed by coordinate id, canonical units). Set `monotone: true` only if the result moves one way in every input.
   - evidence_source: `def run(query: str, limit: int) -> list[dict]` with `title`, `url`, and `kind` + `id` when the item is a pmid, doi, nct, label or evipedia id.

3. Write the tests first, then the code, then install. An extension is full-trust code that runs with the user's
   permissions: install only after the user's explicit approval that names its source (written here, or the URL or
   author it came from). `install` runs the tests with a minimal environment (no keys) and refuses imports outside the
   kind's layer or any patching of plsi; fix every violation it lists. These checks are guard rails, not a sandbox.

   ```bash
   plsi ext install --dir my_ext
   plsi ext list
   ```

4. Use it:

   ```bash
   plsi ingest --instance <instance> --ext my_importer --input export.file --dry-run
   plsi evidence search --source ext:my_source --query "<query>"
   ```

   For a deriver, put the coordinate `derive: {engine: extension, model: <extension id>, inputs: [...]}` in your
   `result`; PLSI hands it to PLSI Health Consultant (`consultant/assess`), who adds it to a user map and projects.

5. Iterate: change the code, bump `version`, install again (installed versions are immutable). `plsi ext test --id <id>`
   re-runs the tests; `plsi ext disable --id <id>` switches an extension off.

## Rules

- Network calls go through `plsi.net` (timeouts, redaction); keys come from `plsi.keys.require("ENV_NAME")`. No secrets in code.
- No personal data in extension code or tests; use synthetic values.
- Derivers are deterministic. Values they produce record `extension:<id>@<version>` in provenance.
- Evidence-source results are leads: verify every ref with `plsi evidence verify` before citing it.
- When an extension has been used in a scored prediction, propose sharing it in your `result` (code only, never user data); PLSI asks.
