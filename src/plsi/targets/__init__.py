"""Target discovery from free sources: `<PLSI_HOME>/targets/<gene>/` holds one dossier per target.

Code gathers and counts; the bot judges through `plsi targets assess`, which refuses ungrounded claims, and
`plsi targets brief` is how a dossier reaches the research bots. The package in layers:

- **Gathering** (network, one module per source): `opentargets` (the GraphQL client, name resolution and
  associations), `biology`, `drugs` and `genetics` (more of Open Targets), `genes` (MyGene.info), `pharos`,
  `structures` (PDB, AlphaFold), `chemistry` (ChEMBL), `protein` (UniProt), `aging` (Open Genes); `trials` and
  `unmet` read ClinicalTrials.gov through `plsi.policy.ctgov`. `dossier` runs one gather and `store` keeps it.
  `discover` lists candidates for a disease or a hallmark and writes nothing.
- **Reads** (offline, recomputed on every read): `rank` (the computed block: band, stage, direction), `reads`
  (the per-source reads), `gaps` (open questions, disagreements, what was not read), `hallmarks` (the aging
  frame).
- **Assess**: `models` (the assessment schema) and `assess` (the refusals, `target-refusal-N`); `keyed` lists
  the user's own platform keys and today's oracle allowance.
- **Brief**: `brief`, the citable part of a dossier for a research move.

`commands` is the `plsi targets` command table.
"""
