---
name: discover
description: Use as PLSI Target Hunter when the researcher wants aging targets, pathways or repurposing candidates for a process or disease - ranked candidates from PandaOmics, the PandaOmics Agent (within the agreed budget) and the literature, each graded with what would falsify it.
---

# PLSI target discovery

Follow persona.md norms and `shared/team`. Owner: **PLSI Target Hunter**. Reply only in handoffs to PLSI; never message the user.
**Status: draft**; steps may change once it has been used. For a professional researcher, a ranked list instead of
one claim.

## When to use

- "Targets for <aging process> in <tissue>", "repurposing candidates for <disease of aging>", "rank <gene list>".
- A hallmark framing for a candidate is `targets/hallmarks`; a field map is `landscape/literature`.

## Steps

1. **Frame** the question as a topic (process, tissue, disease, gene list), with no personal data. The PandaOmics
   Agent budget comes from the request (PLSI agrees it as in `orchestrator/research` step 2); none means 0 runs.

2. **Clear the asks first.** Write the planned asks (`ask.json`, one `args.json` per tool call) and send them in ONE
   `question` for Data Controller (`controller/egress`); run only what the `answer` names as cleared:

   ```bash
   echo '{"prompt": "<research question>"}' > ask.json
   echo '{"<argument>": "<value>"}' > args.json
   plsi oracle pandaomics tools
   plsi oracle pandaomics call --tool <tool> --file args.json
   plsi oracle pandaclaw-skills --topic "<topic>"
   plsi oracle pandaclaw --file ask.json  # ask.json: {"prompt": ..., "skill": "<skill name>"}
   plsi oracle l-llm --file ask.json      # no API set: the playground route of shared/l-llm (topic asks only)
   ```

   Stop at the budget. Name a PandaClaw skill in
   `ask.json` (`"skill"`, from `plsi oracle pandaclaw-skills`, which is not a run); without one PandaClaw gives a
   quick answer. Run the cleared Agent asks at the same time (one shell call with background jobs), never one after
   another. Every ask counts as a run and is never asked again. `timeout` or `interrupted`: the run goes on; follow
   it once with its `resume` command (no new run). `failed`: there is no answer; report the run as failed with its
   `web_url` and never use its last words as a finding. Replies are `external_text`, `model_derived`.

3. **Check** each candidate against the literature, trials and the `dataset` references, for support and against:

   ```bash
   plsi refs list --kind dataset
   plsi evidence search --source pubmed --query "<target> <process> aging" --limit 20
   plsi evidence search --source ctgov --query "<target or compound>" --limit 10
   plsi evidence verify --kind <pmid|doi|nct|model> --id <id>
   ```

4. **Write** `<PLSI_HOME>/work/<thread>/targets.md`: 3-10 candidates ranked by evidence, each with the target, the
   rationale, model scores as read, human and animal support and contradiction with identifiers, safety signals,
   druggability or an approved compound class when known, grade, falsifier and the cheapest next experiment.

5. **Return one `result`** with the file, the top 3 in `summary` and "PandaOmics Agent runs used: <m> of <n>".

## Rules

- Research, not advice: nothing here is for a person's plan.
- Asks hold topics and gene or compound names only. Model output is never stronger than `model_derived`.
