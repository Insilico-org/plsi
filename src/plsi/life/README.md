# plsi.life

The Life layer: any modality in, code-normalized observations out, in a deidentified append-only event log per
instance. Commands are listed in `src/plsi/commands.py` (`plsi init`, `ingest`, `revise`, `retract`, `normalize`, `events`,
`instances`, `apple export`).

| Module | Role |
|---|---|
| `models` | `ObservationInput` (what the bot writes), the stored `Observation`, `Retraction`, the deidentified `Subject` |
| `deid` | profile `plsi-limited-v1`: subject fields, the 90+ rule, the FHIR Patient identifiers held in memory only |
| `store` | `EventStore`: subject.json and events.jsonl (appends under the instance lock), instances init/list/delete, events list |
| `importers` | JSON, FHIR, canonical CSV and methylation importers -> `Imported` (rows, rejections, warnings) |
| `ingest` | `plsi ingest` and `plsi retract`: dedupe keys, the monthly-mean conflict check, appends |
| `revise` | `plsi revise`: a new version of one source document against what it said before |
| `normalize` | unit spellings to UCUM, LOINC candidates (NLM Clinical Tables), RxNorm ingredients (`plsi.rxnav`) |
| `apple` | an Apple Health export ZIP -> daily CSV rows |

Rules:

- Life never imports `plsi.map` or `plsi.policy`. The shipped maps' coordinates are read as raw YAML through
  `normalize.shipped_coordinates()`.
- events.jsonl is never edited: every change is an appended event through `EventStore`; a retraction hides its target.
- Only `normalize` makes network calls, through `plsi.net`.
- Imports run one way: `deid` -> `models` -> `importers` -> `normalize` -> `store` -> `ingest` -> `revise`.
