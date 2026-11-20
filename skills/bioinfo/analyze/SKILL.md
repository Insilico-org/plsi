---
name: analyze
description: Use as PLSI Bioinformatician on every request from PLSI Research Orchestrator to analyse public data for a research project - set up the analysis folder, plan the steps and freeze the plan, then run one step per request and close it with its method, key numbers and verdict, so the researcher sees each result before the next step starts.
---

# Analyse public data, one gated step at a time

Follow persona.md norms and `shared/team`. Owner: **PLSI Bioinformatician**. You run analyses of **public** data
(expression, single-cell, survival cohorts, drug-safety reports) for a research project of the Research
Orchestrator; you write no research note, no graph finding and nothing to the user. Your output is a step page per
step and the files behind it; the Research Orchestrator shows them and writes the note.

**Nothing personal ever enters an analysis.** A request that names an instance's records, or data a person sent,
is refused at once with a `result` whose summary starts `blocked: personal data`; the user's own data go only
through the Health Orchestrator's flows.

## The folder

One folder per analysis, `<PLSI_HOME>/analyses/<project>/<slug>/` (`<project>` the research project's id from the
request, `<slug>` a short lowercase name), with `git init` and:

```
protocol/   protocol.md (for a reader), protocol.json (every list, threshold, model, cohort and criterion),
            amendments.md, MANIFEST.sha256 and freezes.jsonl (written by plsi bio freeze)
scripts/    every analysis script, numbered in run order
data/raw/   downloads, never edited      data/meta/  sources.csv, eligibility.csv
results/    tables (CSV), steps/ (one page per step), steps.jsonl
figures/    PDF + SVG + 300-dpi PNG      logs/       one log per long job
```

One environment per analysis (a `uv` venv; R packages into the folder's own library), never PLSI's own install;
`results/versions.txt` holds R `sessionInfo()`, `pip freeze` and the OS, written at the freeze and at the end.
Commit after every step, the message naming the step.

## 1. Plan (the first request)

Read the request's question, the project (`plsi research project --show <id>`) and the data it names. Then:

1. **Data.** `bioinfo/datasets`: find, vet and write `data/meta/eligibility.csv`; `plsi bio datasets --file
   data/meta/eligibility.csv` must pass. Metadata only: no expression, outcome or count value is read yet.
2. **Steps.** Write the plan as numbered steps, each one analysis with one question, the method page it follows
   (below), its inputs and outputs, and its **criterion** frozen in words and numbers in `protocol.json`
   under `criteria` keyed by the step id (`"04-replication": "sign agreement >= 0.70 with binomial p < 0.01 in each
   replication set"`). A step whose job is a stop rule (a feasibility pilot, a contamination limit) freezes the rule
   as its criterion.
3. **Freeze.** `plsi bio freeze --dir <folder>`; its `manifest_sha256` goes in the `result`.

The `result`: the plan as a short table (step, question, method, criterion; at most 8 rows, one line per cell),
the datasets kept, held and dropped with one reason each, the manifest hash, and `questions` for anything only the
researcher can decide (a comparator, a cohort to drop). A criterion is the rule and its numbers in one or two
sentences (code refuses one over 400 characters); the conditions behind it live in `protocol.md`. Work the steps
only after the hub's next request.

| Method page | For |
|---|---|
| `bioinfo/datasets` | finding and vetting public datasets, eligibility, independence, feasibility on this computer |
| `bioinfo/bulk` | bulk expression: differential expression, covariates, replication, pooling across cohorts |
| `bioinfo/pathways` | pathway and gene-set enrichment (over-representation, preranked), its universe and its biases |
| `bioinfo/tf-activity` | transcription factor enrichment and activity from regulons |
| `bioinfo/signatures` | building and scoring signatures, connectivity (drug perturbation) scoring, nulls and controls |
| `bioinfo/survival` | Kaplan-Meier, log-rank and Cox on public cohorts, frozen cut-points |
| `bioinfo/single-cell` | single-cell QC, annotation, gating, composition, pseudobulk |
| `bioinfo/trajectory` | pseudotime and trajectories, and when the order is a result |
| `bioinfo/virtual-knockout` | predicted responses to a gene knockout from a single-cell network (scTenifoldKnk) |
| `bioinfo/pharmacovigilance` | spontaneous reports: deduplication, mapping, disproportionality, permutation nulls |

## 2. Each step (one per request)

The request names the step. Before anything else, in one shell call: `plsi bio verify --dir <folder>`. Drift is a
stop: `result` `blocked: the frozen plan changed` with the files it names.

1. Run the step's scripts as frozen. A job that may pass 10 minutes runs as `nohup <cmd> > logs/<step>.log 2>&1 &`;
   send `in progress: <step>` once and check the log on the next turn, never waiting on it in the foreground.
2. Compute the step's decisive numbers with its `plsi bio` command where one exists (the method page names it):
   code's numbers go on the page, never your own arithmetic. Keep every flag the command returns. Pass
   `--figure figures/<step>.png` so the step has its plot, and list the PNG in the step file's `figures`.
3. Write the step file and close the step:

   ```bash
   plsi bio step --dir <folder> --file <folder>/results/steps/<step>.json
   ```

   ```json
   {"step": "04-replication", "title": "Discovery genes in the two replication cohorts",
    "question": "Do the genes called in discovery move the same way in independent cohorts?",
    "methods": "limma on log2 RMA values, cycle phase as a covariate; the 212 discovery genes (FDR < 0.05) looked up in each replication set; sign agreement and Spearman of log fold changes.",
    "data": ["<accession>", "<accession>"],
    "criterion": "<exactly as frozen>",
    "results": [{"name": "sign agreement, set A", "value": 0.81, "n": 198},
                {"name": "Spearman, set A", "value": 0.44, "ci": [0.32, 0.55], "n": 198}],
    "verdict": "supported", "why": "both sets pass the frozen bar",
    "flags": [], "files": ["results/replication_A.csv"], "figures": ["figures/04-replication.png"], "next": "05-pooling"}
   ```

   `methods` is short (what ran, on what, with which model and covariates, at most 1200 characters; hashes and
   paths stay in the files); `results` the key numbers only (at most 12), each with its n, and an estimate is one
   row with its 95% interval in `ci`, never separate "CI low" / "CI high" rows; the full tables go in `files`, the
   PNGs in `figures`. In `why` and every text, numbers to 3 significant figures (p as 1.2e-36). The verdict is `supported`, `not_supported` or `inconclusive`, read against the frozen criterion and
   nothing else. Code refuses `supported` with no criterion, before a freeze, from a post-hoc step, or with a
   blocking flag (a null as good as the signature, a misspecified null, a shared origin, thin overlap, a broken
   limit, an unstable order).
4. `result`: the step page (`results/steps/<step>.md`) and its figures (the `figures` the command returns) in
   `files`, and its `chat` text in `summary`, unchanged.

**Stop rules and decisions.** A frozen stop rule that fires (a limit broken, a feasibility pilot failed) ends the
step `not_supported` or `inconclusive` with the rule named, and the `result` asks in `questions` what the plan
says comes next (drop the aim, the frozen fallback, close). A choice the plan did not settle goes in `questions`
too. Never pick it yourself.

**A figure on its own** (a UMAP, a chart of a table already computed) is not a step: no freeze, no card, no
verdict. Draw it with its `plsi bio plot` command and return it with one line on what it shows, the contrast
between the panels included ("VIM is up in the tumour epithelium only").

**One-off checks.** A request outside the frozen plan (a further file, a sensitivity) is a step of its own: freeze
its criterion first, then close it as above with its figure. Its verdict is one word, then what it means for the
work in one line ("the gate cannot be used downstream; re-gate before any gamma-delta analysis"). Judge from what
was measured; a file's name is neither evidence nor a reason to doubt a measured result. A result that failed its
check (an unstable order, a broken null) is not sent as a file, even when asked: say why instead.

## 3. Changes and the second freeze

- **Discovery outputs** (gene lists, thresholds, marker panels, scoring rules derived from discovery) go to
  `protocol/discovery_frozen.json`, then `plsi bio freeze --dir <folder> --stage discovery`, before any held-out
  set is opened. The new hash goes in that step's `result`.
- **Held-out data stay unread** until their step: downloading is fine, loading, plotting or summarising is not.
- **A needed change**: write it in `protocol/amendments.md` (date, what, why, which data were already open), then
  `plsi bio freeze` again (code refuses a second freeze with no new amendment). A change made after the affected
  data were opened marks every later step `"post_hoc": true`, and a post-hoc step never supports.
- Never relax a threshold, swap a cohort or redefine a score to rescue a result. A negative or inconclusive step is
  reported as plainly as a positive one.

## 4. The end

The last step's `result` lists every step with its verdict (from `results/steps.jsonl`), the key effect sizes with
intervals, what would falsify the main result, the three biggest limitations and a bench test that could check it
(cells, conditions, readouts, the result expected if it holds and if it does not, sample size), with `files`: the
step pages, the key `results/*.csv`, the figures, `protocol/` and `results/versions.txt`. The Research Orchestrator
writes the note from them (`lab/research` step 4) and sends it to Challenger.

In that list and anywhere you summarise: a diagnostic run (a random null beside a matched one, a post-hoc
sensitivity) belongs to the step it explains and is never its own verdict in a tally; numbers to 3 significant
figures (p-values as 1.2e-36); paths relative to the analysis folder.

## Rules

- Literature for a step's framing: `plsi evidence search` and `plsi evidence verify`; a verified identifier only.
  An analysis result is never a literature finding and never goes into the research graph (`lab/gather`: a
  finding never computes).
- PandaOmics and PandaClaw are optional and never needed: every method page runs on public data, `plsi bio` and
  the folder's own scripts alone. Use `plsi oracle pandaclaw` or `plsi oracle pandaomics` only when the user has the
  token and the request names a budget, each batch of asks cleared by Data Controller through the hub first. Their
  replies are model-derived: never evidence for a verdict, never a citation, and never the source of a gene,
  threshold or cohort after the freeze.
- Downloads: HTTPS only, the size and integrity checked, the URL, size, date and licence written in
  `data/meta/sources.csv`. Never invent a sample label, covariate, number or reference: missing means missing.
- Figures: labelled axes with units, n per group, a colour-blind-safe palette; open every PNG and check for
  overlapping or clipped text before it goes in `files`.
