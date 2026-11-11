# plsi.policy

The Policy layer: evidence, proactive screening, the plan gates, plans with their predictions, scoring and the
model-derived oracles. Commands are listed in `src/plsi/commands.py` (`plsi evidence ...`, `screen`, `plan ...`, `due`,
`score`, `oracle ...`).

| Module | Role |
|---|---|
| `models` | actions, screening records, claims, predictions, plans, scores, verifications, oracle input |
| `evidence` | live search (PubMed, Europe PMC, ClinicalTrials.gov, openFDA, Evipedia, extensions) and the verification ledger |
| `ctgov` | the ClinicalTrials.gov v2 calls and the reading of its study record |
| `screen` | each drug or supplement action against its openFDA label (ingredient via `plsi.rxnav`) |
| `gates` | G1-G8, run by `plan check`, `plan record` and `plan adopt` |
| `fold` | plans folded from the log with their status history and scores |
| `plan` | `plan record/adopt/review/list` |
| `score` | `due`, `score` and calibration |
| `mcp` | a minimal MCP streamable-HTTP client |
| `oracles` | PandaClaw and PandaOmics over MCP: outbound text built in code, the egress ledger, the daily call cap |

Rules:

- Policy never imports `plsi.life`: it reads states, care context, subject and scoring values through `plsi.map.mapper`
  and the maps through `plsi.map.registry`.
- Network calls go through `plsi.net` (MCP through `mcp`), to the hosts of `plsi.references`; every relayed string is
  ExternalText.
- Gates never trust trust-fields written by the bot; a plan's state is a pure fold over its plan_status events.
