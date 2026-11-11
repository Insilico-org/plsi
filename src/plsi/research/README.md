# plsi.research

The research loop with just enough filing to resume, its projects, topics and budget, and the research note.
Files live under `<PLSI_HOME>/research/` (layout in `store.py`); the command table is `commands.py`.

`plsi research` subcommand -> module: `project` status (`--adopt` adopt) · `topic`, `reframe`, `budget` topics ·
`next` loop · `save` save · `status` status · `propose` propose · `discover` discover · `notes`, `check`, `mark`,
`retire` notes.

- `store` and `schema`: folders, topic and node files and the log; the fields each node kind carries; the text
  helpers every module shares (`parse`, `read_md`, `clip`, `search_counts`).
- `verdict` and `frontier`: the arithmetic code owns: independent lines, verdicts, the ranked queue of open work
  and what a topic already covers.
- `tuning`: every number the loop and the candidate commands are tuned by, the per-depth bars among them.
- `ledger`: one daily allocation shared by the active projects, a weekly ceiling charged from meter readings,
  and the day's reservations of billed runs.
- `loop` and `save`: the two calls a move makes. `cursor` says where the loop goes next and when a topic is
  finished, `working_set` is what one move is handed, `write` and `refusals` turn a save payload into node files
  or refuse it.
- `projects`: titled aims grouping topics and notes; any number are active, each with at most one active topic.
- `topics` and `status`: what the user runs and reads; `notes`: the note the Longevity Mothership receives;
  `propose` and `discover`: candidate topics from the record and from the literature, choosing nothing; `adopt`:
  research filed before projects, moved into project folders.

Imports run one way, from the command modules down to `store`, `schema` and `tuning`; nothing imports `status`.
