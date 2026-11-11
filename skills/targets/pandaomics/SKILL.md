---
name: pandaomics
description: Use as PLSI Target Hunter on demand, only when the user has set their own PandaOmics or PandaClaw token and the free evaluation is already finished - which of the platform's tools answers what, what a platform score may and may not support, the daily cap, and where the answer is recorded.
---

# Asking a commercial platform

Craft, read when needed, not on
every run.

Nothing in target work needs PandaOmics: every question in `targets/evaluate` is answered by free sources, and a
dossier gathered without a token is complete. This page is for a user who already has an account. Read it only when
the dossier's `keyed.unlocked` names a platform; otherwise there is nothing to do here.

## Tokens

Both platforms are bring-your-own-token: the user sets their own token in their environment or `.env`, and PLSI
ships no key.

- `PANDAOMICS_BEARER_TOKEN` (and `PANDAOMICS_MCP_URL` when the account is on another host) opens the PandaOmics MCP
  endpoint; every tool below goes through it. It is an MCP personal access token, not the REST API token: if
  `plsi oracle pandaomics tools` works and a call fails with an authentication error, the token is the wrong kind.
- `PANDACLAW_BEARER_TOKEN` opens PandaClaw.

When a token is missing, say so in the `result`; PLSI helps the user set it (`plsi keys`).

| | Returns | Recorded in | May support |
|---|---|---|---|
| PandaOmics (`plsi oracle pandaomics`) | ranked target lists, a gene's rank with its scores, indications, grants, KOLs | `platform_reads` | nothing as a citation |
| PandaClaw (`plsi oracle pandaclaw`) | prose from an agent | `platform_reads` | nothing as a citation; every identifier in it must verify |

## Four rules

1. **The free path is the floor.** Finish the evaluation first; if the assessment could not be written without the
   platform, the evaluation is not done.
2. **A platform and a curated record do not outrank each other.** Where they differ (a development level, say),
   report both and say which one the question needs.
3. **A score is not a citation.** It carries no PMID, NCT or accession, so it cannot carry a claim. The `llm_*`
   scorings are a language model's judgment arriving as a number. Its scores have no published range or direction:
   write the number with the score's own name, never a word like "high".
4. **Every billed call counts against a daily cap** per platform (`PLSI_ORACLE_DAILY_CAP`, default 25), refused before
   anything is sent. Catalogue listings (`plsi oracle pandaomics tools`, `plsi oracle pandaclaw-skills`) are not runs
   and are not counted. `keyed.unlocked[].today` shows what is left.

## Which tool answers what

```bash
plsi oracle pandaomics tools                       # the live catalogue: check names and arguments first
plsi oracle pandaomics call --tool <name> --file args.json
```

| Tool | Ask it | Why the free path cannot |
|---|---|---|
| `resolve_disease` | `{"query": "<name>"}` -> the platform's `disease_id` | the tools that take a disease need it |
| `resolve_gene_symbol` | `{"query": "<symbol or alias>"}` -> the platform's gene entity | the same, for a gene |
| `explain_target_rank` | `{"disease_id": <id>, "gene": "<SYMBOL>"}` -> why the gene ranks where it does | an independent ranking with its reasoning, to set beside Open Targets |
| `get_target_ids` | `{"disease_id": <id>, "top_n": <n>}` -> the top-ranked genes | a second shortlist beside `targets discover` |
| `get_indication_prioritization` | `{"gene": "<SYMBOL>"}` -> ranked indications | another source's ordering of the dossier's `indications` |
| `get_grants` | `{"gene": "<SYMBOL>"}` or `{"disease_id": <id>}` | current research funding; no free source here has it |
| `get_kols` | `{"gene": "<SYMBOL>"}` or `{"disease_id": <id>}` | who works on this |

The catalogue can change; trust `tools` over this table, and use the short names it lists. Resolve a disease or gene
once and reuse the id. On a shortlist, ask `get_target_ids` once for the disease and read every candidate from it;
`explain_target_rank` is the follow-up for the two or three worth understanding. Never spend a call on what the
dossier already holds (structures, potencies, residues, trials, aging curation, direction of effect).

## Reading the scores

- **Evidence-derived** (`knockout`, `knockin`, `mutation`, `pathway`, `ppi`, `transcriptomics`, `bayes_gwas`): a
  second opinion on what the free sources cover.
- **Attention-derived** (`target_metric`, `funding`, `grant_size`, `high_impact_total`, `trend`, `dl_burst`): how much
  the field has looked at a gene, a competition fact, not quality.
- **Model-derived** (every `llm_*`): report as a model's judgment or not at all.

A rank belongs to a disease; record the question with it.

## Recording it

`platform_reads` on the assessment is the only place a platform answer goes:

```json
"platform_reads": [
  {"source": "pandaomics", "tool": "explain_target_rank",
   "asked": "rank of <SYMBOL> for <disease> (disease_id <id>)",
   "says": "<what came back, in the platform's own terms>"}
]
```

`source` is `pandaomics` or `pandaclaw`. `says` keeps the platform's terms; never turn a score into a verdict.
Refusal 7 rejects an entry with no billed call to that platform (for PandaOmics, that tool) in the egress
ledger in the last thirty days. In the target file these go on the
`Model output` line, `model_derived`.

## PandaClaw

`plsi oracle pandaclaw` is an agent that reads literature and pipeline pages and writes prose; use it for the
landscape question `targets/landscape` leaves to you. Name a skill from `plsi oracle pandaclaw-skills` in `ask.json`
(without one it answers fast and shallow) and keep the whole answer with
`--out <PLSI_HOME>/work/<thread>/pandaclaw_<topic>_<n>.md`. Every identifier in it must pass `plsi evidence verify`
before you cite it, and every asset it names goes through `plsi targets trials` before `harvested_assets`.

## Before you spend a call

- [ ] The free evaluation is finished.
- [ ] `keyed.unlocked` names the platform and `today.remaining` is above zero.
- [ ] The free sources cannot answer the question.
- [ ] On a shortlist, one disease-level call, not one per gene.
- [ ] The answer goes in `platform_reads` with `asked`, not into the prose.
- [ ] Where it disagrees with a curated record, both are reported.
