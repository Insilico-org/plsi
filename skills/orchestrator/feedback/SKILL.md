---
name: feedback
description: Use as PLSI when the user wants to tell the PLSI team how PLSI works for them - "compile a usage report", "what frustrated me in setup", "how long did setup take", "send feedback", "suggest improvements" - and at its offers (end of setup, then the weekly "PLSI feedback" routine) to write a usage report with the frustrations, the time per stage and suggested improvements, and send it from the user's Grok email to the Longevity Mothership's feedback address.
---

# PLSI usage report

The report is about PLSI, never about the user's health: it goes to the PLSI team by email, so it needs no Mothership
join and no token. Data Controller clears it before the user sees the send card (`shared/team` rule 6).

## When to use

- The user asks: "compile a usage report", "list what frustrated me", "how long did each step take", "send
  feedback to the developers", "what should the devs improve?".
- **Offers**, only when "Feedback on PLSI" is in the user's Mothership choice (setup 6.7, `orchestrator/mothership`
  step 1; kept in your permanent memory as "Feedback offers: on"), each as ONE short card "Help improve PLSI? I can
  send the PLSI team a short report of <what>.": See the report / Not now:
  - end of setup, once the record card is answered (`plsi.md` step 14): "how setup went". Right after it, create
    the ENABLED weekly routine **"PLSI feedback"** (an existing one is updated to this);
  - each "PLSI feedback" run: "your week with PLSI", the report built from this week's chats, thread ledgers
    (`orchestrator/conduct`, `failed` rows included) and `feedback mark/timeline`. The run stays quiet when nothing
    was marked that week (no stage timed, no frustration or `failed` row), or after two "Not now" in a row; then
    offer again only when the user brings it up or a month after the second "Not now".
  Keep the offers made and the "Not now" count in your permanent memory; a See the report resets the count. The user
  can always ask.

## Steps

1. **Compile.** From this chat and the thread ledgers (`orchestrator/conduct`), write `<work>/feedback-draft.json`:
   - `frustrations`: each moment the user was slowed, confused or annoyed (a question asked twice, a wait, an error,
     a card that did not fit, an answer they had to correct, a step they asked to skip), as {`stage`, `what`,
     `severity`}: `high` blocked or lost work, `medium` cost minutes or a retry, `low` a small annoyance;
   - `suggestions`: one concrete change for each frustration that has one, and the user's own ideas, as {`stage`,
     `what`};
   - `stages`, optional: estimated minutes for use stages (`records`, `plans`, `research`) as {`stage`, `minutes`,
     `measured`: false}; setup stages are timed by code.
   `stage` is one of `install`, `team`, `choices`, `interview`, `specialists`, `connectors`, `instance`, `routines`,
   `mothership`, `welcome`, `records`, `plans`, `research`, `other`. Each `what` is one plain sentence of at most 300
   characters, about what PLSI did: no names, health values, record content, dates, addresses or links. At most 20
   of each. Then:

   ```bash
   plsi feedback timeline
   plsi feedback report --file <work>/feedback-draft.json
   ```

   `report` adds the timed setup stages, checks the message and writes `usage-report_<YYYYMMDD-HHMMSS>.md` (the
   user's copy) and `.json` (the message). `GATE_FAILED`: rewrite the named entries and run it again.

2. **Clear.** A `request` to Data Controller (`controller/egress`) with the `.json` in `files` and "feedback report"
   in `summary`. `rejected`: rewrite the entries it names and run step 1 again.

3. **Show and ask.** ONE message with the `.md` from `report` attached: the total setup time and the longest
   stage, the top 3 frustrations and the top 3 suggestions, in plain words. Then ONE card "Send this report to the
   PLSI team? It goes from your Grok email.": Send / Edit / Just keep it. The user asked only for the report (no
   "send"): the same card. `email` is null (no feedback address set): no card; say the report is saved.

4. **Send.** Send: email `email.to`, `email.subject` and `email.body` exactly as drafted, from the user's Grok email;
   one line that it went; the routine **"PLSI Mothership replies"** is created or updated by the primary hub
   (another hub asks it hub to hub; `shared/hub`, Mothership replies): the Mothership's receipt or refusal arrives in the user's Grok email and wakes it. Edit: ask
   what to change in one chat line, apply it to the draft, then steps 1-3 again. Just keep it: one line with the file
   name.

## Rules

- Nothing is sent without the Send answer on that card; an offer is never a send.
- The report is written from what happened in PLSI, not from the user's records; a frustration that only makes sense
  with health data is written without it ("a lab report was read wrong", never the value).
- Never ask the user to fill in the report: they see the result and can edit it.
