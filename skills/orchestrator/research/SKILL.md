---
name: research
description: Use as PLSI when the user wants to do citizen longevity research - spare credits, a target hunt, a repurposing idea, a question about a hallmark or a finding, or learning how aging science works - to frame the project, agree the PandaOmics Agent budget, run it through Citizen Researcher and show the research note with one next step.
---

# PLSI citizen research

Follow persona.md norms and `shared/team`. Owner: **PLSI**.
Citizen Researcher runs the session (`researcher/research`); PLSI frames it with the user, keeps the budget and
shows the note. Thread and ledger as in `orchestrator/conduct`. Citizen Researcher is a specialist: when it is not on
the team, research is off; say so in one line and offer "Add PLSI Citizen Researcher?".

## When to use

- "I have spare credits, let's research something", "find a target for <hallmark>", "could <drug class> be
  repurposed for <aging process>?", "what does the science say about <hallmark>?", "explain this finding".
- "Teach me how aging science works", "teach me how <aging process> works", "explain <hallmark or mechanism>": the
  same flow in education mode. With Citizen Researcher on the team, PLSI never answers these from its own knowledge.
  "No paid runs" or "free sources only" is budget 0 (step 2, no card).
- "Dig deeper" on an earlier note.
- "Spend <n>% of my weekly usage on research every day", "research this by yourself", the "Daily research" extra
  (`plsi.md` step 6.5) and each run of the "PLSI research" routine: **Daily research** below.
- "What is my research up to?", "how is my research going?": `plsi research status`, then the answer so far
  with its verdict in words, the budget and the top of the frontier (Daily research step 4).

Not this skill: "is <drug> right for me?" or "what should I do?" (Nostradamus, `nostradamus/plan`); a check of the user's own
values by an outside model (the oracle option on the plan's pick card, `orchestrator/conduct` step 7); role researcher
with Target Hunter on the team: a shortlist of targets goes to `targets/discover`, one named target to
`targets/evaluate`, a hallmark framing to `targets/hallmarks` (`shared/team`, **Target discovery**), with steps
1-2 here for the topic and budget. Those run on free sources and need no budget card at all when the user has
no PandaOmics key — say in one line that it will use the free sources and skip step 2. Their result ends with
steps 4-5 here like a note.

## Steps

1. **Topic.** Take the topic and the mode (`education` when the user wants to learn as it goes) from the user's
   words. Check both kinds of research before spending anything; Citizen Researcher cannot see the autoresearch
   store and the Autopilot cannot see the notes, so this card is where the two meet:

   ```bash
   plsi research propose --instance <name>    # says "the research topic '<X>'" or "the research note '<Y>'"
   ```

   A candidate `already_covered_by` a topic the loop has worked is not a fresh session: say what was found
   (`plsi research status --topic "<X>"`, the answer in words with its verdict) and offer to continue there
   instead. Otherwise pass the uncovered candidates to Citizen Researcher in the `request`.

   No topic: send Citizen Researcher the `request` with `mode`, no topic and those candidates; it replies with a `question` holding 3
   suggested questions. Show them on ONE card "What should we research?": each question as a curious non-scientist
   would ask it ("Could blocking <target> slow aging of the <tissue>?", not "<target> as a target in <tissue> aging"),
   plus "Teach me the basics of aging science" (education mode), with a typed answer allowed. Nothing goes to the
   user before this card: the card is the first message of the thread.

2. **Budget.** PandaOmics Agent (the `pandaclaw` oracle) runs are billed by Insilico to the user's own token and
   take a few minutes each; L-LLM, the PandaOmics tools and the literature are not counted. Skip this card when the
   user named a number of runs or set a standing research budget. `plsi keys status` shows no
   `PANDACLAW_BEARER_TOKEN`: budget 0, and say in one line that the note will use the other sources. Otherwise ONE
   card "How many PandaOmics Agent runs may I use? Each takes a few minutes and is billed by Insilico.": 1 run /
   3 runs / 5 runs / None, free sources only. Dismissed, or left to PLSI ("you decide", "not sure"): None. PLSI
   never picks a billed run itself; only a number the user chose spends credits.

3. **Run.** One `request` to Citizen Researcher, skill `researcher/research`, with the work folder in `files` and in
   `summary` the topic, the kind (target, repurposing, method, hallmark), the mode and "PandaOmics Agent budget: <n>
   runs". When Citizen Researcher asked for the topic, send the budget card first and then ONE `answer` with the
   picked topic and the budget together: it starts as soon as it has the topic. One line to the user, with the topic as a phrase
   ("whether <drug class> could slow <process>"), never the user's question pasted in: "Researching <topic> with
   up to <n> PandaOmics Agent runs; I'll send the note in about 30 minutes." (budget 0: "Researching
   <topic> from free sources; I'll send the note in about 15 minutes."; the Agent runs go at the same time, so the
   time does not grow with <n>; the same line and times for a target or field-map request, and for Dig deeper).
   This line is the thread's only message before the note; the same holds for the one-line answers in Rules.
   Only the topic leaves the computer, so no oracle consent card is needed; never add the user's values, goals or
   plans to the request. Citizen Researcher's oracle query (`ask.json` or `args.json`) goes to Data Controller
   (`controller/egress`) when it asks for clearance; relay the `cleared` result back before any run, and a
   `rejected` one back for a rewrite.

4. **Show the note.** Verify the `result`: the research note (`research/notes/research-note_*.md`) in `files`, a
   claim, a grade, a falsifier and the PandaOmics Agent runs used within the budget. A `ready` note goes first to
   Challenger (`challenger/challenge`, Note mode) with the note and its data files in `files`; `not yet` objections
   go back to Citizen Researcher on the same thread and the card below offers Dig deeper / Done. Then ONE message
   with the note attached:
   - what was found, in 2-3 plain lines from Citizen Researcher's summary, with no identifiers (trial or paper
     numbers, journal names) and no abbreviations; those stay in the note;
   - "How sure: " and, in words: High "well supported in people", Medium "supported, with gaps", Low "early or
     animal data", Speculative "an idea, not yet tested", Not found "nothing solid found", never the grade name
     itself; a claim that rests only on an AI model says so ("this comes from an AI model and has not been checked
     against data");
   - the main risk from the note's Risks, in one line;
   - what would prove it wrong, in one line;
   - "PandaOmics Agent runs used: <m> of <n>", with each timed-out run's link from Citizen Researcher (budget 0: no
     line).
   Then ONE card "What next?": Dig deeper (up to <n> more runs; budget 0: "Dig deeper") / Share it with the
   Longevity Mothership (only when Challenger's Note mode said `worthy` and Explorer is on the team) /
   with Grant Writer on the team, "Draft a Mothership project proposal" and "Draft a grant proposal" (a typed
   answer names the funder), so no second card asks which kind / Done. A target request's message attaches the
   target file and the dashboard Visualizer renders from Target Hunter's `target_<gene>.json` files
   (`visualizer/dashboard`, scope **target dossier**, or **target comparison** for a shortlist). The same card ends
   a target or field-map request; there Share is offered whenever Explorer is on the team, and picking it first sends the targets file
   (`targets_*.md`), its top candidates named, its data files and the subjects of target files already sent (from
   permanent memory) to Challenger in Note mode; only the `worthy` candidates go on as below, the rest listed under
   the report's `## Dropped` with Challenger's reasons. Insights for the plan in the `result` go on without asking (Reviewer `reviewer/review` for an active
   plan, Nostradamus `nostradamus/plan` for a new option; `shared/team`, Research and insights).

5. **Next step.**
   - **Dig deeper:** a new `request` on the same thread with the note in `files`, the same mode and budget, and as
     the topic the note's "Next step" turned into a question about the first topic ("Which blood tests show
     <hallmark> changing with age?"), not a task; back to step 4.
   - **Share:** the `shared/team` **Research note to the Mothership** flow: a `request` to Explorer, skill
     `explorer/mothership` (Contribute), with the note (or the targets file and its `worthy` candidates) and the
     data files in `files`, then the message file it returns to Data Controller (`controller/egress`); show only a
     `cleared` one. **Large files** (Explorer reports `TOO_LARGE_FOR_EMAIL`;
     a single file over 9 MB never goes): with `email` of `plsi refs show longevity_mothership_drive` unset, say in one line
     that those files cannot go yet and offer the note without them. Otherwise the file goes through the user's
     Google Drive, in a folder named **PLSI Mothership** that holds only Mothership files:
     - **Once:** the folder must be shared as Viewer with <that email>; nothing else in their Drive is shared. With
       the Google Drive connector, create the folder yourself if it is missing; then send ONE message: "Large files go
       to the Mothership through your Google Drive. Once, please share the folder PLSI Mothership (only this folder)
       as Viewer with <that email>, then say done." Remember permanently when it is done.
     - **Each file:** with the connector, upload it yourself (`UploadFile` into that folder, the file unchanged,
       `convertToGoogleFormat` off) and give Explorer the new file's id as its `drive_link`. Without the connector,
       send ONE message with the file attached: "Please upload this file, unchanged, into your PLSI Mothership folder
       and paste its link here", then the plain chat question for the link, given to Explorer the same way.
     Wait for Explorer's new message file. Tell the user in one line: "The Mothership reads the file from your Drive
     only if it is exactly this one, and keeps a copy only if a steward chooses to when accepting the note: keep it
     there, unchanged, for as long as you want the note's data to be available."
     Draft the email:

     ```bash
     plsi mothership email --file <cleared message file> --hash <package_hash from Data Controller's result>
     ```

     In plain words: what would be shared in one line ("One research note: <claim>, with 18 checked sources"; for a target file "Target report: <n> candidates,
     <symbols>, with 18 checked sources") and
     "It goes from your Grok email, so it is signed with your address; the Mothership replies there." When
     Explorer's result says hidden pictures were removed, add one line: "I removed <n> picture(s) hidden in the
     text; the Mothership takes no pictures. The text is unchanged." Then ONE
     card "Send this note to the Longevity Mothership?": Send / Edit / Don't send. Send: copy `attachment` unchanged
     into your `attachments/` folder as `research-note_<topic>_<YYYYMMDD>.json` (and `report`, when given, as
     `report_<topic>_<YYYYMMDD>.md`, and `bundle`, when given, as `research-files_<topic>_<YYYYMMDD>.zip`), then email `to`, `subject` and `body` exactly as drafted, with those files
     attached, from the user's Grok email (agent inbox); tell the user it
     went; for a research note have Citizen Researcher set it `submitted`, and for a target file, which has no status,
     keep "Sent target file <file name>: <subject>" in your permanent memory. Right after the send, create the routine **"PLSI Mothership replies"** or update it
     (`shared/team`, Mothership replies). Edit: ask what to change in one chat line and send the user's words to
     Explorer. The Mothership's reply (a receipt within minutes, then accepted or rejected with a reason, or a
     refusal) arrives in the user's Grok email and wakes that routine.
   - **Done** or dismissed: close the thread.

## Daily research

Research that runs by itself on usage the user would not spend, for every role. Needs **PLSI Research Autopilot**
on the team; without it, say so in one line and offer "Add PLSI Research Autopilot?". The Autopilot works one
topic move by move and keeps going across days.

**The two research bots do not depend on each other and never talk to each other.** The Autopilot owns the loop
(topic folder, cursor, ledger, graph, renders); Citizen Researcher owns asked sessions and notes. Everything
between them crosses through you: when the Autopilot reports a direction worth writing up, that is a card for the
user ("Write this up as a research note?"). With Citizen Researcher not on the team, say in one line that a note
needs it and offer "Add PLSI Citizen Researcher?"; never show a note, a Challenger review or a share option that
nothing can produce.

1. **Turn it on.** **What to research** and **how much it may spend** are the user's, and a routine cannot ask,
   so both are agreed here.

   - **The share** comes from the user's words ("5% a day") or ONE card "How much may research use each day?",
     which states what that comes to over a week:

     | | |
     |---|---|
     | 2% | up to 8% of your week |
     | 5% | up to 20% of your week |
     | 10% | up to 40% of your week |
     | Off | |

     The weekly figure is the **ceiling**, four days' worth of the daily share, and code enforces it. Say in one
     line under the card: "two limits, the daily one and the weekly ceiling, whichever comes first, and research
     always leaves you at least 10% of the week."

     Both numbers are free text; take whatever the user names ("1.5% a day", "15% a day but never more than 30%
     in a week", "as little as possible").

     ```bash
     plsi research budget --share 1.5                 # the ceiling stays four days' worth: 6%
     plsi research budget --share 15 --ceiling 30     # both named
     plsi research budget                             # what they are now
     ```

     A share above the ceiling is accepted with a warning (the first day would take the whole week's
     allowance); say that back to the user in their own numbers.
   - **The topic.** Start from what the record already says:

     ```bash
     plsi research propose --instance <name>          # add --online to read the Mothership findings ledger
     ```

     It returns candidates that each point at something real - an active medication or condition
     (`personal_case`), a State Map gap or a marker whose series moved (`personal_data`) - minus anything an
     existing topic covers. It chooses nothing.

     For the question from the field, ask the field, with the subject from what the user said or from the
     personal candidate they lean towards:

     ```bash
     plsi research discover --about "<the subject>"          # add --trials for what is being asked right now
     plsi research discover --about "<the subject>" --entity "@CHEMICAL_<Name>"
     ```

     **`well_studied` is what not to open a topic on; `candidates` is where a question is open**, each with its
     own PMIDs to rest the topic on. The counts are a model's reading, so the first Gather still retrieves and
     quotes. `resolved: false` means PubTator uses another name (pass `--entity`). It sees PubMed and the
     open-access subset only, so your own web search is the other half. Take one from the ledger with
     `propose --online` as well when you have it.

     Show ONE card "What should your daily research work on?" with three, **at least one personal and one from the
     field**, each as a curious non-scientist would ask it ("Could <the drug you started> be what is breaking your
     sleep?", not "adverse effects of <compound class> on sleep continuity"). A typed answer is allowed.
     Dismissed, or left to you ("you decide"): take the top candidate, prefer a personal one when the record has
     anything to offer, and say in one line which you took and that it can be changed at any time. Never leave
     the routine with no topic.

     ```bash
     plsi research budget --share <p>
     plsi research topic --new "<short title>" --question "<the question in chief>" --depth <d> \
       --kind personal_case --because "<why this question, now>" --rests-on "medication:<event>" --instance <name>
     ```

     `--kind` and `--because` are required, and a `personal_data` or `personal_case` topic must point at data that
     resolves.

   - **How thorough** (`--depth`). The share says how much research may spend; depth says how good an answer has
     to be before the topic is finished. Take it from the user's words and **never ask a second card for it**:

     | | what the user said | what it does |
     |---|---|---|
     | `fast` | "quickly", "just the gist", "is there anything in this at all?" | one source can answer a direction; the topic finishes on whatever it finds |
     | `standard` | nothing in particular — **the default** | an answer has to rest on something |
     | `deep` | "properly", "dig in", "I want to be sure" | every direction gets an explanation tested against the evidence, and nothing is called answered without two independent sources |
     | `exhaustive` | "leave no stone unturned" | the same bar, with more room to branch |

     Say it back in one line with the share ("a quick pass, 2% a day"). It is changeable at any time; a `deep`
     topic that could not replicate anything stops and says so, and the user may take it as it stands:

     ```bash
     plsi research topic --switch "<topic>" --depth standard   # lower the bar and carry on
     ```

   Then create (or update) the ENABLED daily routine **"PLSI research"** on yourself, at an hour the
   user named or early morning their time; each run sends the Autopilot a request (step 2). A new share is
   `plsi research budget --share <p>`: one number for all research, not one per topic, applied from the next
   move. Tell the user in the same message that it will be quiet unless it has something to show.

   **"Off" on the share card, and "Daily research off", are two actions**: `plsi research budget --share 0` *and*
   disable the routine.

2. **Each run, quietly:** an open thread with the user waiting on a card, or the user active in the last hour:
   stop for today. Otherwise send PLSI Research Autopilot one `request` (skill `autopilot/run`, thread
   `research-<date>`) and conduct it (`orchestrator/conduct`). It reads this account's usage itself, works move by
   move and stops when the day's allocation is spent. A `headroom` stop means the week, not the day, is nearly
   gone (research always leaves the user a tenth of it); tell it in those words.

3. **After the run:** the `result` says what the moves did, what changed verdict, what is at the top of the
   frontier and what went unspent. Then at most ONE short message to the user: what the research did today in
   1-2 plain lines and what is next. Nothing new, or the run stopped at the start: say nothing.

   `stop: off` means research has no share: do not report it daily; check that the routine is disabled too.
   `stop: stuck` means the first move never completed; nothing was closed, and it retries tomorrow.

   **A direction that has become a question about a gene or a drug target** may go to Target Hunter, with the
   user's role researcher and Target Hunter on the team: one `request`, skill `targets/evaluate`, with the gene
   and the question in `summary` and no personal data. What comes back is `plsi targets brief --gene <SYMBOL>` in
   `files`; pass it to the Autopilot in the next run's `request` (or to Citizen Researcher for a session) and say
   it is **database records with identifiers, not quotes**: the receiving bot retrieves any source it quotes and
   writes the node itself. Without Target Hunter, say so in one line and offer "Add PLSI Target Hunter?"; never show a target result nothing can produce.

   If the Autopilot says a direction has reached something worth writing up, that is ONE card
   "Write this up as a research note?" (Yes / Not yet), only with Citizen Researcher on the team. Yes starts the
   asked-session flow above with the topic, its question and the names and answers of the nodes it rests on (from
   `plsi research status --topic "<topic>"`) in the `summary`; from there the note runs as
   in steps 4-5. `retire` notes go to Memory Hole (`memoryhole/prune`).

4. **Showing progress.** "How is my research going?" at any time:

   ```bash
   plsi research status
   plsi research status --topic "<topic>" --full > <PLSI_HOME>/work/<thread>/research_status.json
   ```

   The second is for the dashboard: one `request` to Visualizer, skill `visualizer/dashboard`, scope **research
   topic**, with `research_status.json` in `files`. It costs nothing and shows both where the research stands and
   how it got there (what each move cost and bought); attach the HTML report it returns.

   Say the answer so far **with its verdict in words** - `supported` "well supported for now", `thin` "one line of
   evidence", `contested` "the sources disagree", `refuted` "ruled out", `untested` "nothing bears on it yet" -
   and what limits it. Then the budget as a fraction of today's allowance and the top of the frontier in plain
   words. Never a percentage of the research "done". Attach the dashboard.

5. **When a topic finishes.** **`answered`**: the question in chief has an answer and nothing is open under it.
   **`exhausted`**: it ran out of directions first. Tell them apart in the first line ("we have an answer" against
   "we ran out of ways to find out").

   Either way: 2-3 plain lines with the answer reached **and its verdict in words**, what was closed and why, and
   how much went unspent. Attach the dashboard (as in step 4). Then ONE card — "<topic>: here is what we found. Where next?"
   or "<topic> has run out of directions. Where next?" — with three or four options:

   - **one or two from `continue_with`**, as a curious non-scientist would ask them; continuing is
     `plsi research topic --switch "<topic>"`, and the next run opens the chosen direction;
   - **one from the user's own newer data**: run `plsi research propose --instance <name>` now, and a pick is
     `plsi research topic --new` with the kind, `--because` and `--rests-on`, as in step 1;
   - **"Research something else"** and **"Stop here"**; a typed answer is allowed. Stopping leaves the topic
     `done` or `parked`, resumable with its cursor intact.

   **Never pick the continuation yourself.**

6. **Reframing, before switching.** When the research has learned that the question itself was wrong (the
   Autopilot says so in `open`, or the user does):

   ```bash
   plsi research reframe --question "<how it should now read>" --because "<what changed it>"
   ```

   The old wording is kept and the graph is untouched. Say it back to the user in one line, with both wordings. A
   **new topic** is for a different question, not a better statement of this one.

7. **Switching topic.** `plsi research topic --switch "<name>"`; the one it leaves keeps its cursor. Topics never
   link to each other.

## Rules

- A research note is research, not advice: never turn it into a step for the user. A user who wants to act on it
  ("should I take it?"): when the note shows its subject only in trials, with no approved use in people, answer in
  one line from the note ("It is only being tested in trials so far, so I won't plan it") and offer ONE card "Look
  for a trial you could join?": Yes / No; Yes is the **Exploration** flow with `scout/trials` and the subject.
  Otherwise the **Plan** flow (`nostradamus/plan`) with the note's sources.
- Never exceed the budget the user chose; a timed-out PandaOmics Agent run counts and is never asked again.
- Nothing personal goes into a research request, a note or a contribution; the user's own data reaches the
  Mothership only through `orchestrator/mothership`. Research notes and target files go only by the user's Grok
  email, never the relay.
- Past notes: `orchestrator/answer` ("What have I researched?").
