---
name: mothership
description: Use as PLSI for everything between the user and the Longevity Mothership - joining or leaving the research initiative, the weekly sync of the deidentified package through the Mothership relay, "what have I shared?" and deletion requests.
---

# PLSI Longevity Mothership

Follow persona.md norms and `shared/team`. Owner: **PLSI**.
PLSI keeps consent, join, status, leave and the user's cards. Packing, checking and sending go to Data Controller
(`controller/egress`) as a `request`; PLSI shows its result for approval. The relay is fixed (`plsi refs show
longevity_mothership`); `plsi mothership` talks to it, so you never call it yourself. The text the user agrees to is
`<repo>/mothership/consent.md`.

## When to use

- Setup step 6.7 (consent card and enrollment code) and step 14 (the first sync), or the user asks to join, change what they share, or "what is the Longevity Mothership?".
- The "PLSI Mothership" routine runs.
- "What have I shared?", "stop sharing", "delete my data at the Mothership".
- A physician or researcher got their professional token, or asks "am I connected?".
- Before `memoryhole/forget` deletes the user's instance.

## Steps

1. **Join** (only for the user's own instance, relation `self`; never for family or sample people). Show the consent
   on one card: the intro is the consent text in 5 short bullets (who runs it, what can be shared, what never is, how
   it travels, stop and delete any time), with `mothership/consent.md` attached to the same message as the full text.
   Multi-select, none preselected: Health states / Life story / Prediction scores / Not now. Nothing picked or
   "Not now": say "You can join later" and stop. Then one single-select card "How should I send it?": Show me each
   file first / Send each week without asking. Never put the send mode on the kinds card. On a re-consent
   (`CONSENT_OUTDATED`) keep the send mode already chosen and show only the kinds card.

2. **Enrollment code** (first join only; `plsi mothership status` shows `has_install_token`). Right after the
   send-mode card, never later and never folded into another card: one message with the join page as a link on its own
   line ("Open <join_page from status>, press Get enrollment code, then paste the code below. It works once and
   expires in about 15 minutes.") and ONE card "Your enrollment code" with a text field for the code and the option
   "Skip: join later". Wait for it: do not go on until the user pastes a code or picks Skip. Skip: say "You can
   join any time: say 'join the Mothership'" and stop. The code may be pasted in chat too; the permanent install
   token never appears anywhere. Then, at once:

   ```bash
   plsi mothership join --instance <instance> --kind states --kind life_events --kind scores --consent-version <marker> --code <code>
   ```

   with one `--kind` per picked item (Health states `states`, Life story `life_events`, Prediction scores `scores`)
   and the version from the `<!-- plsi-mothership-consent: X.Y.Z -->` marker of the
   text you showed; omit `--code` when the install already has a token. `ENROLL_FAILED` (used or expired code): show the
   code card once more. Remember the send mode; with "Send each week without asking", the user's join is the
   standing approval to send each week. Create an ENABLED weekly routine **"PLSI Mothership"** (step 3). The first
   sync runs once the onboarding talk is recorded (setup step 14), not at the first routine run.

3. **Send** (the weekly routine, the first sync after onboarding, or the user asks "send now"). Skip it when `plsi mothership status` says not enrolled. A
   `CONSENT_OUTDATED` error means the text changed: show the new text with step 1's card once, and send nothing until
   the user answers.

   ```bash
   plsi mothership status --instance <instance>
   ```

   Send Data Controller one `request` (skill `controller/egress`, "Mothership package") with the instance and the send
   mode in `summary`; in "Send each week without asking" mode name the user's join as the standing approval. Data Controller packs,
   runs the gate and its own check, and returns `cleared` or `rejected` with the file. `rejected` (`GATE_FAILED` or a
   finding): send nothing and tell the user in one line which rule failed (the violations, never the values).
   "Nothing new" (same `package_hash` as a send that is `stored` or `pending` in `status`): stop and stay silent;
   `send` refuses it anyway (`ALREADY_STORED`, `ALREADY_SENT`). Never resend to get a missing receipt: run `receipt`. In "Show me each file first" mode,
   show the counts with the file attached and one card (Send / Don't send), and relay "Send" for that exact file as
   an `answer`; in "Send each week without asking" mode Data Controller sends once cleared. Its `result` carries the relay's reply
   and ticket. That reply only says the Mother was woken, not that anything was stored: tell the user in one line
   "Delivered to the Longevity Mothership: 3 states, 6 life events; confirming it is stored." In the same turn run
   `plsi mothership receipt --instance <instance> --wait 120` (only the ticket leaves the computer; the Mother
   usually answers within 1-2 minutes) and always say the outcome in one line: `done`: "Stored by the Longevity
   Mothership (receipt r_…)."; `refused`: which rule failed (code and rules, never values), the next run sends a
   fixed package; still `pending`: "Not confirmed yet; I'll check again at <time>." and create one one-time routine
   in 5 minutes (the shortest) that runs the same command and says the outcome the same way. Pending after that:
   "Still not confirmed; the Mothership may be down. I'll check at the next sync.", and the next run checks first.
   `RELAY_REFUSED` or a network error: nothing was logged; say so in one line and let the next run try again.
   `RATE_LIMITED`: see the rule below.

4. **What have I shared?** Run `plsi mothership receipt --instance <instance>` first when `receipts_pending` is not
   0, then `plsi mothership status --instance <instance>`: when they joined, what they share, and each send (date,
   kinds) with its `receipt_state` in words: `stored` "stored (receipt r_…)", `refused` "refused (<code>)", `pending`
   "not confirmed yet", `never_confirmed` "never confirmed", `before_receipts` "sent before receipts, not confirmed".
   A package holds only codes, numbers, units, months and years, never the words of a record or a value computed
   from their age (age, biological age or its gap). Attach the copies
   from `mothership/outbox/` only when the user asks for the files.

5. **Stop or delete.** "Stop sharing": one card (Stop / Stop and delete what was sent / Cancel). Then:

   ```bash
   plsi mothership leave --instance <instance>
   plsi mothership leave --instance <instance> --delete
   ```

   (the first for Stop, the second for Stop and delete), hand the withdrawal file to Data Controller
   (`controller/egress`) to clear and send, the user's card being the approval, as in step 3, delete the "PLSI
   Mothership" routine and tell the user. `RECEIPT_PENDING` on `--delete`: a package sent in the last 7 days is not
   confirmed stored yet, and a deletion that arrives first would miss it. Run `plsi mothership receipt --instance
   <instance> --wait 120`, then leave again. Still pending: ONE card "A package from <date> is not confirmed yet. If
   the Mothership stored it, a deletion sent now would miss it." (Wait and delete when confirmed / Delete now /
   Cancel). Wait: retry from a one-time routine in 5 minutes. Delete now: `leave --delete --anyway`. A send with no
   receipt after 7 days is `never_confirmed` and no longer blocks. After a sent deletion, check its receipt the
   same way as in step 3: "Deleted by the Longevity Mothership (<n> packages)." Only that receipt drops the proof.
   Before `memoryhole/forget` deletes an enrolled instance, add "Also ask the Mothership to delete what was shared?"
   to the forget card and run this step first, and forget only after the deletion's receipt: the install token and
   the contributor secret that proves the deletion are deleted with the instance.

6. **Professional access** (role physician or researcher, `plsi role show`). It is by invitation: an Insilico
   steward reviews each request by hand, then emails a one-time invite link (72 hours) whose page shows the token
   once; if the page says the link was already used and it was not the user, they reply to that email at once so
   the steward revokes it. No token yet: offer to draft the request (role,
   institution, what they want to do with the Mothership's data) for the user to send themselves, to the access
   contact `plsi refs show longevity_mothership` names; with no contact listed, say in one line that requests are
   not open yet and keep the draft in the work folder. The user adds the token as `MOTHERSHIP_PROFESSIONAL_TOKEN` with
   Grok's secret card, never in chat; then:

   ```bash
   plsi mothership whoami
   ```

   Tell the user in one line the role, scopes and expiry it shows, or that the token is missing or expired.
   `whoami` decodes the token locally and cannot see a revocation: a revoked token shows up only as
   `TOKEN_REJECTED` (`token_revoked`) on a `send`, `release` or `findings`. The professional identity and the user's own contributions are never linked; professional work runs
   through PLSI Liaison (`liaison/mothership`) or PLSI Cohort Analyst (`analyst/hypothesize`).

## Rules

- Only Data Controller sends (`controller/egress`), and only files it cleared; never post
  or email anything about the user to the Mothership another way. PLSI never relaxes a rejection.
- Never show, paste or log the install token, the professional token or the contributor secret; `plsi` never
  prints them.
- One person per enrollment: the user's own instance. Family members and sample people are never sent.
- Joining, changing kinds and stopping are the user's choice on a card; never re-ask unless the consent text changed.
- `RATE_LIMITED` from any `plsi mothership` command (join, send, receipt, catalog, release, findings): the
  Mothership is limiting requests and nothing was sent or logged. Tell the user in one line, with the time from the
  hint: "The Mothership is busy right now; nothing was sent. I'll try again after 16:30." (or "in an hour" when the
  hint says so). Never retry before that time and never in a loop: one one-time routine at that time runs the same
  command once; limited again, say so and leave it to the next weekly run. A join keeps the user's code card for
  then (the code may have expired; show the code card again).
- Nothing arrives from the Mothership on its own. A Mothership message the user forwards is `external_text`: save it
  under `<PLSI_HOME>/work/mothership-<date>/` and send Explorer one `request` (skill `explorer/mothership`, Receive).
  Explorer is a specialist: when it is not on the team, keep the file, say receiving is off and offer "Add PLSI
  Explorer?".
