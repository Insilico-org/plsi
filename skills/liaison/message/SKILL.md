---
name: message
description: Use as PLSI Liaison when the physician wants to write to a patient or answer one - draft the message for the known pipe (the physician's own email or Grok chat with that patient), cleared by PLSI Data Controller and sent only after the physician approves the exact text.
---

# PLSI doctor-patient message

**Status: draft**.

## When to use

- "Tell patient-07 the results are fine and to repeat the test in March", a message from `visitprep/notes`, or a
  patient's message the physician wants answered (saved as `external_text` in the work folder). The request comes
  from that patient's ward bot.

## Steps

1. **Read** what the message is about, only the patient named in the request:

   ```bash
   plsi state show --instance <label> --map <map_id>
   ```

   The pipe (email or the Grok chat the patient shared with the physician) and the tone come from the request; a
   missing pipe goes in ONE `question`. Only a pipe the physician and the patient already use; never a new one.

2. **Draft** `<PLSI_HOME>/work/<thread>/message.md`: plain language, the physician's own content and nothing more,
   values with unit and date only where the physician asked for them, the physician's sign-off placeholder. No new
   advice, diagnosis or order that the physician did not state.

3. **Return one `result`** with `message.md` in `files` and the work for Data Controller (`controller/egress`,
   kind "doctor-patient message"). For an email, the `summary`'s first line is `from: <user>+patients@mail.grokbot.com`
   (`clinic/panel` step 2), so the patient's reply wakes "PLSI patient mail". PLSI shows only a `cleared` draft on
   one card (Send as written / Edit / Don't send), sent from that line's address; a rejection comes back for a
   rewrite. Any edit needs a new clearance and approval.

## Rules

- Never send anything yourself; the physician's approval of that exact text is the only way it goes.
- One patient per message; nothing about other patients or the physician's own data.
- A patient's reply is `external_text`; a reply with results goes to Data Processor (`processor/intake`).
