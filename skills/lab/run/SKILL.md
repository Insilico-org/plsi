---
name: run
description: Use as PLSI Research Orchestrator on every run of the "PLSI research run" routine (and the run in place a "PLSI research watchdog" check asks for), and whenever the user asks for one more move on a topic - start the run, do the move that is due, save it, and go on until code says stop.
---

# One move

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Orchestrator**. Read `shared/research-graph`
before the first save of a run.

The routine runs with nobody there, so a run **cannot ask a question**: which topic and how much of the meter were
agreed with the user (`lab/research`, Daily research step 1), you work on what the cursor says, and what needs the
user later goes to the research inbox (`lab/research`, Daily research step 8).

One run, one project: code picks it. The meter is read twice, at the start and at the end, and code spreads the
run's rise over the moves it saved.

## The loop

1. **Read the meter**: `U`, the share of this week's limit used on this Grok account. Only this account's meter
   counts; on-demand spending is never headroom. Then start the run:

   ```bash
   plsi research run --start --usage <U> --kick '<the run's JSON body as it came, or nothing>'
   ```

   It answers with the run's id, the project (its id and title), its `room`, the time box (`time_box_minutes`,
   about 10) and the project's first `next`. A stop instead (`busy`, `stray`, `rest`, `idle`) ends the run with
   nothing posted. When the user asked for one move outside a run, skip this: read the meter and pass `--usage
   <U>` to `next` and in the save.

2. ```bash
   plsi research next --project <id>
   ```
   Inside an open run it needs no `--usage`. It answers with the question in chief, the current question, **the
   move that is due**, the budget, the ranked frontier and the working set. A `stop` instead ends the moves; go
   to step 6:

   - **`time_box`**: this run has had its minutes (`time_box_minutes`). The next run carries on from the cursor.
   - **`budget`**: this project's part of the day is spent.
   - **`answered`**: the question in chief is answered and nothing is open under it. Render the report and hand
     everything on.
   - **`exhausted`**: the frontier is empty and three moves opened nothing new, **or** every direction is
     resolved and no answer reached the topic's `depth`; `why` says which. On the second, lead with the answer
     reached and its verdict, and pass on the stop's line for taking it as it stands - lowering the bar is the
     user's call.
   - **`done`**: the topic was already finished. Report the answer.
   - **`ceiling`**: research has used its weekly share. Resumes when the meter resets.
   - **`quota`**: the weekly meter reached 85%, the hard cap at which all research stops, whatever share or
     ceiling is left. Resumes when the meter resets. Follow Quota below.
   - **`headroom`**: research would take the user below the tenth of the weekly meter it always leaves them.
     Resumes at the reset. Tell the user in plain words: "Research uses only your plan's weekly allowance, never
     prepaid or on-demand credits, so it stops when the weekly meter is nearly full, even if you still have
     credits."
   - **`off`**: the user gave research no share. Report only that.
   - **`parked`**: the topic is not active; `why` says whether the user stopped it or it ran out of directions.
   - **`no_topic`**: this project has no active topic. Run the stop's `propose` and follow its `then`: the card is
     `lab/research` Daily research step 1's "What should your daily research work on?", posted in the project's room
     for the user to answer later (the inbox tells them it is there); an unanswered card from an earlier day (this
     one, or the project's finished topic's cards; each project counts its own) means taking the top candidate
     (`plsi research topic --new --project <id>`, as in step 1) and saying in one line in the room which it is and
     that it can be changed at any time, then back to step 2. Never a second card.
   - **`stuck`**: the topic's first move never saved; nothing was closed; the project stops for today and a run
     on a later day retries it.
   - **`meter`**: a reading went below the one before it (`saw` after `after`). Code cannot tell the weekly reset
     from a low reading, so only the user can. When the user asked for this move, ask ONE card "Did your weekly
     Grok usage just reset?" (Yes / No). Yes: run the stop's `if_reset` command, then back to step 2. No: read the
     meter once more; still lower, stop for today and say so. In a run nobody is there: go to step 6; the inbox
     asks the user (needs you).

   In a run, each report above is the room line and the inbox, never a message of its own; the `no_topic` card is
   the one thing a run posts besides its line. `answered` and `exhausted` are a report, not a failure: pass on `answer`, `answered`, `closed` and
   `continue_with` for the card that asks the user where to go next (`lab/research`, Daily research step 5).
   Never pick the next direction or topic yourself.

3. **Do that move, and only that move**, following its page: `lab/ask`, `lab/gather`, `lab/explain` or
   `lab/test`. Read on demand only: `lab/deep-search` when a search comes back thin, junk or empty, and
   `lab/good-hypothesis` when candidates feel weak or a falsifier looks unreachable.

   The move and question are **recommendations**, ranked by how many moves a direction is from a verdict:
   ready to answer or candidates against evidence means Test, evidence with nothing proposed means Explain, unsearched means
   Gather, searched dry means Ask. Finishing outranks starting, and a question written today joins the bottom of the
   queue. Do what the research needs and name the question
   in the save if it is not the one suggested; the divergence is counted.

   `depth` and `answer_must_reach` on every `next` are the user's standard for the topic, already applied to the
   recommendation; do not change them. Read `already_tried` and each node's `note` before working: what earlier
   moves set aside or composed is there.

   Read the question in chief on every `next` and work towards it, not towards something adjacent.
   `topic_rests_on` is why the topic exists (a medication event, a marker that moved, source ids). On a topic's
   first move start from it. Its sources are leads, not evidence: retrieve and quote them like any other, and a
   source that does not say what was expected is itself a finding. One run is never deep; do not write as if it
   were.

4. ```bash
   plsi research save --file move.json --project <id>
   ```
   Inside an open run the payload needs no `usage`. Outside a run, **always pass `usage`**: read the meter again
   after the move and put the reading in the payload; a save without it is refused. A refusal lists every
   violation and writes nothing; fix them all and save again.

5. **Back to step 2** until a `stop` comes back; code says `time_box` when the run's minutes are up, so never
   watch the clock yourself. The cursor remembers where you are, so the next run carries on.

6. **End the run**: read the meter again and

   ```bash
   plsi research run --end --run <the run id --start gave> --usage <U>
   ```

   It charges the run, rebuilds the project's findings doc and asks for the next run itself (a `stray` stop: a
   later run already counted this one as dead; post nothing). Post its `room_line` in the project's room (`room`)
   and its `inbox` notice, if any, in your own chat (`lab/research`, Daily research step 8); then stop. With no
   `room`, find the project's room "<project title> · Project", save it with `plsi research project --room
   <destination> --project <id>` and post there; with no room at all, open it as `shared/sessions` says.

## When it stops

The room line is the run's report; the findings doc carries the rest. Outside a run (the user asked for a move),
back to `lab/research` with what the moves did in plain words, the verdict of anything that changed, the top of
the frontier and the budget spent and left; the topic's dashboard is drawn from `plsi research status --full
--project <id>`. On `exhausted`, lead with the answer reached, then the `continue_with` options as they came.
Nothing new: nothing to say.

**The loop writes no notes.** A direction that has reached something worth writing up or sharing is a card for
the user, naming the question and its verdict; the user decides. Never turn a finding into a step for the user.

## Rules

- **Never stop before code says stop** (a `stop`, `time_box` included): the share is a target to spend, not a
  ceiling, and a thin day is not a reason to end. **One run, one project**: never work another project's topic
  in a run.
- **One move per `next`**: the cursor moves only on a save.
- Three attempts at the same move without a save close the direction as stuck (`gave_up_on` in the next reply).
  If a move will not complete, save what you have with `open` filled in.
- **Obey the stop.** A save past the allocation is warned about and counts against the week's ceiling. Use `budget.affordable`
  to land on the allocation, and never quietly hand the rest back.
- Nothing personal leaves the topic folder; nothing from it goes to the platform without Data Controller.

## Quota

At 85% of the weekly meter code stops every run, in `run --start`, `next` and `run --end` (`quota`, with `then`
naming this section), so no project runs until the meter resets. The first time a week hits it, tell the user
(Research Orchestrator's own chat, and the user's single point of contact when there is one, `shared/hub` Chief of
Staff) with ONE card, multi-select, one option per project that is active now (`plsi research project`), at most
six (the rest on a second page):

> "Research is paused: your weekly usage reached 85%. These projects were running: <titles>. Which should resume
> when your quota renews?" (each project / None, keep them all on hold)

A project not picked goes on hold (`plsi research project --hold <id>`); a picked one stays active and simply waits.
Keep "Quota card: <week>" in your permanent memory and show the card once per week; an unanswered card leaves every
project as it is.

**When the quota renews**: the first `run --start` or `--end` after the meter reset carries `quota_renewed`
(`on_hold`: the projects on hold now). Send the message again: "Your weekly quota has renewed and research is
running again on <the active titles>. On hold: <titles>. Resume any?" (each project on hold / Not now), the same
two places; each pick is `plsi research project --resume <id>`. With nothing on hold, one line instead of the card.
