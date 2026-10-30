---
name: nudge
description: Use as PLSI to remind and support the user between check-ins - physician follow-ups, measurement windows about to open, the first days of a new plan - from one reminders file and one one-time routine per reminder, at most one short message a day.
---

# PLSI reminders

Follow persona.md norms and `shared/team`. Owner: **PLSI**.

One file, `<PLSI_HOME>/reminders.md`, holds every reminder; each reminder has one one-time routine on its day. Other
skills add rows here instead of creating their own routines.

```markdown
| id | instance | what | due | remind_from | source | status |
|---|---|---|---|---|---|---|
| r1 | me | repeat lipid panel (bring the visit summary) | 2026-12-01 | 2026-11-27 | follow-up | open |
| r2 | me | walking plan: first week, 3 sessions | 2026-10-28 | 2026-10-22 | plan start | open |
```

## When to use

- `orchestrator/physicians` sets a follow-up (repeat test, next visit, referral).
- A plan is adopted: add a "first week" row for its first adherence target (`nostradamus/plan` result).
- The weekly check-in or a record card while a plan is active (Mid-plan check, below).
- `plsi due --all` shows a measurement window opening in the next 7 days.
- The user asks "what reminders do I have", "remind me to …", or "reminders off/on".

## Steps

1. **Add** a row per reminder. A date the user names is `remind_from`; for follow-ups and plan starts PLSI sets
   itself, use a few days before `due` (the day before for plan starts). Deidentify `what` as in persona.md: no
   clinic, physician or place names. Confirm in one line: what, and the one day it will appear.

2. **One-time routine per reminder**, no daily routine (every run costs usage): schedule it for `remind_from` at
   09:00 local. The run sends ONE line (what, by when, what to bring), adds any window from `plsi due --all` opening
   within 7 days, and marks the row `sent <date>`. Rows due the same day share one message.

   ```bash
   plsi due --all
   ```

3. **Support.** When the user replies with a struggle ("I missed two sessions", "it's too hard"), thank them in one
   line and pass it on as a mid-plan check reply (below); never change a plan yourself.

4. **Close** a row when the user says it's done or a matching record arrives (New record flow); mark it `done`. A row
   `sent` with no reply gets one more one-time routine 3 days later, then `expired`.

## Mid-plan check

For each active plan whose start date has passed (`plsi status --instance <instance>`); a plan not started yet gets
"starts <date>" or nothing:

- **Weekly line.** The check-in (plsi.md step 10) adds ONE line per plan, for the whole plan, not one per action, in
  plain words: "Your walking plan: how many of the 3 planned sessions this week, and any side effects?"
- **Record card.** A New record thread adds, per plan, to Data Processor's record card: missing measurements; per action the
  doses or sessions done of those planned since adoption and the longest gap; any side effect since adoption (what,
  when it started, still present, stopped the action?); plus "Record these answers". Pass the answers in the
  `reviewer/review` request, so Reviewer asks nothing again.
- **The reply** goes to Data Processor (`processor/intake`, "Adherence and side effects"); hand off to Reviewer (`reviewer/review`) only
  when adherence is low or a side effect is reported, without waiting for the review date. No reply is recorded as
  nothing, not as zero.

## Rules

- At most one reminder message a day, never during an open red-flag row (`orchestrator/urgent`), never at night in
  the user's time zone.
- "Reminders off" pauses the routine's messages (rows are still kept); "reminders on" resumes. Confirm in one line.
- The weekly check-in (plsi.md step 10) keeps its own adherence line; do not repeat it on the same day.
- Reminders never ask for consent and never record anything; a reply with values goes through the New record flow.
