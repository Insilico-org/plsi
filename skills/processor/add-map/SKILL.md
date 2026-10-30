---
name: add-map
description: Use as PLSI Data Processor when PLSI forwards a map gap - a bot needs to track, predict or score a measured quantity no installed map has a coordinate for (an amount, a questionnaire total, a device metric, a lab test) - or the user asks to track one, so it becomes a coordinate in a validated, installed user map.
---

# PLSI add a map

Follow persona.md norms and `shared/team`. Owner: **PLSI Data Processor**. Reply only in handoffs to PLSI; never message the user.
A map is a contract for reading the log (Tier 0: no code, no formula). A computed score is `processor/add-score`;
anything one formula cannot do (a file format, a fitted model) is PLSI Engineer's (`engineer/extend`).

## When to use

- PLSI forwards a `processor/add-map` request from a bot: what it needs to track, in what unit, and why.
- `processor/intake` recorded coded measurements that no map reads, and the user wants them tracked.
- The user asks to track something PLSI does not track yet.

## Steps

1. **Is it really missing?** Read every map, the user's included, and the coverage:

   ```bash
   plsi maps list --instance <instance>
   plsi maps show <map_id> --instance <instance>
   plsi maps select --instance <instance>
   ```

   A coordinate that already measures the same quantity (another name, another unit): return it in your `result`
   and stop. A ratio, index or equation of existing coordinates: `processor/add-score` instead.

2. **Define each coordinate:** one quantity per coordinate, measured the same way: an `id` (lowercase), a plain
   `label` that says what and how (e.g. "reported", "calendar-month mean", "stronger hand"), `kind: measured`, the
   canonical UCUM `unit` and `predictable: true` unless it is a list of items (`kind: set` with `collects`).
   Related quantities go in one map (`user_<topic>`); at most 6 coordinates.

3. **Codes.** Find LOINC codes for exactly that quantity (`plsi refs show nlm_clinical_tables_loinc` for the search
   API; property, timing and method must match the label). Put close but different codes in `reject_codes`
   (another hand, another time window, packs instead of cigarettes, another method), so they are never read as this
   one. A code a shipped coordinate already reads belongs to that coordinate: use it instead (the install refuses
   it). No LOINC code exists: accept `{system: free, code: <map_id>.<coordinate_id>}`, and say in your `result` that
   `processor/intake` records its values with exactly that code.

4. **Units, windows, boundaries.** Conversions only with a cited factor (`sources`); otherwise none. `recency_days`
   and `score_window_days` from how often the quantity is measured and how fast it changes (shipped maps of the same
   kind are the default). `inference_boundaries`: what the map supports (tracking and predictions on the quantity)
   and what it does not (diagnosis, comparing methods or devices, values estimated instead of measured or
   answered); `min_evidence_class_for_actions: hypothesis_only`; `claim_level: designed`.

5. **Write** `<PLSI_HOME>/work/<thread>/user_<topic>.yaml`, shaped like a shipped map (`plsi maps show
   sleep_activity`), with a first comment line saying when the codes were checked. Nothing about the user in it:
   no names, dates of their records, values or story; labels and boundaries are generic, so the map can be shared
   later as it is.

6. **Validate, install, project:**

   ```bash
   plsi maps validate <PLSI_HOME>/work/<thread>/user_<topic>.yaml --live
   plsi maps install --instance <instance> --file <PLSI_HOME>/work/<thread>/user_<topic>.yaml
   plsi project --instance <instance> --map user_<topic>
   ```

   A violation is fixed in the file and validated again; `map.code_taken` means the quantity already lives in that
   shipped coordinate (step 1).

7. **ONE `result`** to PLSI: the map id, each coordinate with unit and codes, what the projection found (values
   present, or the gap and its suggestion), the new `states` hash, and one plain line for the user ("PLSI can now
   track your <quantity>"). The requesting bot's work continues with the new coordinate.

## Rules

- Never change a shipped map; a better shipped map is a change to the repository, named in your `result`.
- Never invent a quantity the request does not need, or a code that does not resolve (`--live` checks it).
- Changing an installed user map bumps its `map_version`; old predictions keep scoring against their snapshot.
- The map stays `claim_level: designed` until a prediction on it has been scored.
