---
name: run
description: Use as PLSI Research Orchestrator on every run of a project's "PLSI research · <project>" routine, and whenever the user asks for one more move on a topic - read the cursor, do the one move that is due, save it, and stop when the day's allocation is spent.
---

# One move

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Orchestrator**. Read `shared/research-graph`
before the first save of a run.

The routine runs with nobody there, so a run **cannot ask a question**: which topic and how much of the meter were
agreed with the user (`lab/research`, Daily research step 1), and you work on what the cursor says.

## The loop

1. **Read the meter**: `U`, the share of this week's limit used on this Grok account. Only this account's meter
   counts; on-demand spending is never headroom.

2. ```bash
   plsi research next --usage <U> --project <id>
   ```
   It answers with the question in chief, the current question, **the move that is due**, the budget, the ranked
   frontier and the working set. A `stop` instead ends the run:

   - **`budget`**: the day's allocation is spent. Say what is unspent and what you did not get to.
   - **`answered`**: the question in chief is answered and nothing is open under it. Render the report and hand
     everything on.
   - **`exhausted`**: the frontier is empty and three moves opened nothing new, **or** every direction is
     resolved and no answer reached the topic's `depth`; `why` says which. On the second, lead with the answer
     reached and its verdict, and pass on the stop's line for taking it as it stands - lowering the bar is the
     user's call.
   - **`done`**: the topic was already finished. Report the answer.
   - **`ceiling`**: research has used its weekly share. Resumes when the meter resets.
   - **`headroom`**: research would take the user below the tenth of the weekly meter it always leaves them.
     Resumes at the reset.
   - **`off`**: the user gave research no share. Report only that.
   - **`parked`**: the topic is not active; `why` says whether the user stopped it or it ran out of directions.
   - **`no_topic`**: this project has no active topic. Run the stop's `propose` and follow its `then`: the card is
     `lab/research` Daily research step 1's "What should your daily research work on?", posted in the project's room
     for the user to answer later; an unanswered card from an earlier day (this one, or the project's finished
     topic's cards; each project counts its own) means taking the top candidate (`plsi research topic --new
     --project <id>`, as in step 1) and saying in one line which it is and that it can be changed at any time. Never
     a second card.
   - **`stuck`**: the topic's first move never saved; nothing was closed, and the next run retries it.
   - **`meter`**: a reading went below the one before it (`saw` after `after`). Code cannot tell the weekly reset
     from a low reading, so only the user can. When the user asked for this move, ask ONE card "Did your weekly
     Grok usage just reset?" (Yes / No). Yes: run the stop's `if_reset` command, then back to step 2. No: read the
     meter once more; still lower, stop for today and say so. In the routine nobody is there: end the run with one
     line naming both readings, and the card for the user to answer later.

   `answered` and `exhausted` are a report, not a failure: pass on `answer`, `answered`, `closed` and
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
   **Always pass `usage`**: read the meter again after the move and put the reading in the payload. A save
   without it is refused. A refusal lists every violation and writes nothing; fix them all and save again.

5. **Back to step 2** until a `stop` comes back. The cursor remembers where you are, so the routine may fire
   once a day or several times.

## When it stops

Back to `lab/research` (Daily research step 3) with what the moves did in plain words, the verdict of anything
that changed, the top of the frontier, the budget spent and left, and **what you did not get to**; the topic's
dashboard is drawn from `plsi research status --full --project <id>`. On `exhausted`, lead with the answer reached, then the
`continue_with` options as they came. Nothing new, or a stop at the start: nothing to say.

**The loop writes no notes.** A direction that has reached something worth writing up or sharing is a card for
the user, naming the question and its verdict; the user decides. Never turn a finding into a step for the user.

## Rules

- **One move per `next`**: the budget is charged per move and the cursor moves only on a save.
- Three attempts at the same move without a save close the direction as stuck (`gave_up_on` in the next reply).
  If a move will not complete, save what you have with `open` filled in.
- **Obey the stop.** A save past the allocation is warned about and counts against the week's ceiling. Use `budget.affordable`
  to land on the allocation, and never quietly hand the rest back.
- Nothing personal leaves the topic folder; nothing from it goes to the platform without Data Controller.
