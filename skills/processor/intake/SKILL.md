---
name: intake
description: Use as PLSI Data Processor when PLSI hands over health data the user shared (PDF, photo, typed values, FHIR export, CSV, methylation betas) or a correction or retraction of something already recorded.
---

# PLSI intake

Follow persona.md norms and `shared/team`. Owner: **PLSI Data Processor**. Reply only in handoffs to PLSI; never message the user.

## When to use

- The user sends a lab report, photo, discharge letter, device export, FHIR bundle, CSV or methylation file.
- The user states a value, medication, condition, allergy, symptom or habit in chat.
- The user states a goal ("run 10 km by June") or a standing preference ("vegetarian", "Budget: moderate"): kind `goal`
  or `preference`, `original_text` is the goal or preference itself, `effective_end` is the target date if any. A goal
  reached or dropped gets a new observation with `clinical_status: "resolved"`. They feed the `personal_context` map.
- Lifestyle habits and exposures (alcohol, smoking or vaping, shift work, abstinence): kind `lifestyle`. They stay in
  the event log and feed the `lifestyle_context` map when active (see Lifestyle below). Do not use `preference` for
  these.
- A recorded value is wrong or must be withdrawn.

## Steps

### PDF or photo

1. Hash the file (the hash goes into `origin.file_sha256`; the filename never does):

   ```bash
   python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" report.pdf
   ```

2. Extract every item into `obs.json`, a list of ObservationInput (`contracts/ObservationInput.schema.json`). One value per item; keep the unit as printed; `value_comparator` for censored results such as `<0.5`.
   A medication or supplement whose source states a dose: keep the wording in `dose` (it never leaves the computer)
   and, when it names one amount per dose, also fill `dose_quantity` (a number > 0) and `dose_unit` (a UCUM symbol:
   `mg`, `g`, `ug`, `mL`, `[iU]`, `U`, `mmol`, or an annotation for counted forms such as `{tablet}`, `{capsule}`,
   `{puff}`, `{drop}`). Both or neither; leave them out when the amount is unclear, a range, or only a frequency.
   Only this amount and unit may be shared with the Mothership, never the wording or the schedule.

   ```json
   [{"kind": "measurement", "original_text": "Hemoglobin A1c", "value_quantity": 5.4, "unit": "%",
     "effective_at": "2026-09-14", "specimen": "blood",
     "origin": {"kind": "grok_extraction", "file_sha256": "<sha256>", "page": 1}},
    {"kind": "medication", "original_text": "<medication as written>", "value_bool": true, "dose": "<dose as written>",
     "dose_quantity": 10, "dose_unit": "mg", "clinical_status": "active", "effective_at": "2026-09-14",
     "origin": {"kind": "grok_extraction", "file_sha256": "<sha256>", "page": 2}}]
   ```

3. Normalize codes (LOINC, RxNorm, UCUM). For each entry in `data.ambiguous`, keep only candidates that are the same
   measurement (analyte, specimen, property) and check them against the maps (`plsi maps show <id>`, `accepts.codes`):
   - all kept candidates are accepted by the same coordinate: pick the most specific one yourself (method, e.g. "by
     Automated count") and do not ask;
   - none is accepted by any map: pick the closest match yourself (specimen as printed; a routine chemistry panel
     without one is serum or plasma) and name it in the `result`; do not ask;
   - they fall on different coordinates: add the choice to the step's `question` (step 4), with only those
     candidates and what each one would mean.
   Medications, supplements, conditions and allergies: pick the code yourself, or leave the item uncoded; never
   ask the user to choose one. Never offer a code for a different measurement (e.g. reticulocyte width for RDW). Write the chosen `code` into the
   output file.

   ```bash
   plsi normalize observations --in obs.json --out obs.norm.json
   ```

4. Dry run, then send ONE `question` handoff to PLSI that lists the items ("Record these 14 results from 14 Sep 2026?"
   Record / Edit / Cancel) together with every open code choice and uncertain date; ingest after the `answer`. "Edit"
   comes back with the user's corrections as text: apply them, dry-run again and ingest without a new question unless
   the corrections raise a new code choice or date. Ingest
   without asking only when the request names a standing approval, quotes the user's own words asking to record
   these items, or quotes their earlier card answer on this thread; a consent line without a quote is not consent:

   ```bash
   plsi ingest --instance <instance> --file obs.norm.json --dry-run
   plsi ingest --instance <instance> --file obs.norm.json
   ```

5. **Project and return.** Any ingest or retraction makes every saved state stale: project the maps that cover the
   new items and every map already listed in `plsi status` `states`, then send ONE `result` to PLSI:
   ingested/duplicate/rejected counts, every projected map in `states` with its hash, what changed and the gaps (from
   `data.storyline`), and the coded measurements no map reads (by name, for a `processor/add-map` offer). Do not
   interpret them: PLSI hands the new `states` to PLSI Health Consultant (`consultant/assess`).
   A cancelled `answer` still gets a `result` saying nothing was recorded.

   ```bash
   plsi status --instance <instance>
   plsi maps select --instance <instance>
   plsi project --instance <instance> --map <map_id>
   ```

### Free text in chat

Build the same ObservationInput list with `origin: {"kind": "grok_extraction"}` and `effective_basis: "user_stated"`, then steps 3-5 (or pipe it with `--file -`).

The user says they have none (no allergies, no medications, no conditions): record one item of that kind with
`original_text` "None reported", `value_bool: false` and `clinical_status: "resolved"`, so `care_context` reads the
set as present and empty, not missing.

If the date is uncertain, add "When was this measured?" to the step's `question` handoff:

| Answer | `effective_at` | `effective_basis` |
|---|---|---|
| Today | today | `user_stated` |
| This week | today minus 3 days | `user_stated` |
| This month | today minus 15 days | `user_stated` |
| Not sure | today | `assumed` (never scored, never a baseline) |

### FHIR bundle

```bash
plsi ingest --instance <instance> --fhir bundle.json --dry-run
plsi ingest --instance <instance> --fhir bundle.json
```

The bundle's Patient birth year and sex fill an empty instance; to replace existing values, put it in the step's `question` handoff first, then add `--update`. Items rejected with `IDENTIFIER_IN_TEXT` contained a name or identifier; re-enter them by hand without it. Confirm and return as in steps 4-5 (also for CSV and methylation).

### PLSI export

A JSON with `"kind": "plsi_export"` (a patient's shared PLSI data): write its `observations` to `obs.json`, dropping
`event_id`, `recorded_at` and `unit_original` from each, then steps 4-5 (`ingest --file obs.json --dry-run` as
usual). Its plans, scores and states are not imported.

### Canonical CSV

Header `effective_at,text,value,unit[,code_system,code,specimen,kind,fasting,dose_quantity,dose_unit]`; other columns are dropped (`data.dropped_columns`).
There is **no `dose` (wording) or `clinical_status` column**; `dose_quantity` and `dose_unit` go together. For `kind=lifestyle`, put only the stable habit name in `text`
(e.g. `Smoking`, not `Smoking 10 cigarettes a day`). Quantity, stop/resolve, and status changes belong in
ObservationInput JSON via `--file` (or chat extraction), using `dose` / `clinical_status` / `effective_end` as in
Lifestyle above — not in CSV `text`.

```bash
plsi ingest --instance <instance> --csv results.csv --dry-run
plsi ingest --instance <instance> --csv results.csv
```

### Methylation betas

Needs the clocks extra (`plsi doctor` shows `extras.clocks`). First column CpG id, one column per sample.

```bash
plsi ingest --instance <instance> --methylation betas.csv --sample <column> --effective-at 2026-09-14 --dry-run
plsi ingest --instance <instance> --methylation betas.csv --sample <column> --effective-at 2026-09-14
```

### Lifestyle (ongoing vs past)

Kind `lifestyle` with `origin.kind` `grok_extraction` (chat) or as extracted from a document. Always record the
observation in the log; current state comes from projecting `lifestyle_context` (step 5).

**Stable identity + dose (no new schema).** Uncoded set items are keyed by exact `original_text` (case-insensitive).
Put the **stable habit name** in `original_text` and any quantity / frequency / regularity in the existing `dose`
field (same string field medications already use). Do **not** bake amount into the text, or a later stop with the
bare habit name will not close the active item.

| User meaning | Record |
|---|---|
| Ongoing / current ("I smoke 10 a day", "I drink socially", vaping daily, on shift work) | `clinical_status: "active"`, no `effective_end`; stable `original_text` (e.g. `Smoking`, `Alcohol use`, `Vaping`, `Shift work`); put amount/frequency in `dose` when stated (`"10 cigarettes a day"`, `"social"`, `"daily"`) |
| Ended ("I quit smoking", "I stopped drinking") | Same `original_text` as the active row (read it from `plsi state show --instance <instance> --map lifestyle_context`); `clinical_status: "stopped"` or `"resolved"`; set `effective_end` to the stop date; `dose` optional |
| Explicit abstinence ("I don't drink") | Separate active item, e.g. `original_text` "Alcohol abstinence"; when the matching use item ("Alcohol use") is active, also record it `stopped` as in the row above. Never infer abstinence from silence |
| Preference only ("prefer red wine with dinner" as a constraint) | `preference` on `personal_context`, not `lifestyle` |

Examples (chat → ObservationInput fields):

- "I smoke 10 cigarettes a day" → `original_text: "Smoking"`, `dose: "10 cigarettes a day"`, `clinical_status: "active"`
- later "I quit smoking" → `original_text: "Smoking"`, `clinical_status: "stopped"`, `effective_end: <date>`
- "I drink socially" → `original_text: "Alcohol use"`, `dose: "social"`, `clinical_status: "active"`
- "I vape daily" → `original_text: "Vaping"`, `dose: "daily"`, `clinical_status: "active"`

**Amounts are measured items too.** A stated amount also goes in as a measured observation with its LOINC code,
dated to when it describes, so plans can predict on it: drinks per week `44940-5` (`/wk`; "6 a day most days" is
the weekly sum the user confirms, never your estimate), drinking days per week `81032-5` (`d/wk`), cigarettes per
day now `64218-1` (`/d`), the AUDIT-C total `75626-2` only from all three of its answers. Questionnaire totals
(PSS-10 `106860-0`, PHQ-2 `55758-7`) only from all of their items, as answered; body fat `41982-0` (or `77233-5` for
impedance) and grip strength `83174-3` / `83173-5` (the stronger hand, best trial) as measured.

After ingesting any `lifestyle` item, project `lifestyle_context` with the other fitting maps in step 5.

### Adherence and side effects

From PLSI Reviewer (`reviewer/review`) or the weekly check-in, relayed by PLSI. No dedicated kind exists; use these:

- Adherence: kind `intervention`, one item per action and period; `original_text` "adherence: <action> (plan
  <plan_id>)", `value_quantity` the count done, `unit` "sessions" or "doses", `effective_at` / `effective_end` the
  period, `value_text` "of <n> planned; gaps: <dates>". Record the counts as stated; unknown is not recorded.
- Side effect or adverse event: kind `symptom`, `original_text` the effect as stated, `effective_at` the onset,
  `clinical_status` `active` or `resolved`, `value_text` "reported during plan <plan_id>; action stopped: yes|no".
  The link to the action is the user's report, not a diagnosis.

Then steps 3-5.

### Correct or retract

Unless the request relays the user's words naming this exact item and its replacement, put "Retract <label> <value>
<unit> from <date> (replace with <new>)?" (Retract / Cancel) with the event ids and reason in the step's ONE
`question`; retract only after the `answer`.

```bash
plsi events list --instance <instance> --kind measurement --limit 50
echo '{"reason": "transcription error: wrong unit"}' > reason.json
plsi retract --instance <instance> --event <evt_id> --file reason.json --replacement fixed.json
```

Omit `--replacement` to withdraw without a replacement. Then step 5.

## Rules

- Always dry-run and get the user's confirmation (the `answer`, or a standing approval) before `ingest` or
  `retract`; one `question` handoff per request (every file and chat item PLSI sent together), never one per file or
  item.
- The `question` asks only what recording needs (items, a code choice between coordinates, dates): no follow-up
  questions about the items ("How is your knee now?"), no code ids or system names, and every part offers Edit or
  Change.
- `duplicate` results are already recorded; set `"repeat": true` only for a genuine repeat measurement with identical fields.
- `UNCODED` warnings: run `normalize observations` or choose a code; uncoded items never reach a map coordinate.
- Never put names, IDs, addresses, file names or paths in any field; `original_text` is the item label only (at most 200 characters).
- Never edit `events.jsonl`; use `retract`.
- Red flags: a result the lab marked critical, panic or call-back, an acute symptom or self-harm content gets a
  `red_flag:` line (`orchestrator/urgent`) in the step's ONE `question`, sent as soon as the dry run is done: put the
  open code choices in that same question as they stand rather than resolving them first, and never send a second
  question for them. Then wait for the `answer` as usual. Never set a threshold
  yourself; without a lab flag or verified source mark it `uncertain`. Record pregnancy, breastfeeding or an age under
  18 as a `note` and say so in the `result`, so PLSI can set the scope. Soft
  `caution: mood-screen-positive | ...` lines from Sleep or PLSI are recorded as a `note` the same way (they do not
  set hard `scope:`).
