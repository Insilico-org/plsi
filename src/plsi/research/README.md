# plsi.research

The research loop with just enough filing to resume, its projects, topics and budget, and the research note.
Files live under `<PLSI_HOME>/research/` (layout in `store.py`); the command table is `commands.py`.

`plsi research` subcommand -> module: `project` status (`--adopt` adopt; also `--hold`, `--resume`, `--room`) ·
`topic`, `reframe`, `budget` topics · `run` chain · `watchdog` watchdog · `inbox` inbox · `next` loop · `save`
save · `status` status · `propose` propose · `discover` discover · `notes`, `check`, `mark`, `retire` notes.

- `store` and `schema`: folders, topic and node files and the log; the fields each node kind carries; the text
  helpers every module shares (`parse`, `read_md`, `clip`, `search_counts`).
- `verdict` and `frontier`: the arithmetic code owns: independent lines, verdicts, the ranked queue of open work
  and what a topic already covers.
- `tuning`: every number the loop and the candidate commands are tuned by, the per-depth bars among them.
- `ledger`: one daily target shared by the projects still working today (a project that stops hands its part on
  to the others), the weekly ceiling and the user's headroom as hard stops, charged from meter readings at each
  run's start and end, and the day's reservations of billed runs.
- `loop` and `save`: the two calls a move makes. `cursor` says where the loop goes next and when a topic is
  finished, `working_set` is what one move is handed, `write` and `refusals` turn a save payload into node files
  or refuse it.
- `projects`: titled aims grouping topics and notes; any number are active, each with at most one active topic,
  and on hold ones keep everything but are never worked; each saves its room's destination.
- `chain`, `watchdog` and `runs`: the research chain. `research run --start` picks the project and `--end --run
  <id>` charges that run, rebuilds the project's `findings.md` (`findings`, from the status view) and asks for the next
  run by a POST to the "PLSI research run" webhook (through `plsi.net`, with the keys from `plsi.keys.get`); the
  hourly watchdog restarts dead runs and starts the day, and runs one in place while the webhook is missing or
  refused. Every run event is a line of `research/runs.jsonl`; each `next` and save inside a run logs a `beat`, so
  a run is dead only after 30 silent minutes, and `next` ends it with `time_box` after 10. The watchdog wakes the
  bot's computer once an hour but cannot keep it awake: Grok pauses it minutes after a routine run ends, so
  nothing in the chain may rely on a process that outlives a run.
- `inbox`: what unattended runs have to tell the user, once a day, with the question form that answers it
  (`research/inbox.json` keeps what was told).
- `topics` and `status`: what the user runs and reads; `notes`: the note the Longevity Mothership receives;
  `propose` and `discover`: candidate topics from the record and from the literature, choosing nothing; `adopt`:
  research filed before projects, moved into project folders.

Imports run one way, from the command modules down to `store`, `schema` and `tuning`; `runs` imports only
`store`, so `loop`, `save` and `ledger` can read the run log. Only `findings` imports `status`, and `status` and
`topics` import `chain` inside a function, to kick a run when they create work.
