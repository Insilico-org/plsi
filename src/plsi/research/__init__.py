"""Autoresearch: a research loop with just enough filing to resume.

- `store` and `schema`: the topic folder, its node files and log, and the fields each node kind carries.
- `verdict` and `frontier`: the arithmetic code owns (independent lines, verdicts, the ranked queue of open work).
- `ledger`: the budget, one daily allocation and a weekly ceiling charged from meter readings.
- `loop` (`research next`) and `save` (`research save`): the two calls a move makes. `cursor` says where the loop
  goes next and when a topic is finished, `working_set` is what one move is handed, and `write` and `refusals`
  turn a save payload into node files or refuse it.
- `topics` and `status`: what the user runs and reads (create, switch, park, reframe, budget; where a topic stands).
- `notes`: the research note the Longevity Mothership receives.
- `propose` and `discover`: before the loop, this person's record and the literature's relation annotations;
  neither chooses.
"""
