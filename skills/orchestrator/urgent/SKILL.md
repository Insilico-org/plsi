---
name: urgent
description: Use as PLSI when the user's words, a bot's `red_flag` line or a recorded value suggest an acute emergency, a critical lab value or a mental-health crisis, or when a request falls out of scope (minors, pregnancy, eating-disorder risk) - send the person to care at once, pause every other flow and resume later.
---

# Urgent and out of scope

Follow persona.md norms and `shared/team`. Owner: **PLSI**.
Every other bot only flags; PLSI alone tells the user.

Safety beats every other flow, the confirmation budget and tips. A red flag is answered in the same turn, before
any other step, and never waits for a bot's reply or a question card.

## When to use

- The user describes a possible emergency, for themselves or the person an instance is about.
- A `result` or `question` from any other bot carries a `red_flag:` line in `summary`.
- A request touches a minor, pregnancy or breastfeeding, eating-disorder risk or a mental-health crisis.

## Red flags

Recognize by category, never by a fixed list of values or substances:

- **Acute symptoms:** chest pain or pressure; sudden breathlessness; stroke signs (face drooping, arm or leg
  weakness, slurred speech, sudden confusion or vision loss); fainting or a seizure; severe or sudden headache;
  severe bleeding; severe allergic reaction (swelling of face or throat, trouble breathing); severe abdominal pain;
  high fever with a stiff neck, rash or confusion; suspected poisoning or overdose; a severe reaction after
  starting or changing any plan action.
- **Mental-health crisis:** thoughts of suicide or self-harm, or of harming others.
- **Critical values:** a result the lab itself flagged as critical, panic or call-back; or a value beyond a critical
  limit given in a verified source. Thresholds come only from the lab's flag or that source,
  never from memory. A value far outside its map's range with no flag or source is flagged as `uncertain`.

Bots flag in the step's ONE `question` or `result`, sent as soon as they see it, one line per item in `summary`
(eating-disorder signs go as a `scope:` line instead, see Out of scope):

```text
red_flag: <category> | <item label> | <value and unit, or the user's words> | <lab critical flag | pmid:<id> | uncertain>
```

## Steps

1. **Tell the user at once**, in one short message, first in the answer:
   - acute symptom or crisis: "Please call your local emergency number now (112 in the EU, 911 in the US) or go to
     the nearest emergency department." For self-harm thoughts add: contact a local crisis line or emergency
     services now, and stay with someone you trust.
   - critical value without symptoms: "Contact your clinician or the lab today about <item>; if you feel unwell,
     call emergency services." `uncertain`: "Please check <item> with your clinician soon."
   - about someone else (`mother`): say who, and ask the user to get that person help. A `sample` instance: state
     the red flag in the answer, no emergency instruction.
   - a patient instance (physician role): one line at the top (label, item, value, flag, "contact the patient
     today"); step 2 pauses only that patient's threads, and step 3 asks once whether the patient was contacted.
   No diagnosis, no probabilities, no plan advice, no tips; one line on why ("chest pain can be a heart attack").

2. **Pause every other flow.** Add a row to each open ledger (`orchestrator/conduct`). Send each bot with a `sent`
   row one `request` on its thread: "Paused for safety: finish only read-only work, send your reply, start nothing
   new." A reply that arrives during the pause: verify it and write `received (paused)` with one line in the row; send
   nothing. The open-threads routine sends no nudges.

   ```markdown
   | n | red flag: <category> | orchestrator | orchestrator/urgent | <time> | asked | paused |
   ```

3. **Check back.** In the next turn, or the open-threads routine after a day, ask once: "Did you get care? Tell me
   when you want to continue." No other topic until the user answers.

4. **Resume** when the user says they are safe, have seen care, or it was a false alarm:
   - offer, in that thread's next question card, to record the event (symptom, clinician advice, new results) via
     `processor/intake`;
   - if it may relate to an active plan action, send `reviewer/review` with the `red_flag` line in `summary`; until
     the revised plan is adopted, tell the user to ask their clinician before continuing that action;
   - mark the red-flag row `done` and resume each paused row at the step its status needs: `received (paused)` ->
     `orchestrator/conduct` step 7 or 8, `sent` -> keep waiting (step 4), `planned` -> step 3.

## Out of scope

One format for the scope line everywhere: the `note` PLSI keeps in the instance (via `processor/intake`), the line it
names in every request `summary`, and the line a bot flags in its `question` or `result`:

```text
scope: <area> | <since date, or the user's words>
```

For example "scope: pregnancy | since 2026-09"; requests under it get no plans.

| Area | Recognize | Decline | Point to |
|---|---|---|---|
| Minor | birth year under 18 years ago, or the user says so | every plan, stack and diet change for that instance | a pediatric clinician |
| Pregnancy or breastfeeding | the user says so, or a recorded test or note | every plan, stack and diet change | an obstetric clinician or midwife |
| Eating-disorder risk | restriction, purging or fear of weight gain in the user's words; very low weight-for-height in a state | diet, fasting, calorie, weight and body-composition plans; weight targets in the arrow | a clinician or an eating-disorder service |
| Mental-health crisis | the red flag above | every plan until resume | emergency services or a crisis line |

- Say it in one line, without judgment: "I can't plan <area> changes while <scope>; your <clinician> is the right
  person. I can still record your results and show your reports."
- Still allowed (with the usual consent): recording, projecting, the life arrow's past and present, reports and
  export.
- The scope line is retracted (`processor/intake`, `retract`) only when the user says it no longer applies.

## Soft caution (not a hard stop)

Same pipe grammar as `scope:` / `red_flag:`, but **soft**: plans continue under clinician/test-first and narrow
limits. Emit when a non-crisis positive mental-health screen is identified (ad-hoc low mood or anxiety/panic
screening yes; PHQ-2 ≥ 3 on record; stress that stops daily life). Crisis remains `red_flag:`; minors / pregnancy /
eating-disorder risk remain hard `scope:`.

```text
caution: mood-screen-positive | <trigger> | <since date, or the user's words>
```

Examples: `caution: mood-screen-positive | phq2=3 | recorded 2026-10-21`; `caution: mood-screen-positive | ad-hoc low mood | ~3 weeks`.

- Does **not** decline every plan and does **not** pause all flows.
- PLSI copies the exact line into later request `summary`s on the thread (`orchestrator/conduct`) and records it as a
  `note` via `processor/intake` when not yet recorded.
- Specialists narrow or defer (Coach: easy/restorative only; Biohacker: defer new stack; Nostradamus: clinician/test
  FIRST, stress practices only) until clinician ack / revision_rule; they do not hard-stop ordinary recording.

## Rules

- Never delay the emergency message to collect a reply, confirm a detail or ask a question card.
- Never downgrade a bot's `red_flag`, a lab's critical flag or a scope; only the user's words resume a flow.
- Never name a drug, dose or remedy as first aid; point to emergency services or the clinician.
- A bot that messages the user about a red flag itself is corrected once (`orchestrator/conduct`, Rules), after the
  user has been told.
