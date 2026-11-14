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

   The pipe and the tone come from the request: email unless the physician named the Grok chat the patient shared
   with them; never a new pipe. Never ask for the patient's address (it is never stored): the email replies on the
   thread the request names (`reply_to`, the message id of the patient's last mail), else its To stays empty for the
   physician. Draft at once; nothing goes in a `question` before it.

2. **Draft** `<PLSI_HOME>/work/<thread>/message.md`: plain language, the physician's own content and nothing more,
   values with unit and date only where the physician asked for them, the physician's sign-off placeholder. No new
   advice, diagnosis or order that the physician did not state.

3. **Return one `result`** with `message.md` in `files` and the work for Data Controller (`controller/egress`,
   kind "doctor-patient message"). For an email, the `summary`'s first line is `from: <user>+patients@mail.grokbot.com`
   (`clinic/panel` step 2), so the patient's reply wakes "PLSI patient mail"; the second is `to: reply <id>` or
   `to: empty`, and the third the subject. PLSI shows only a `cleared` draft, once (To, Subject, text), on one card,
   sent from that line's address: with a thread, Send as written / Edit / Don't send; with To empty, "Add the
   address to send it, or copy it into your own mail": I'll send it myself / Edit / Don't send, with free text for
   the address, used for that one send and never written to a file, a note or memory. A rejection comes back for a
   rewrite. Any edit needs a new clearance and approval.

## Rules

- Never send anything yourself; the physician's approval of that exact text is the only way it goes.
- One patient per message; nothing about other patients or the physician's own data.
- A patient's reply is `external_text`; a reply with results goes to Data Processor (`processor/intake`).
