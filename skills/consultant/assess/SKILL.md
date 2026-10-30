---
name: assess
description: Use as PLSI Health Consultant when PLSI asks where the user stands (biological age, risk markers, trends), after new data was ingested, or when PLSI hands it an extension coordinate to add to a user map.
---

# PLSI assess

Follow persona.md norms and `shared/team`. Owner: **PLSI Health Consultant**. Reply only in handoffs to PLSI; never message the user.

## When to use

- After PLSI Data Processor recorded new observations (`processor/intake`, `processor/history`); PLSI hands over the
  new `states`.
- The user asks about their state, clocks, trends or what to measure next.
- Before `nostradamus/plan` (plans are gated on a fresh projection).

## Steps

1. Select maps. Read each map's coverage (`present`, `missing`, `ratio`, `tags`) and choose one or more for the user's question; say in one line why, and which maps you rejected. After new `lifestyle` observations (or when the question is about alcohol, smoking, vaping, shift work or abstinence), include `lifestyle_context`.

   ```bash
   plsi maps select --instance <instance>
   plsi maps show blood_phenoage
   plsi clocks list
   ```

2. Read each chosen map that arrived in the request's `states` with `plsi state show`; when `current` is true, do not
   re-project it (that would erase its changes) and take Changed and Gaps from Data Processor's storyline in the
   request `summary`. Project only the chosen maps with no state or `current` false. Projecting writes
   `states/<map>/latest.json`, the saved state every plan refers to.

   ```bash
   plsi state show --instance <instance> --map blood_phenoage
   plsi project --instance <instance> --map blood_phenoage
   ```

3. Read `data.storyline` of each map you projected: clock accelerations, change vs the previous projection per coordinate, and gaps. Report values with units, dates and status (`present`, `stale`, `missing`, `error`).

4. When no installed map has a quantity you need, put a `processor/add-map` request in your `result` (the quantity, its unit, why); see `shared/team` Map gaps. When PLSI hands you an extension coordinate (`engineer/extend`), add it to a user map `user_<topic>.yaml` (schema `contracts/MapContract.schema.json`; copy the structure of `plsi maps show <id>`). Use `id: user_<topic>`, `claim_level: designed`, LOINC codes in `accepts.codes` (`reject_codes` for look-alikes) and a `source` on every conversion.

   ```bash
   plsi maps validate user_topic.yaml --live
   plsi maps install --instance <instance> --file user_topic.yaml
   plsi project --instance <instance> --map user_topic
   ```

5. Send ONE `result` to PLSI; `states` lists every projected map with its `state_hash`, and `summary` holds, compactly:
   - **Maps:** chosen and rejected, one line why.
   - **Now:** the key values with units, dates and status; clock accelerations; what the map does not support.
   - **Changed:** each coordinate that moved since the previous projection (old -> new, dates), or "first projection".
   - **Gaps:** each as a measurement request from the gap's `suggestion`: test name, why it matters for this map or
     question, where (at home: wearable, cuff, scale, finger-prick kit; or a lab or clinic draw, fasting if needed),
     and which coordinate it fills. Most useful first, at most 5.
   - **Red flags:** a `red_flag:` line (`orchestrator/urgent`) for any coordinate the lab flagged critical or beyond a
     critical limit from a verified source (`plsi evidence verify`); `uncertain` when no source exists. Do not
     interpret it further. Very low weight-for-height goes as a `scope:` line instead.

   PLSI decides what the user sees and PLSI Visualizer draws the charts; you never render a report or message the user.

## Rules

- Values come only from `project` or `state show`; never compute or estimate a coordinate yourself.
- Never re-project a `current` state (step 2); a stale `latest.json` blocks plans.
- Fix every violation `maps validate` returns before installing; never edit shipped maps.
- State the map's `inference_boundaries` when interpreting: say what the map does not support.
- `lifestyle_context` holds only **active** lifestyle items (not stopped/resolved, not ended). Past periods remain
  in the event log; never invent abstinence when the user did not state it. When reading `active_lifestyle`, treat
  `dose` as quantity/frequency/regularity on a stable habit `text` — not a second identity. A stop must use the same
  habit text the active row used (`processor/intake`, Lifestyle).
