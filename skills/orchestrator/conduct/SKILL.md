---
name: conduct
description: Use as PLSI for every task delegated to another bot on the team - plan the steps, dispatch each ready request (independent ones in parallel), wait for and collect the replies, verify them, re-prompt on gaps, chain the next steps and batch every user question into one card per decision point.
---

# PLSI conduct

Follow persona.md norms and `shared/team`. Owner: **PLSI**.

Handoffs between Grok Bots are asynchronous: the receiving bot wakes, works in its own chat and replies later; its
reply arrives in your direct-message chat with it later, and it may not wake you. Sending a request is not finishing a step; a step is
done only when you have collected and verified the reply.

## When to use

- Any user request that needs another bot (every flow in `shared/team`).
- A bot's `result` or `question` arrives, or the user returns to an open thread.
- The start of every turn: re-read the open ledgers first.

## Steps

1. **Resume.** Re-read the open ledgers before anything else: `<PLSI_HOME>/work/<thread>/ledger.md` (`plsi doctor`
   prints `PLSI_HOME`); a thread is open while any row is `sent`, `asked` or `retry`. Continue the open thread the user's message belongs to; mention other open threads in one line.

2. **Plan.** Check the user's words against `orchestrator/urgent` first: a red flag runs that skill; a plan, stack or
   diet change out of scope is declined in your first reply, and only recording and reports go ahead. Then pick the
   flow in `shared/team` and write the ledger: one row per step, before dispatching anything; `after` names the rows
   a step needs first (empty = ready now). Check every row's bot against the team (your permanent memory of the
   bots created at setup; core bots are always there). A row whose bot is not on the team is never dispatched: drop
   it and follow the missing-specialist rule (`shared/team`, Team). The user says yes to "Add <bot>?": run the add
   step in `plsi.md` for that bot only, then re-plan. When the user's message
   literally asks to record or save the items ("record these", "save them"), that is the consent for those items:
   quote the user's exact words in the request ("User's words: 'Record these events'"), no record card. Never write
   a consent line in your own words; anything less (a story, "continue it") gets the one record card.

   ```markdown
   | # | step | bot | skill | after | sent | status | result |
   |---|---|---|---|---|---|---|---|
   | 1 | record lab PDF | processor | processor/intake | | 2026-10-21 09:12 | sent | |
   | 2 | plan options | nostradamus | nostradamus/plan | 1 | | planned | |
   | 3 | test against history | challenger | challenger/challenge | 2 | | planned | |
   ```

   Status: `planned`, `sent`, `asked` (question with the user), `retry`, `done`, `failed`; a red-flag row
   (`orchestrator/urgent`) is `asked` with result `paused`; a reply filed during that pause is `received (paused)`.

3. **Dispatch every ready row.** A row is ready when every row in its `after` is `done`. Ready rows for different
   bots go out in the same turn, one request each (e.g. the specialists' proposals, `coach/exercise` and `sleep/sleep`, for
   one goal; `visualizer/charts` as soon as the data it draws is recorded); a bot gets one open request at a
   time, so a second ready row for the same bot waits. Check each request, send it as the message text **marked actionable (priority)**: Grok wakes the
   other bot only for actionable messages; informational ones wait for its next turn. Mark the row `sent` with the
   time and the message id of its request. A reply is a row's reply only if it is a Grok reply to that message id (not a handoff field); a
   reply to an earlier request on the thread is filed, not used. **Known before asked:** before a specialist,
   Nostradamus or a section bot gets a request in a Plan, Scenarios or Review flow, collect what the team already
   holds on the skill's topic and put it in `summary` as a `Known:` block, one fact per line with its date and
   source: `plsi state show` of the maps the skill reads, `plsi events list --instance <instance> --kind <kind>`
   for what no map holds yet (habits, consumption, symptoms), the interview and talk transcripts and other bots'
   notes (`<PLSI_HOME>/inbox/`), earlier threads' results (`work/*/`), connected sources (`plsi keys status`) and
   what the user said in this chat. The bot then asks only what is not there. Name standing
   approvals that apply in `summary` ("Standing approval: record lab results without asking"; the oracle approval:
   "Oracles: allow" / "ask each time" / "never"). When any worker `result` (especially Sleep) carries a `caution:`
   line in `summary` (`orchestrator/urgent`), copy that exact line into every subsequent request `summary` on the
   thread (Coach, Biohacker, Nostradamus, Challenger, …) until retracted; when it is not yet a recorded `note`,
   also pass it to `processor/intake` as a `note`. Soft caution is not a `red_flag:` and does not pause flows.

   ```bash
   plsi handoff check --file -
   ```

4. **Wait and collect.** Keep working in the same turn on what does not depend on the reply (write the next row's
   request now, with everything but the reply's content), then read the bot's replies. Never end a turn with a `sent` row unless you told the user in one line what is running, how long it
   usually takes and that you will report when it is back ("Drafting your plan, usually a few minutes; I'll report
   when it's back"). Say it once, when the thread starts; after that the user gets nothing until the next card or the
   final answer: no "drafting…", "almost there", "X is back, now Y" or "waiting on …" lines. **Depth cap:** at
   most 4 sequential hops (a dispatch you must wait on before the next; parallel rows count as one hop, a retry as
   one) between two messages the user sees. A chain that needs more sends ONE plain progress line after the
   fourth hop, saying what is done and what is left ("Your results are recorded and the plan is drafted; checking it
   against your history next"), and the count starts again. Send at most one message per turn, as its last step, never one before dispatching and
   one after; a turn woken by a bot sends nothing unless it carries a card, a recorded result, a depth-cap progress
   line or the final answer.
   Do not rely on being
   woken: before ending a turn with a `sent` row, check the bot's chat once more; if nothing, schedule the one-time
   check (Open-thread checks, below). When a reply arrives, find its thread ledger and row and go to step 5; never re-plan
   (step 2) a thread that has a ledger.

5. **Verify** the reply against the request before using it. A reply that only feeds the next bot (a proposal for
   Challenger, objections for Nostradamus, a plan for its checks) needs only the first two checks below: then add it
   to the request you prepared and send, in ONE shell call with the ledger update, without copying its files. The
   full list runs before anything reaches the user:
   - it is a `result` or `question` on the same thread, and `plsi handoff check` returns `ok`;
   - every cited state is current (no `STALE_STATE`) and every path in `files` exists;
   - it has the shape the skill promises (e.g. `nostradamus/plan`: `plan.json`, `findings.json`, predictions with a
     no-action control and `trajectory.json` whose every point in `current`/`plan` has expected/low/high/basis, level-only
     items carrying `"basis": "hypothesis_only"` at item level with empty `current` and `plan`, brief at most ~120
     words; `processor/intake`: ingested counts and the new `states`);
   - every option meets the request's constraints (area and radius, budget, scope); drop or label what does not
     ("outside your 50 km: Abu Dhabi, ~130 km");
   - nothing was done that needed consent the user had not given.

   A reply that asks for another bot's work (re-project, record items via `processor/intake`, `processor/add-score`) is not a
   gap: insert a row for that bot before the current one (not on the team: the step 2 "Add" line), dispatch it (recording only with the consent it needs,
   merged into the thread's next card). Re-send the original request with the new `states` only when the reply could
   not finish without that work (stale state, missing score, medications to record before screening); a finished
   result that only lists items to record is `done`, and its intake row is chained. A stale state is
   always fixed this way, never by re-prompting the bot that reported it.

6. **Re-prompt on a gap.** Send a `request` on the same thread naming the exact gap ("`findings.json` missing for
   a2"), mark `retry`. At most 2 retries per step; then mark `failed` and tell the user plainly what failed and why.

7. **Batch questions.** A `question` (or a `result` with `questions`) marks the row `asked`. First answer from the
   record every question it can answer, as in step 3's `Known:` block, and send those to the bot as `answers` with
   their source ("from events 2026-08 to 2026-10: about 40-42 standard drinks a week"); the user never gets a
   question the team can answer. While parallel rows of the thread are still `sent`, hold the questions until each
   of them has replied or asked (or 10 minutes passed), so the user gets one message for all of them, never one
   per bot. Show what is known in one line above the questions when it frames them ("On file: about 40 drinks a
   week, steps 8-12k a day"). Merge all open questions of the thread into ONE question card per decision point, add any consent that point needs (`persona.md`,
   Consent), and skip what a standing approval covers. When answers will be recorded, add "Record these answers" to
   the same card and pass that approval in the `processor/intake` request. Send each bot an `answer` with its own question
   ids and the user's words unchanged, then mark the row `sent` with the new time: it is waiting on the bot again.
   Stay within the card budget below. A card's question shows as one paragraph: put any list (items to record,
   options with their details) numbered above the card in the same message, one per line, and keep the card to
   a short question and its options. A Grok card holds ONE question (single- or multi-select): fold a decision point
   into one question whose options carry the combined choice ("Record all 9" / "Edit" / "Cancel"), and resolve
   everything a bot can decide before asking. Several open questions (habits, limits, baselines) go in ONE plain
   chat message, numbered, answered in one reply; never one card each. Never ask the user to type a keyword
   ("unknown", "skip", "n/a"): their own words count ("I can't find it on the label" means not known), and a fixed
   choice is a card option. Oracle consent is an option on the pick card
   ("Also send my values to <oracle> for a personal check"). The adoption card comes only after every question the plan still depends on is answered (doses from a label,
   a missing baseline), and only after Challenger's challenge and
   Nostradamus's one reply (objections go to Nostradamus without asking the user), and it is ONE short card: "Start the plan
   on 21 Oct, with the cautions above?" Start 21 Oct / Start 28 Oct / Change the plan / Not yet; no separate date or caution cards. Start
   proceeds on every caution shown; Nostradamus records the acknowledgements. "Change the plan" asks what to change in one
   chat line and sends the user's words to Nostradamus. The card comes in the message
   that carries the trajectory picture, the HTML report, the cautions in plain words (one line each) and each of
   Challenger's objections with Nostradamus's answer in one plain line. If an objection stops the prediction being scored, offer what fixes it ("Get a
   current BMI first"), never "adopt anyway". Write every card
   in plain words: no ids, map, skill or action names, one short sentence per caution. The same goes for everything
   you write to the user, including bot results you relay: rewrite them, never use the bots' shorthand ("uncoded",
   "coded", "scored", "baseline", "assumed", "bands", "hypothesis only", "dry run", "dose", "screened", "package",
   "panel", "chronological", "all-cause mortality", "primary prevention", "BP", "BMI", "OTC"); PhenoAge is "blood-test
   age" with its gap to the user's age ("50, about 4 years above your age"), naming PhenoAge at most once in
   brackets. Round numbers as a
   clinician would say them ("about 125 over 80", not "125/80.5"); each caution says what it means for them and what, if anything, to do ("We have only one
   blood-pressure reading, so we can't tell yet whether it's high; a week of home readings will show it"). A card cannot be withdrawn:
   an answer to a card of a closed or cancelled thread is filed, not acted on.
   **One open card at a time.** A newer card can leave an earlier one unanswerable, so never send a card while
   another is unanswered, on any thread: hold the next (its row stays `asked`, result `queued`) and send it after the
   answer. Record decisions that are ready together (chat items, a file, a device import) go in ONE record card with
   the lists numbered above it. An answered card is the consent: never ask it again in chat ("Should I write them
   now?"); quote the user's selection in the `processor/intake` or `wearables/import` request so the bot ingests
   without asking again.
   **Dismissed cards** (also Done with nothing selected) arrive as a message telling you to decide yourself. Do not
   re-ask, and never decide what needs the user:
   - a consent card (persona.md, Consent) dismissed = No: do nothing and say so in one line;
   - a choice leading to one (an option pick, which person, what to record) dismissed: stop the thread in one line
     ("Paused the plan; say 'show options' to pick later"), mark its rows `failed (dismissed)`;
   - any other choice (chart form, wording): decide yourself and say what you chose.
   Every multi-select card, whichever skill or setup step defines it, ends with "None of these" ("Not now" on a
   consent card).
   **Grok's own permission prompts** ("Allow PLSI to run a command?", "… save a routine?") that are skipped or expire
   mean the step did not run: say so in one line with what is still undone ("The deletion request was not sent; say
   'retry' to send it"), keep the row open, and never report the step as done.

8. **Chain.** Mark the row `done` with one line of result, then dispatch every row it made ready at once (step 3);
   do not ask the user whether to continue. Rows that ran in parallel are verified each on its own; the step that
   needs them all waits for the last. A reply that starts another row goes on in the same turn it arrives (the last
   specialist's proposal: all proposals to Challenger in one request). The user sees only: one line when the thread starts ("Recording the panel, then a plan;
   I'll come back with the options"), each card with its result in the same message ("Recorded: blood-test age 50, about 4 years above your age"),
   any depth-cap progress line and the final answer. Never narrate handoffs ("sending to the Data Processor",
   "Nostradamus is revising"); the ledger keeps them.

## Card budget

The decision points of each flow (`shared/team`, Flows). Each is ONE card (or one plain chat question) and counts
against the thread; a standing approval removes its card. Write the budget in the ledger's first line.

| Flow | Decision points | Budget |
|---|---|---|
| New record | record (items, codes, dates; plus active plans' adherence and side effects) | 1 |
| Plan | pick (options, or lifestyle gaps; plus oracle consent on "ask each time"), only when no option was chosen · adopt (cautions, start date, goals to record) | 2 |
| Record, then plan (the sample prompt) | record · pick · adopt | 3 |
| Review | adherence and side effects, only when not already answered · one decision per plan | 1 + plans |
| Life arrow | record the story · "Work on <risk>?" | 2 |
| Exploration | missing area, radius or budget, only when not in the user's request · pick | 2 |
| Research | topic and PandaOmics Agent budget, each only when not in the user's request · what next | 3 |
| Research loop | pick hypothesis and analysis budget · approve the cleared preregistration · approve the cleared finding | 3 |
| Wearables and food logs | prerequisites, OAuth client setup and authorize (each only on first connect or an expired token) · record | 1-4 |
| New score or importer | none: PLSI reports the new value | 0 |
| Panel review | a patient to prep, only when the physician picks one | 0-1 |
| Visit prep | none: PLSI shows the brief (the visit notes after it are a New record) | 0 |
| Forget, Mothership send, physician message, doctor-patient message | confirm (for a doctor-patient message, the cleared text) | 1 |

A bot's extra `question` beyond the budget is merged into the thread's next card, never asked on its own; ask it at
once only when the step cannot go on without it, and write why in the ledger row. Red flags and scope
(`orchestrator/urgent`) are outside the budget.

## Open-thread checks

Every routine run costs usage, even when it finds nothing, and creating one can ask the user for permission: keep
each routine cheap (read only what the run needs, stop at once when there is nothing to do) and make one only for
something the user chose or a flow needs. Open threads need no standing routine: schedule ONE one-time routine 10 minutes ahead only when a turn ends with a `sent` or `retry` row
still open, never at dispatch; each run re-reads every open ledger and schedules the next only if such a row is
still open. When only `asked` rows are left (cards with the user, a red-flag pause), schedule one check 24 hours
ahead instead, for the one reminder (`orchestrator/urgent` step 3). A reply waiting: continue at step 5.
A `sent`/`retry` row older than 15 minutes with no reply: send the
bot one nudge on the same thread ("Thread <id>: reply with your `result`, `question` or `in progress: <step>`") and
write `nudged <time>` in its result column. A `nudged` row with no reply after the next run: `failed`; tell the user.
An `in progress` reply resets the row's time once and clears `nudged` (`shared/team`). `asked` rows older than a day:
remind the user once. No nudges on a thread with an open red-flag row. Otherwise stay silent.

## Expert room

Every request starts hub and spoke: the specialists get their requests at once and work in parallel, and you merge
their proposals. When the brief already holds what they need, that is faster and costs fewer bot messages than the
room, for the same plan. Open the room only when, in that run, a specialist's `question` asks for another
specialist's fact, or two proposals conflict; its members are then only those specialists, and the others' proposals
stand. A user who asks for the room gets it.

1. **The room.** One Grok channel, "PLSI expert room", created once: check that it exists before creating it,
   never a second one, and never delete it (you cannot; the user removes it). A post that fails because the room is
   gone (the user removed it, or its id no longer resolves): create it again once and post; if that fails too, run
   the request hub and spoke and say nothing about the room. Members for this request: the
   specialists it needs, at most 5 bots; PLSI Challenger checks the merged plan afterwards in the usual flow, not in
   the room. The user's account can see the room, so every post is in plain words, without ids.
2. **Brief** (your post): the thread id, the question, a `Known:` block (step 3, the core facts and the topic), the
   limits (cautions, the user's goals), the result you need ("one dosed proposal each") and the order below. It
   @mentions every specialist at once, so they work in parallel, and says: "Your room post is your answer: also save
   it to `<PLSI_HOME>/work/<thread>/<your role>-proposal.md`, send no separate result, and post nothing after my
   close."
3. **One round, two at most.** Each specialist posts its proposal; only when it needs a fact that is not in the brief
   it first asks the colleague who holds it (@mention), and that colleague answers before posting its own proposal.
   A second round only for a conflict between two proposals. A member silent for 5 minutes gets one nudge in the
   room; silent at 10 minutes, it is left out of the summary and named in it. The room post and its proposal file
   are the specialist's result: there is no `result` handoff to wait for, so go to the close as soon as every member
   has posted (or the 10 minutes have passed). A `result` handoff that arrives anyway: file it, and do not dispatch
   again for it.
4. **Close** (your post): one summary of the proposals and any conflict between them; save the room's posts for
   this request to `<PLSI_HOME>/work/<thread>/room.md`; mark the room row `done` in the ledger and go on with the
   flow (`shared/team`, Flows). The close is the room's last post for this request: after it you post nothing more
   there (no lock-ins, corrections or thanks). A fact you still need from one specialist goes as a hub-and-spoke
   `request` to that specialist; a member's post after the close is added to `room.md` and not answered. Nothing is
   recorded or adopted in the room; the user hears the result only from you.

## Rules

- One open request per row and per bot; the ledger is the source of truth, not memory. The team list (bots created
  at setup, added or removed since) is kept in permanent memory.
- A research or Lab request (citizen research, a field map, a target hunt, a proposal): repeat the topic back in
  the one line that starts the work, and when it came by voice, or reads as outside health and aging, ask "Did you
  mean <topic>?" first.
- Never dispatch to a bot that is not on the team. Persona updates and setup messages go only to bots on the team.
- The user removes a bot: close its open rows as for a cancel (below), drop its `planned` rows (the step 2 "Add"
  line where the flow still needs one) and stop routing to it.
- Never send the same line twice in a turn; creating, updating or deleting a routine is not a reason to repeat the
  last message.
- Files for the user (reports, summaries, exports, packages, the consent text) go as chat attachments, which Grok
  shows with a download button; never as a `file://` link or a path, which opens nothing.
- A `red_flag:` line in any reply, or an emergency in the user's words: run `orchestrator/urgent` before verify or
  chain.
- A soft `caution:` line (e.g. `caution: mood-screen-positive`) in any reply: keep the flow; copy the exact line into
  later request `summary`s and record it as a `note` when missing; never treat it as hard `scope:` or pause all
  flows.
- Read-only and reversible work (reading, projecting, evidence searches, screening, drafts, reports) never waits for
  the user.
- Standing approvals the user grants ("record lab results without asking") are remembered permanently, listed when
  the user asks, revoked when the user says so.
- The user drops or changes the request: first stop your own pending actions at once (an open browser, a queued
  script or command), then send each bot with an open row one `request` on the thread ("Stop: thread
  <id> cancelled; reply with a `result` of what was done"), mark the remaining rows `failed` (cancelled by user) and
  file late replies without chaining.
- A bot that messages the user directly is corrected once with a `request` on skill `shared/team` (rule 2).
