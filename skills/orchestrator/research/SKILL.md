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
- "Spend <n>% of my weekly usage on research every day", the "Daily research" extra (`plsi.md` step 6.5) and each
  run of the "PLSI research" routine: **Daily research** below.
- "What is my research up to?": `plsi research index`, then the projects and `ready` notes in plain words.

Not this skill: "is <drug> right for me?" or "what should I do?" (Nostradamus, `nostradamus/plan`); a check of the user's own
values by an outside model (the oracle option on the plan's pick card, `orchestrator/conduct` step 7); role researcher
with Target Hunter on the team: target, repurposing and hallmark asks go to `targets/discover` or `targets/hallmarks`,
with steps 1-2 here for the topic and budget.

## Steps

1. **Topic.** Take the topic and the mode (`education` when the user wants to learn as it goes) from the user's
   words. No topic: send Citizen Researcher the `request` with `mode` and no topic; it replies with a `question` holding 3
   suggested questions. Show them on ONE card "What should we research?": each question as a curious non-scientist
   would ask it ("Could blocking <target> slow aging of the <tissue>?", not "<target> as a target in <tissue> aging"),
   plus "Teach me the basics of aging science" (education mode), with a typed answer allowed. Nothing goes to the
   user before this card: the card is the first message of the thread.

2. **Budget.** PandaOmics Agent (the `pandaclaw` oracle) runs are billed by Insilico and take a few minutes each;
   L-LLM, the PandaOmics tools and the literature are not counted. Skip this card when the user named a number of
   runs or set a standing research budget. `plsi keys status` shows no `PANDACLAW_BEARER_TOKEN`: budget 0, and say
   in one line that the note will use the other sources. Otherwise ONE card "How many PandaOmics Agent runs may I
   use? Each takes a few minutes and is billed by Insilico.": 1 run / 3 runs / 5 runs / None, free sources only.
   Dismissed, or left to PLSI ("you decide", "not sure"): None. PLSI never picks a billed run itself; only a number
   the user chose spends credits.

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

4. **Show the note.** Verify the `result`: `research-note.md` in `files`, a claim, a grade, a falsifier and the
   PandaOmics Agent runs used within the budget. Then ONE message with the note attached:
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
   Longevity Mothership (only when PLSI Challenger's Note mode said `worthy` and Explorer is on the team) /
   with Grant Writer on the team, "Draft a Mothership project proposal" and "Draft a grant proposal" (a typed
   answer names the funder), so no second card asks which kind / Done. The same card ends a target or field-map
   request. A `ready` note goes to Challenger (`challenger/challenge`, Note mode, the note and its graph items in
   `files`) before this card; `not yet` objections go back to Citizen Researcher on the same thread and the card
   offers Dig deeper / Done. Insights for the plan in the `result` go on without asking (Reviewer `reviewer/review` for an active
   plan, Nostradamus `nostradamus/plan` for a new option; `shared/team`, Research and insights).

5. **Next step.**
   - **Dig deeper:** a new `request` on the same thread with the note in `files`, the same mode and budget, and as
     the topic the note's "Next step" turned into a question about the first topic ("Which blood tests show
     <hallmark> changing with age?"), not a task; back to step 4.
   - **Share:** the `shared/team` **Research note to the Mothership** flow: a `request` to Explorer, skill
     `explorer/mothership` (Contribute), with the note in `files`, then the message file it returns to Data
     Controller (`controller/egress`); show only a `cleared` one. Draft the email:

     ```bash
     plsi mothership email --file <cleared message file>
     ```

     In plain words: what would be shared in one line ("One research note: <claim>, with 18 checked sources") and
     "It goes from your Grok email, so it is signed with your address; the Mothership replies there." Then ONE
     card "Send this note to the Longevity Mothership?": Send / Edit / Don't send. Send: email `to`, `subject` and
     `body` exactly as drafted from the user's Grok email; tell the user it went, and have Citizen Researcher set the
     note `submitted`. Edit: ask what to change in one chat line and send the user's words to Explorer. The
     Mothership's reply (receipt, then accepted or rejected with a reason) arrives in the user's Grok email: when you
     see it, or the user forwards it, tell the user the decision in one line and have Citizen Researcher set the
     note `accepted` or `rejected` with the reason.
   - **Done** or dismissed: close the thread.

## Daily research

Research that runs by itself on usage the user would not spend, for every role. Needs Citizen Researcher on the
team; without it, say so in one line and offer "Add PLSI Citizen Researcher?".

1. **Turn it on.** The share comes from the user's words ("5% a day") or ONE card "How much of your weekly Grok
   usage may research use each day?": 2% / 5% / 10% / Off. Keep "Daily research: <p>% of the weekly limit per day"
   in your permanent memory and create (or update) the ENABLED daily routine **"PLSI research"** on yourself, at an
   hour the user named or early morning their time. "Daily research off" disables it; a new share updates it. Tell
   the user in the same message that the first run asks what to research (one card); after that it is quiet unless
   it has something to show.
2. **Each run, quietly:**
   - an open thread with the user waiting on a card, or the user active in the last hour: stop for today;
   - read this Grok account's usage once: U, the share of this week's limit used, and the reset time. Only this
     account's meter counts. Headroom H = 100 - U. Stop for today when H < p + 10 (the user keeps at least 10% for
     themselves) or the included usage is used up; on-demand spending is never counted as headroom;
   - send Citizen Researcher one `request` (skill `researcher/research`, mode `daily`, thread `research-<date>`) with
     `summary` "Daily research: stop when this week's usage reaches <U + p>% (now <U>%). PandaOmics Agent budget: <the
     user's standing research budget, or 0>" and conduct it (`orchestrator/conduct`). U is read at the start of
     today's one run, so the run spends at most p% of the week whatever the day; the user's own use during the run
     counts against it too, which only stops it sooner.
3. **After the run:** `retire` ids go to Memory Hole (`memoryhole/prune`); `ready` notes go to Challenger (Note
   mode); `worthy` ones are offered for sharing as in step 5 (Share). Then at most ONE short message to the user:
   what the research did today in 1-2 plain lines and what is next, with the share card when a note is `worthy`.
   Nothing new, or the run stopped at the start: say nothing.
4. **No project yet:** the run's `result` holds Citizen Researcher's 3 topic suggestions; show ONE card "What should
   your daily research work on?" with them (typed answer allowed) and start the next run on the pick.

## Rules

- A research note is research, not advice: never turn it into a step for the user. A user who wants to act on it
  ("should I take it?"): when the note shows its subject only in trials, with no approved use in people, answer in
  one line from the note ("It is only being tested in trials so far, so I won't plan it") and offer ONE card "Look
  for a trial you could join?": Yes / No; Yes is the **Exploration** flow with `scout/trials` and the subject.
  Otherwise the **Plan** flow (`nostradamus/plan`) with the note's sources.
- Never exceed the budget the user chose; a timed-out PandaOmics Agent run counts and is never asked again.
- Nothing personal goes into a research request, a note or a contribution; the user's own data reaches the
  Mothership only through `orchestrator/mothership`. Research notes go only by the user's Grok email, never the
  relay.
- Past notes: `orchestrator/answer` ("What have I researched?").
