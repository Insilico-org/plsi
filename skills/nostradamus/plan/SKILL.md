---
name: plan
description: Use as PLSI Nostradamus when PLSI asks for options to improve a coordinate (for example lower PhenoAge acceleration) or relays specialists' dosed proposals - merge them into ONE screened, recorded plan with explicit predictions.
---

# PLSI plan

Follow persona.md norms and `shared/team`. Owner: **PLSI Nostradamus**. Reply only in handoffs to PLSI; never message the user.

## When to use

- The user asks what they could try, or wants to start, change or compare interventions.
- A current state exists (`plsi state show`); otherwise say so in a `result` (PLSI has PLSI Health Consultant project it, `consultant/assess`).
- Not when the request `summary` names a `scope:` line (`orchestrator/urgent`) and the plan falls in that area:
  return a `result` that declines it and names the care to point to; draft nothing.
- When the request `summary` or a relayed proposal names `caution: mood-screen-positive` (`orchestrator/urgent`):
  do **not** hard-decline the whole plan. Keep a clinician check as a `test` FIRST; merge Sleep stress practices
  only (no longevity stack / new progressive WHO); surface the exact caution line in the plan `objective` or
  findings and in the `result` `summary`.
- You are the one plan author: specialists only propose. Exercise and substance actions are dosed by PLSI Coach,
  sleep and stress by PLSI Sleep, diet by PLSI Nutritionist, supplement stacks by PLSI Biohacker, patient protocols
  by PLSI Clinical Evidence (physician role); their dosed proposals reach you through PLSI. A domain whose specialist is not on the team is off: do not dose it; say so in
  your `result` so PLSI can offer "Add <bot>?". A general, undosed plan action in that domain (or in a domain no
  specialist owns) is still allowed.

## Steps

1. **Gather evidence on the fly** for each candidate option, reusing what is already known (`shared/team`, Evidence
   speed), then verify every identifier you will cite. If the request names the chosen option(s) (specialists'
   proposals relayed by PLSI, or the user's pick), skip the pick: reuse the proposals' verified claims, search only
   for cross-domain interactions and the screening points, make no oracle asks (no pick question carries their
   clearance) and go to step 2.

   ```bash
   plsi evidence search --source pubmed --query "<intervention> <coordinate> randomized" --limit 10
   plsi evidence search --source europepmc --query "<intervention> <coordinate>"
   plsi evidence search --source ctgov --query "<intervention>"
   plsi evidence search --source openfda --query "<intervention>"
   plsi evidence search --source evipedia --query "<intervention>"
   plsi evidence verify --kind pmid --id <pmid>
   plsi evidence verify --kind doi --id <doi>
   ```

   With the Evipedia MCP connected, use `search_reviews`, `get_conclusion` and `get_metadata` (cite as `{"kind": "evipedia", "id": "<slug>"}`). Model oracles are `model_derived` (cite as `{"kind": "model", "id": "pandaclaw"}` or `"longevity_llm"`). Send `instance`/`map_id` (the saved state leaves the computer) only when the request `summary`
   names the user's oracle approval ("Oracles: allow", or the user's Allow relayed on this thread). Otherwise build the
   options with topic-only asks (`{"prompt": ...}`, no personal data). For "ask each time", add "Send your <map> values
   to <oracle> for a personal check of the chosen option?" to the option-pick `question` below, and make that ask only
   after the `answer` says Send, before step 2. When no pick is needed, stay with topic-only asks; never send a question
   only for oracle consent.

   Write each planned ask to `<PLSI_HOME>/work/<thread>/ask.json` and put it in the step's ONE `question` for PLSI
   to clear with PLSI Data Controller (`controller/egress`); run only the asks the `answer` names as `cleared`,
   unchanged:

   ```bash
   echo '{"prompt": "<question>", "instance": "me", "map_id": "blood_phenoage"}' > ask.json
   plsi oracle pandaclaw --file ask.json
   plsi oracle l-llm --file ask.json      # no API set: the playground route of shared/l-llm (topic asks only)
   ```

   Save the options' sources and findings to `<PLSI_HOME>/work/<thread>/evidence.json`. Put the graded options
   (benefits and risks) in the step's ONE `question` and wait.

2. **Write ONE `plan.json`** (schema `contracts/PlanInput.schema.json`) from the step 1 evidence in `evidence.json`,
   merging every relayed proposal into it (each prediction names the `map_id` of its coordinate, so one plan spans
   every map the proposals predict on; keep each proposal's dose and schedule; drop duplicates; one
   no-action control for the whole plan); screen the combined set in step 3, since cross-domain actions interact;
   search again only for what the chosen option still lacks (a dose, a schedule, a safety point). Under
   `caution: mood-screen-positive`, put the caution line in `objective` (or a findings caution), order the clinician
   `test` first among actions, drop new supplement/longevity-stack actions, and keep only low-intensity stress /
   restorative proposals from Sleep (and Coach NARROW if present):

   ```json
   {"objective": "lower phenoage_acceleration over 90 days",
    "actions": [{"local_id": "a1", "description": "<intervention> <dose> daily", "category": "supplement",
                 "dose": "<dose>", "schedule": "daily"}],
    "claims": [{"local_id": "c1", "statement": "<what the source shows>", "evidence_class": "evidence_backed",
                "sources": [{"kind": "pmid", "id": "<pmid>"}], "supports": ["a1"],
                "effect": {"coordinate": "crp", "direction": "down"}}],
    "predictions": [
      {"local_id": "p1", "map_id": "blood_phenoage", "coordinate": "phenoage_acceleration",
       "target": "change_from_baseline", "horizon_days": 90, "expected": -1.0, "low": -3.0, "high": 0.5, "interval_level": 0.8, "method": "<how you derived it>",
       "evidence_class": "evidence_backed", "basis": [{"kind": "pmid", "id": "<pmid>"}], "driven_by": ["a1"]},
      {"local_id": "p0", "map_id": "blood_phenoage", "coordinate": "phenoage_acceleration",
       "target": "change_from_baseline", "horizon_days": 90, "expected": 0.0, "low": -1.5, "high": 1.5, "method": "no-action control: test-retest variation",
       "evidence_class": "rule_derived", "basis": [{"kind": "rule", "id": "plsi.derive.phenoage"}], "driven_by": []}],
    "revision_rule": {"review_after_days": 90, "continue_if": "p1 within interval or better",
                      "modify_if": "no change and no side effects", "stop_if": "any adverse effect or worse than p0"}}
   ```

3. **Screen with judgment, check, fix.** `plsi screen` sets a floor from the label (term matches); you add what a
   reader sees and a regex misses. Read the care context and the label and literature for each drug or supplement
   action, and write `findings.json` (`{"a1": [{"severity": "caution", "summary": "...", "source": {"kind": "pmid",
   "id": "<pmid>"}}]}`, verified sources only). Your findings can only raise the outcome.

   ```bash
   plsi state show --instance <instance> --map care_context
   plsi screen --instance <instance> --file plan.json --findings findings.json
   plsi plan check --instance <instance> --file plan.json
   ```

   - `block`: drop or replace the action; never argue a block away.
   - `caution`: do not ask now. List each caution in your `result` (one line each, with its source); PLSI shows
     them above its one adoption card (`orchestrator/conduct`), and the user's Start proceeds on every one of them.
     Only after Start set `"acknowledged": true` and an `acknowledgement_note`.
   - Fix ALL other violations `plan check` lists, then re-run it until only unacknowledged cautions remain.
   - Run `screen` and `plan check` again only after changing `plan.json` or `findings.json`, or when a state
     changed (`plan check` reports G1); never as a last check before sending. When a state changes or PLSI Challenger objects,
     change only the actions, claims and predictions it touches, then run them once.

   Run `nostradamus/trajectory` (current course vs with the plan). Save `plan.json`, `findings.json` and
   `trajectory.json` under `<PLSI_HOME>/work/<thread>/` and send a `result` to PLSI: the trajectory brief in `summary`,
   the options, grades, predictions, the no-action control, the cautions and, as the one `questions` item, the start
   date. Add a `red_flag:` line (`orchestrator/urgent`) if the state or evidence shows a critical value or a
   dangerous interaction with a current action. PLSI has PLSI Challenger challenge it (`challenger/challenge`); answer the objections
   once, revising the plan or rebutting with sources. The request carries Challenger's objections on the specialists'
   proposals (Proposals mode): answer each in the draft (drop or lower the dose, or rebut with a source). On an objection to a specialist's dose, drop the action or lower
   its dose (stricter only), citing the objection; a new dose needs its owner, so name `<role>/<skill>` in your
   `result` for PLSI to dispatch. Only if the plan changed, rewrite `trajectory.json` and re-run
   `screen` and `plan check`.

4. **Record and adopt** only after PLSI's `answer` from the one adoption card. Start: set the acknowledgements,
   then record (`plan record` runs every gate) and adopt on the chosen date. For a Review `modify`, PLSI sends the
   `replacement_plan_id` and start date: run only `plan adopt`:

   ```bash
   plsi plan record --instance <instance> --file plan.json
   plsi plan adopt --instance <instance> --plan <plan_id> --start-on 2026-10-21
   ```

   "Change the plan" carries the user's words: change only what they touch (step 3) and send a new `result`. "Not
   yet": record nothing.

   Send a `result`: the plan id, the review date and what to measure at each horizon, or plainly what failed.

## Prediction guidance

- Prefer `phenoage_acceleration` or `change_from_baseline` targets; they cancel ageing and baseline offsets. Add a
  `level` prediction of the same coordinate when the trajectory should draw it (`nostradamus/trajectory` step 5).
- Honest intervals: include measurement noise and the uncertainty of transferring population effects to one person.
- State assumptions (adherence, dose, measurement timing) in `method`.
- Compute expected values of derived targets (clocks, scores) with `plsi calc derive ... --set <input>=<value> --at
  <horizon date>` from the effect sizes you cite; never by hand. Start no-action courses from `base_rate` references.
- Always add one no-action control prediction (`driven_by: []`); it is the bar the plan must beat.

## Rules

- Soft `caution: mood-screen-positive` is durable packaging, not hard `scope:`: clinician/test FIRST, no longevity
  stack, stress practices only; repeat the caution line in the `result` `summary`.
- A proposal that predicts on a quantity no map has: keep the action, put a `processor/add-map` request in
  your `result` and add the prediction once the coordinate exists; never predict on an uninstalled coordinate.
- Re-screen when the plan, the care context (medications, conditions, allergies) or the 7-day screening window changes.
- Cite only identifiers verified with `plsi evidence verify` in the last 30 days (`plan check` enforces it for plan sources only).
- Each action needs a supporting claim at or above the map's `min_evidence_class_for_actions`.
- Prediction coordinates must be predictable map coordinates, in the coordinate's canonical unit.
- Never call `plan record` or `plan adopt` without the user's confirmation relayed by PLSI.
