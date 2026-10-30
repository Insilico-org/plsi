---
name: trajectory
description: Use as PLSI Nostradamus after every plan proposal, and when the user asks "where am I heading", "what changes if I do this" or to simulate several regimens against doing nothing (n-of-1 what-ifs, body weight, expected lifespan) - return trajectory.json with the current course vs the proposed plan, or the Scenarios mode with a baseline and up to 4 regimens, plus a short brief.
---

# PLSI trajectory

Follow persona.md norms and `shared/team`. Owner: **PLSI Nostradamus**. Reply only in handoffs to PLSI; never message the user.
Nostradamus predicts; PLSI renders it (`visualizer/dashboard`, scope "trajectory brief"). Every number comes from a
state, a `plsi calc derive` output, a `base_rate` reference, a verified paper or the plan's predictions; nothing is
estimated by hand.

## When to use

- `nostradamus/plan` step 3: with every plan proposal or revision, before the `result` goes to PLSI.
- PLSI asks for skill `nostradamus/trajectory` ("where am I heading", "what does this plan change").
- With every replacement plan PLSI Reviewer asks for (`reviewer/review` `modify`; current course vs revised plan),
  and after it is adopted.
- **Scenarios mode:** PLSI asks to compare regimens with doing nothing before any plan (the regimens in `summary`,
  the specialists' proposal files in `files`); see **Scenarios** below. It records nothing.

## Steps

1. **Read the plans and the state of every map their predictions name** (each prediction's `map_id`). Stale states (`current: false`): say so in a `result` (PLSI has PLSI Data Processor re-project); stop.

   ```bash
   plsi state show --instance <instance> --map <map_id>
   plsi plan list --instance <instance>
   plsi refs list
   ```

2. **Pick 3-6 items** that matter most for this person: the plan's predicted coordinates first, then the top
   modifiable risks in the state (risk equations, raised markers). No fixed list.

3. **Current course** (no action), per item, at the plan's horizon dates (`horizon_days`), also for risks. With
   two or more recorded values that move one way, never draw the slope yourself: use a slope only from a `calc`
   output or a verified source, otherwise keep the course flat and say in `basis` "recorded values trending
   <up|down>; course shown flat", so a small change is not mistaken for success.
   - Clocks and scores: `plsi calc derive` at the horizon date with today's inputs; interval from test-retest
     variation (the plan's no-action control `p0` when it exists).
   - Risks: a published risk equation in the state, derived as of the plan's horizon date with today's inputs (`--at
     <plan horizon date>`), labelled "10-year risk as of <date>"; or a matching `base_rate` table (age, sex, country,
     period; cite table and year) or a verified cohort paper.

   ```bash
   plsi calc derive --map <map_id> --coordinate <coordinate> --instance <instance> --at <horizon date>
   plsi evidence verify --kind pmid --id <pmid>
   ```

   No sourced number: leave the item level-only: `"basis": "hypothesis_only"` on the item, empty `current` and `plan`.

4. **With the plan.** Only the plan's recorded or proposed predictions (`plan.json`), with their intervals and
   `local_id`; never extend them past their horizons or add effects the plan does not predict. A plan effect on a risk
   input: run `plsi calc derive ... --set <input>=<value> --at <horizon date>` at the input's expected, low and high
   values; expected is the run at the expected value, low and high are the min and max of the three outputs. An input
   predicted as `change_from_baseline` leaves the risk level-only on the plan course unless the plan also records the
   absolute input value; never add the delta by hand.

5. **Write `<PLSI_HOME>/work/<thread>/trajectory.json`:**

   ```json
   {"instance": "me", "thread": "plan-2026-10-21", "as_of": "2026-10-21", "plan": "work/plan-2026-10-21/plan.json",
    "states": [{"map_id": "blood_phenoage", "state_hash": "sha256:..."}],
    "items": [{"coordinate": "phenoage_acceleration", "label": "Biological age gap", "unit": "years",
      "kind": "marker", "now": {"t": "2026-09-14", "v": 2.1, "source": "state blood_phenoage"},
      "current": [{"t": "2027-01-19", "expected": 2.1, "low": 0.6, "high": 3.6, "basis": "p0 test-retest"}],
      "plan": [{"t": "2027-01-19", "expected": 1.1, "low": -0.9, "high": 2.6, "basis": "p1 (level)", "source": "pmid:<pmid>"}]},
     {"coordinate": "<risk>", "label": "10-year <event> risk", "unit": "%", "kind": "risk", "now": {...},
      "current": [{"t": "2027-01-19", "expected": 9.0, "low": 6.5, "high": 12.0, "basis": "<equation>, 10-year risk as of 2027-01-19"}],
      "plan": []}],
    "summary": "..."}
   ```

   Values in the coordinate's canonical unit, on the same scale as `now`. Plan predictions with target
   `change_from_baseline` go in the item's `changes` list (`{"t", "expected", "low", "high", "basis"}`), shown only in the
   table as "change <expected> (<low> to <high>)", never as `plan` level points. An empty `plan` list means the plan
   does not predict that item's level. To draw a plan course, `nostradamus/plan` also predicts the level (`target: level`).

6. **Write the brief** (`summary`, at most ~120 words): about 80% plain facts (where each item is now, where it
   heads on each course, how wide the uncertainty is, what is not predicted), then about 20% vivid: one or two
   sentences in the second person with a concrete image of the day-to-day difference ("By spring you would ...").
   Only numbers that are in the file; say "roughly" with the interval, not false precision.

7. **Return** the path in `files` of the `result` (with the plan's `result` in `nostradamus/plan`); the brief goes in
   `summary`. PLSI renders it with `visualizer/dashboard` and shows it with the adoption card.

## Scenarios

Several regimens against a baseline (nothing changes), for the items that matter (step 2) plus, when asked, body
weight and expected lifespan. Scenarios are what-ifs from population evidence, not plans and not predictions that
get scored; a regimen the user wants to try then goes through the Plan flow.

1. **Regimens:** the baseline first, then at most 4 from the request: the user's own and the specialists'
   proposals (`work/<thread>/proposal-<role>.json`), each with its actions as written.
2. **Effects, each cited:** for each regimen and item, the steady-state change with low and high and its time
   course from a verified trial, meta-analysis or model (`plsi evidence verify`); for lifespan, the hazard ratio
   for all-cause mortality (with its interval) that the cited cohort or meta-analysis gives for the change, and from
   when it applies. The baseline uses the person's own state: an `age_shift` from a recorded biological-age gap
   (e.g. `phenoage_acceleration`), cited as that state, or a hazard ratio for a recorded risk factor, cited. No cited
   effect: the item stays flat for that regimen and says "no sourced effect".
3. **Compute, never by hand:** a measurement (weight, a marker) with `plsi calc course` (start = the latest
   recorded value from `state show`; one scenario per regimen); lifespan with `plsi calc survival` (age, sex and country from the
   instance's subject, `plsi status`; no country recorded: ask PLSI in a `question`; the bundled UN WPP 2024 snapshot covers USA, China and Costa Rica; for any other country
   download the latest WPP single-age life table CSV for the person's sex once (`plsi refs show un_wpp`, download
   centre, "Life_Table_Complete", estimates) into `<PLSI_HOME>/data/` and give it as `un_wpp.file`; other tables as
   `q` rows from a `base_rate` reference, with that id as `source`). Several effects on
   lifespan in one regimen: multiply their hazard ratios only when the sources adjusted for each other; otherwise
   use the largest single one and say so.

   ```bash
   plsi calc course --file <PLSI_HOME>/work/<thread>/course-<item>.json
   plsi calc survival --file <PLSI_HOME>/work/<thread>/survival.json
   ```

4. **Write `trajectory.json`** with `"mode": "scenarios"`, `"scenarios": ["baseline", "<regimen>", ...]` and per
   item a `courses` object (scenario name -> points `{t, expected, low, high, basis, source}`) instead of `current`
   and `plan`; lifespan is an item of kind `lifespan` with, per scenario, the `calc survival` row (life expectancy
   with low and high, median age at death, chance of reaching 80 and 90, years vs baseline) and its survival curve.
   The brief (step 6) leads with the baseline and says once that these are population averages applied to the
   person, not a forecast of their life.

## Rules

- Two courses only: current course and with this plan (the Scenarios mode is the one exception). Never mix in other options or unrecorded actions.
- Every point has expected, low, high and a basis; level-only items are labelled, never filled in.
- Do not imply certainty or cure; the vivid part describes the predicted difference, never a promise.
- No intervention names in the brief beyond the plan's own action labels; no names, places or employers.
- Plan changed after `challenger/challenge` or a review: rewrite the file before the `result`.
