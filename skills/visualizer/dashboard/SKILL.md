---
name: dashboard
description: Use as PLSI Visualizer when PLSI asks for a custom dashboard (trajectory brief, state now, plan review, life arrow, clinician brief, panel, research topic, target dossier or comparison) - build a DashboardPayload whose scope the requesting skill defines, render it with plsi report and return it to PLSI with a matching chart.
---

# PLSI dashboard

A dashboard is one self-contained HTML file rendered from a DashboardPayload
(`contracts/DashboardPayload.schema.json`); the scope below decides what goes in, the requesting skill decides which
scope. Rendering is read-only: never ask before building one. Clicks in the HTML never reach PLSI; every choice the
user makes about a dashboard is the question card PLSI sends with it.

## When to use

- `nostradamus/trajectory` returned `trajectory.json` (Plan flow, "where am I heading"): scope **trajectory brief**.
- The user asks how they are doing now, how a plan went, or for their life arrow.
- `orchestrator/physicians` prepared a visit summary, or `visitprep/brief` a pre-visit brief: scope **clinician
  brief**.
- `panel/overview` returned `panel.json` (physician role): scope **panel**.
- The physician asks for a report for a patient (physician role, `panel/clinic`): scope **patient report**, built
  for that patient and shown to the physician first.
- `lab/research` shows a research topic's progress or its finish (`research_status.json`): scope
  **research topic**.
- Target Hunter handed over one target (`target_<gene>.json`): scope **target dossier**; two to eight for "which of
  these": scope **target comparison**.

## Blocks

`markdown {text}` (no raw HTML) · `kv {items:[{key, value}]}` · `table {columns, rows}` (cell: text, number or
`{text, href, level}`) · `timeseries {series:[{name, unit, points:[{t, v, ref_low, ref_high, flag}], predictions:[{t, expected, low, high}]}]}` ·
`list {items:[{text, href}]}` · `timeline {now, events:[{t, t_end, label, kind: past|predicted, level: info|watch|high, probability,
detail, href}]}`.
`parts {items:[{label, value, tone}], unit}` (one whole in at most 6 parts, instead of a pie) · `meter {value, max,
label, tone}` (one share of its total) · `scale {unit, marks:[{label, value, tone}]}` (values on one number line, such as
ages) · `bars {unit, left, right, items:[{label, value, note}]}` (signed amounts around zero). A `kv` item with
`hero: true` (and `unit`) is the view's one large figure. Any block may name an `icon` (`patient`, `panel`, `visits`,
`lab`, `vitals`, `device`, `medicine`, `condition`, `diet`, `plan`, `follow_up`, `file`, `trend`, `alert`, `note`, `age`).

## Scope

| Scope | From | Blocks, in order |
|---|---|---|
| trajectory brief | `nostradamus/trajectory` | markdown (the brief, unchanged) · one timeseries block with two series per marker item, "<label>: current course" and "<label>: with plan" (each with the recorded points incl. `now`, so both start at today; `current` / `plan` level points as predictions; same prefix and unit share one axis, the plan dashed) · table "Two courses" (item, now, current course, with plan, basis; risks as `expected (low-high) %` by horizon) · list (sources, linked) |
| scenarios | `nostradamus/trajectory` (Scenarios mode) | markdown (the brief, unchanged) · one timeseries block per measurement item, one series per scenario ("<label>: <scenario>", the baseline solid, the others dashed) · one timeseries block "Chance of being alive" with each scenario's survival curve (age on the axis) · table "Scenarios" (scenario, each item at the horizon as `expected (low-high)`, life expectancy, median age at death, chance of reaching 80 and 90, years vs baseline, basis) · list (sources, linked) |
| state now | `consultant/assess` result | kv (as of, maps, gaps count) · table (coordinate, value, unit, reference range, date) · list (gaps and next measurements) |
| plan review | `reviewer/review` result | kv (plan, review date, decision proposed) · timeseries (observed vs predicted, with interval) · table (prediction, expected, interval, observed, score); with a `modify` proposal append the trajectory brief's markdown, timeseries and Two courses table |
| life arrow | `orchestrator/arrow` | timeline · markdown (the story) |
| clinician brief | `orchestrator/physicians` (visit) or `visitprep/brief` | markdown (one line: a patient-made summary for discussion, not a diagnosis or referral; from `visitprep/brief`: a pre-visit brief for the physician, not a diagnosis or order) · kv (as of, maps, active plans, open gaps) · table "Recent results" (coordinate, value, unit, date, reference range, change since previous) · table "Active plans" (action, start, prediction with interval and review date, score so far) · list "Questions to ask" (from `visitprep/brief`: "To cover"); a timeseries only for a trend a question is about |
| panel | `panel/overview` | kv (as of, patients, per group count) · table "Needs attention" (label, group, reason, since, next), red flags first · table "On track" (label, last update) |
| research topic | `lab/research` (`plsi research status --full --project <id>`) | markdown (the question in chief; the answer so far with its verdict in words and what limits it: `limited_by`, `ruled_out`, `nothing_found_for`; no answer yet: "No answer yet") · timeline "Moves" (one past event per log row with a `move`: label the move and its question, detail what it cost (`cost.delta`) and what it changed (created, closed, verdicts flipped), level `watch` when not `productive`; `day` and `stop` rows as info events) · kv (verdict, depth, spent today of the allocation, spent this week of the ceiling, moves by kind, what the spend bought from `progress.segments`) · table "Evidence" (hypothesis, for or against, origin, design, findings, source ids from `sources`; the `set_aside` findings as "set aside") · table "Open frontier" (question, verdict, gap, why) · list "Closed directions" (each with its reason). Never a percentage of the research done |
| target dossier | Target Hunter (`plsi targets show`) | markdown (the verdict with its three ratings and the rationale from `assessment`, or "Not assessed yet") · kv (gene, name, Ensembl id, UniProt, indication, gathered, development level with its `evidence`, band with `band_basis`, furthest stage here and anywhere) · table "What the records say" (read, value, what it means: unread sources first as "not read", then structures (co-crystals, read of deposited), chemistry, genetics, safety and essentiality, aging (animal and human apart), assets in development (a floor), trials from the assessment's `harvested_assets`) · table "Risks" (dimension, rating, evidence, mitigation) · list "Open questions" (`open_questions` and `disagreements`) · list "Sources" (every id the assessment cites, linked to its record) |
| target comparison | Target Hunter (`plsi targets show` per target) | markdown (the question, then one line: "Compared side by side, never ranked: the rows share no unit") · table (one column per target in the order named, one row per read: band, furthest stage here, modalities, co-crystal, chemical matter, genetics, aging link, assets, verdict, the three ratings, falsifier; a last column "differs" marks each row whose values are not all equal; an unassessed target's judgment rows say "not assessed") |
| patient report | the physician, for one patient (`panel/clinic`) | markdown (the physician's own message, unchanged, or none) · table "Since your last review" (results dated after the roster row's `reviewed` date, each with its previous value; a value replaced by a new version of a report says "corrected", not "changed"; no `reviewed` yet: "First report: there is no earlier review to compare with") · one timeseries per trend the physician picked, with one plain line under them: "Each result is compared with the range printed on its own lab report; blank months had no data" · table "Your recent results" (test, value, unit, date, the range and the lab's flag printed on that report) · table "Your medicines" only when the physician asked (name as written, current / past / not sure: a past or unclear one is never shown as current) · list "Next steps" (only what the physician stated) · last, one line: "A summary of your records that your physician reviewed with you; not a diagnosis or a treatment plan." Plain words a patient reads without help: no codes, map or coordinate ids, hashes, model names, confidence labels or internal terms; no number that is not a recorded value or one the physician stated; nothing about other patients |

Order is fixed: the takeaway first, pictures next, tables and sources last. At most 6 blocks.

## Steps

1. **Collect** the requesting bot's file named in PLSI's request (`work/<thread>/trajectory.json` etc.) and the recorded data:

   ```bash
   plsi export --instance <instance>
   plsi due --instance <instance>
   ```

   Scopes **research topic**, **target dossier** and **target comparison**: only the file PLSI names
   (`research_status.json`, `target_<gene>.json`), written from the commands in the Scope table; render them on the
   user's own instance (relation `self`), `subject_id` the topic name or the genes.

   Scope **panel**: `panel.json` and `plsi instances list` instead; the payload is rendered on the physician's own
   instance and holds patient labels and the physician's own handles (roster `handle`) only, never full names. Its
   values stay in that report until a patient is
   forgotten: name the report path in the `result` so `memoryhole/forget` can find and delete every panel naming
   the patient.

2. **Write** `<PLSI_HOME>/work/<thread>/dashboard.json`, copying values from those files only:

   ```json
   {"kind": "plsi_dashboard", "schema_version": 1, "title": "Where you are heading", "subject_id": "<subject_id>",
    "generated_at": "2026-10-21T09:00:00Z", "blocks": [
     {"type": "markdown", "title": "In brief", "data": {"text": "..."}},
     {"type": "timeseries", "title": "Biological age gap", "data": {"series": [
       {"name": "Biological age gap: current course", "unit": "years", "points": [{"t": "2026-09-14", "v": 2.1}],
        "predictions": [{"t": "2027-01-19", "expected": 2.1, "low": 0.6, "high": 3.6}]},
       {"name": "Biological age gap: with plan", "unit": "years", "points": [{"t": "2026-09-14", "v": 2.1}],
        "predictions": [{"t": "2027-01-19", "expected": 1.1, "low": -0.9, "high": 2.6}]}]}}]}
   ```

3. **Render** and keep the `uri`:

   ```bash
   plsi report --instance <instance> --payload <PLSI_HOME>/work/<thread>/dashboard.json
   ```

   Scope **clinician brief**: also render the same payload with `--format pdf` (a static A4 copy for e-mail) and
   return the PDF path next to the HTML one in step 5. Scope **patient report**: render the PDF only (it lands in
   the patient's own `reports/`); the `result` names the work for Data Controller (`controller/egress`, kind
   "patient report"); PLSI shows only a cleared PDF to the physician on one card (Approve for the patient / Edit /
   Don't share), and only an approved file goes to `panel/clinic` step 5.

4. **Chart for chat.** Draw the same data as one PNG following `visualizer/charts` (trajectory brief: both courses
   on one axis per item, bands for intervals, the plan course lighter and dashed). The research and target scopes
   have no PNG: the HTML report is the file.

5. **Return** to PLSI in one `result`: the brief, the PNG path and the HTML report path (`uri`). PLSI sends them, in
   this order, as one turn: the brief with the PNG, the HTML report as a chat attachment and, last, in the Plan flow,
   the single adoption card (PLSI's `orchestrator/conduct` step 7). If rendering fails, say so in the `result`; PLSI
   never sends the adoption card without the PNG and the HTML report.

## Rules

- Never in a dashboard: names, places, employers, raw record text or inbox file contents, numbers not in a bot's file
  or the export, points without their interval, intervention names beyond the plan's action labels (the research
  and target scopes: beyond those in the topic's or the dossier's own file), secrets.
- Level-only items go in the table as "not predicted", never as a drawn line.
- `change_from_baseline` points go in the Two courses table only, never on a level timeseries.
- Target scopes never show a composite score, a probability of success, a rank, a "best" or a total across rows; a
  sample carries its denominator (`n of N`, read of deposited); a source in `unread` is "not read", never 0.
- One dashboard per thread step; regenerate rather than edit an old report.
