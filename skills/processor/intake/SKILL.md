---
name: intake
description: Use as PLSI Data Processor when PLSI hands over health data the user shared (PDF, photo, typed values, FHIR export, CSV, methylation betas) or a correction or retraction of something already recorded.
---

# PLSI intake

## When to use

- The user sends a lab report, photo, discharge letter, device export, FHIR bundle, CSV or methylation file.
- The user states a value, medication, condition, allergy, symptom or habit in chat.
- The user states a goal ("run 10 km by June") or a standing preference ("vegetarian", "Budget: moderate"): kind `goal`
  or `preference`, `original_text` is the goal or preference itself, `effective_end` is the target date if any. A goal
  reached or dropped gets a new observation with `clinical_status: "resolved"`. They feed the `personal_context` map.
- Lifestyle habits and exposures (alcohol, smoking or vaping, shift work, abstinence): kind `lifestyle`. They stay in
  the event log and feed the `lifestyle_context` map when active (see Lifestyle below). Do not use `preference` for
  these. An occupation, job title or employment status is never recorded; a work exposure (shift or night work) is
  `lifestyle` without the job. Ethnicity, race or ethnic group is never an observation either: it is only the
  subject's field (`plsi init --ethnicity`, PLSI's setup).
- A recorded value is wrong or must be withdrawn.

## Steps

An instance `plsi` does not list yet (`INSTANCE_NOT_FOUND`, often mid-setup): record nothing and reply `blocked: the
record is not created yet` (`shared/team`, People and instances); PLSI sends it again once it exists.

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
   A result printed with its reference range gets `ref_low` and/or `ref_high` in the result's unit, exactly as
   printed on that report (it changes between labs and years; never fill it from elsewhere; "<5.2" is `ref_high`
   only), and the lab's own mark (H, L, HH or LL, critical, A or *) goes to `flag` (`high`, `low`, `critical`,
   `abnormal`).
   A file from the clinic sync (`panel/clinic`) gets `origin.document` = the Drive file id the request names, on
   every item.

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

   A name no candidate fits because it is misspelled or not in English ("Feritin", "Kreatinin", "Глюкоза"): run
   `normalize` again on a scratch copy of that item with only `original_text` spelled right in English
   ("Ferritin"), and take its code into `obs.norm.json`; the printed name stays in `original_text`. A code comes
   from a search, never from memory. Put the specimen in `specimen` when the report prints it apart from the name
   ("Urine", "Serum"), so urine results never get a blood code.

3b. **Sanity check, every item** (the auto-coded ones too): one row per measurement, where it would land.

   ```bash
   plsi calc place --instance <instance> --file obs.norm.json
   ```

   Read every row against the report: the printed name and `code_name` are the same test (total cholesterol is not
   LDL; HbA1c is not haemoglobin), on the same specimen (a urine result is never a blood one) and with the same
   timing (a fasting code only when the report says fasting); `lands_on` is that test. A row that fails gets a
   code of the right test from its candidates or a new search (above), and the check runs again. A `problem` row
   `unit: ...` is a unit PLSI cannot convert as printed. Reduce the doubt before asking: its `readings` (a slip fixed,
   a missing slash, a ratio printed as a concentration, each with the value it gives) and your own reading of a
   misprint (`mmo/L` is `mmol/L`) are checked against the report: its printed reference range, the test's usual
   values, the other results on the page. The one reading the report supports goes in `unit`, the printed unit in
   `unit_printed`, the value never changes, and the check runs again; the Record card shows it ("HbA1c 38 mmol/L,
   read as mmol/mol -> 5.6 %"). Two readings fit, or none: ask about that item in the step's `question` (step 4).
   No reading at all for a test that is right usually means another coordinate (Lp(a) in nmol/L is not the mass
   one; RDW in fL is RDW-SD): fix the code, not the unit. `no map reads this code`: recorded but not
   projected (a urine test, for now); list it in the `result` (step 5). Nothing is ingested while a row fails.

4. Dry run, then send ONE `question` handoff to PLSI that lists the items, each as printed with where it lands
   ("Total cholesterol 5.4 mmol/L -> total cholesterol"; "Record these 14 results from 14 Sep 2026?"
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
| Today | the current time (ISO datetime with offset), never a bare date | `user_stated` |
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

### Clinic tables

A CSV or spreadsheet from a doctor, clinic or lab, in its own layout (one row per test, or one column per test and
one row per visit; labels in its own words, abbreviations or another language). Rewrite it as the canonical CSV
above, or as `obs.json` when it has doses, statuses or reference ranges:
- one row per result: date, the label as printed, the value and unit as printed (never convert; the map converts);
  a range column goes to `ref_low`/`ref_high` and an H/L column to `flag`, never into `text`; the same result printed
  twice (same test, date and value) is one row;
- only the patient in the request: a column naming patients (an id, a name, a record number) that holds more than
  one person means only that patient's rows, and only when the column clearly says which, else ask; the column's
  values never go into any item;
- no unit printed for a test reported in more than one common unit (mmol/L or mg/dL): ask once per test, never
  guess the unit from the size of the value;
- a result in words ("positive", "trace", "see note") is `value_text`, never a number; an empty cell or "n/a" is no
  row;
- dates as printed: a day-month order you cannot tell from the file (03/04) goes in the step's ONE `question`, once
  for the whole file;
- a label that could mean two tests (glucose in serum or by meter, fasting or not) needs the specimen, fasting,
  method or body-site column (step 3 picks the code that carries it), else the question; a lab's or physician's own shorthand ("metx") is coded only once the physician confirmed
  it, and the confirmed meaning stays in your permanent memory per source;
- then step 3 (codes) and steps 4-5 as usual; with `origin.document`, a later version of the same file goes through
  `revise` below.

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

**A new version of a document** (a lab re-issued a report, a clinic table was shared again: `revised: true` from the
clinic sync, or the user says so): extract the **whole** new version as usual, then let `revise` compare it with
what that document said before. Unchanged rows are skipped, changed ones retracted and replaced, rows the new version
no longer has retracted, new ones added; a row of the new version that fails validation stops it (the dry run
lists it under `rejected`), so a value is never withdrawn by mistake. An amended-result notice that lists only the
changed results is not a new version: use Correct or retract above. Its dry run goes in the ONE `question` like any ingest ("The new version of
the lipid report changes triglycerides 1.5 -> 1.8 mmol/L and drops HDL. Apply?").

```bash
plsi revise --instance <instance> --document <file id> --file obs.json --dry-run
plsi revise --instance <instance> --document <file id> --file obs.json
```

## Rules

- Always dry-run and get the user's confirmation (the `answer`, or a standing approval) before `ingest` or
  `retract`; one `question` handoff per request (every file and chat item PLSI sent together), never one per file or
  item.
- The `question` asks only what recording needs (items, a code choice between coordinates, dates): no follow-up
  questions about the items ("How is your knee now?"), no code ids or system names, and every part offers Edit or
  Change.
- `duplicate` results are already recorded; set `"repeat": true` only for a genuine repeat measurement with identical fields.
- `UNCODED` warnings: run `normalize observations` or choose a code; uncoded items never reach a map coordinate.
- `FUTURE` warnings: the item is dated after now (a bare date is 12:00 UTC) and stays out of the state until then;
  a measurement from today is replaced with its time (`plsi retract --event <id> --replacement <json>`).
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
