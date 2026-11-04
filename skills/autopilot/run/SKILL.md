---
name: run
description: Use as PLSI Research Autopilot on every run of the "PLSI research" routine, and whenever PLSI asks for one more move on a topic - read the cursor, do the one move that is due, save it, and stop when the day's allocation is spent.
---

# One move

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Autopilot**. Reply only in handoffs to PLSI;
never message the user. Read `shared/research-graph` before the first save of a run.

You run with nobody there and **cannot ask a question**: which topic and how much of the meter are agreed by PLSI
with the user, and you work on what the cursor says.

## The loop

1. **Read the meter**: `U`, the share of this week's limit used on this Grok account. Only this account's meter
   counts; on-demand spending is never headroom.

2. ```bash
   plsi research next --usage <U>
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
   - **`parked`**: the user stopped this topic.
   - **`stuck`**: the topic's first move never saved; nothing was closed, and the next run retries it.

   `answered` and `exhausted` are a report, not a failure: pass on `answer`, `answered`, `closed` and
   `continue_with` so PLSI can ask the user where to go next. Never pick the next direction or topic yourself.

3. **Do that move, and only that move**, following its page: `autopilot/ask`, `autopilot/gather`,
   `autopilot/explain` or `autopilot/test`. Read on demand only: `autopilot/deep-search` when a search comes back
   thin, junk or empty, and `autopilot/good-hypothesis` when candidates feel weak or a falsifier looks
   unreachable.

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
   plsi research save --file move.json
   ```
   **Always pass `usage`**: read the meter again after the move and put the reading in the payload. A save
   without it is refused. A refusal lists every violation and writes nothing; fix them all and save again.

5. **Back to step 2** until a `stop` comes back. The cursor remembers where you are, so the routine may fire
   once a day or several times.

## When it stops

One `result` to PLSI (PLSI has the topic's dashboard drawn from `plsi research status --full`): in `summary`, what the moves did in plain words, the verdict of anything that changed,
the top of the frontier, the budget spent and left, and **what you did not get to**. On `exhausted`, lead with
the answer reached, then the `continue_with` options as they came. Nothing new, or a stop at the start: one line.

**You write no notes and hand work to no bot.** If a direction has reached something worth writing up or
sharing, say so in the `result`, naming the question and its verdict; PLSI decides with the user. Never turn a
finding into a step for the user.

## Rules

- **One move per `next`**: the budget is charged per move and the cursor moves only on a save.
- Three attempts at the same move without a save close the direction as stuck (`gave_up_on` in the next reply).
  If a move will not complete, save what you have with `open` filled in.
- **Obey the stop.** A save past the allocation is warned about and counts against the week's ceiling. Use `budget.affordable`
  to land on the allocation, and never quietly hand the rest back.
- Nothing personal leaves the topic folder; nothing from it goes to the platform without Data Controller.
