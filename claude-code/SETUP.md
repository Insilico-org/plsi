# PLSI setup on Claude Code

Run by `/plsi-setup`. Follow `<repo>/plsi.md` from step 0 to step 14, in order, as one continuous run, with
`claude-code/RUNTIME.md` for every Grok mechanism. The step changes below override `plsi.md`; a step not listed
here runs exactly as `plsi.md` says. Keep `plsi.md`'s step numbers (skills refer to them) and its rules: never skip a
step, never end the turn mid-setup except to wait for the user's answer, one question per message in step 6, the
three milestone lines, and the stage timing with `plsi feedback mark`. After each finished step, update
`Setup: next step <n>` in `.plsi/memory.md`, so a new session can resume where this one stopped.

## 0. Welcome

As `plsi.md`, with one change to the data paragraph: Anthropic processes what is sent to Claude under the user's
Claude plan terms and privacy policy (in place of xAI and the Grok Bot account); services they connect may also
receive information; Insilico receives information only through contributions or emails they choose to send; shared
measurements carry a code, not their name, with dates reduced to the month. The closing line says "a short
conversation about you, by voice (Claude Code's /voice) or in chat".

## 1. Install

The repo is already checked out: `<repo>` is the current project directory. Install into a project virtualenv, in
the foreground:

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -q -e .
```

Then check `plsi --version` (the session-start hook puts `.venv/bin` on PATH; if `plsi` is not found in this first
session, use `.venv/bin/plsi` for the rest of setup). Create `.plsi/memory.md` from the template at the end of
`RUNTIME.md` if it does not exist.

**Terms:** one AskUserQuestion "By installing, you agree to the Terms of Service (legal/TERMS.md) and the Privacy
Policy (legal/PRIVACY.md). You must be 18 or older." with "I agree" / "Not now", naming both files in the text
before it and offering to show them. Everything else as `plsi.md`; remember the marker as `Terms accepted:` in
`.plsi/memory.md`.

## 2. Check the environment

As `plsi.md`. In place of other Grok Bots and sidebar sections, note which `.claude/agents/plsi-*.md` workers exist
(`python claude-code/gen_agents.py --list`), the **Team** and **Routines** in `.plsi/memory.md`, and the PLSI lines of
`crontab -l` (`claude-code/routines.sh list`). There are no "other Grok Bots"; skip everything about them here and in
steps 6.1, 6.3 and 9.

## 3. Set identity

Nothing to set: `CLAUDE.md` already names you PLSI · Chief Orchestrator. Keep a custom name the user gives in
`.plsi/memory.md`. Skip the avatar.

## 4. Adopt the persona

`CLAUDE.md` imports `persona.md`, so the persona is adopted. Write `Persona: <its plsi-persona marker>` in
`.plsi/memory.md`. The persona check of step 4.2 runs in `/plsi-update-check`: a changed marker becomes the
"Adopt?" question; after "Adopt" there is nothing to send to the workers (they read `persona.md` on every call).

## 5. Create the core team

No section and no first messages. Run:

```bash
python claude-code/gen_agents.py --tiers core
```

Write every core role with its Display name under **Team** in `.plsi/memory.md`. New agent files load in the next
session: tell the user in the "team created" milestone line (after step 7) to restart Claude Code once setup is
done, or to run `/agents`, so the team can be called. Nothing waits for `result` replies: the setup `result` check
before step 14 is replaced by `gen_agents.py --list` showing every Team role installed.

## 6. Setup choices

Every card follows RUNTIME.md (AskUserQuestion up to 4 options; a numbered list and one plain question above that).

- **6.1** As `plsi.md`, without the other-bots card.
- **6.2** As `plsi.md`: one AskUserQuestion "How shall we do the setup?" (intro: a short talk about you, then a few
  choices) with "Talk by voice (recommended)" / "Here in chat". Voice: write `Voice: on` and "Setup: by voice, next
  step 6.3" in `.plsi/memory.md`, and in the same message tell the user to type `/voice` and hold Space to answer
  (`/voice tap` to toggle instead), with the interview plan of `orchestrator/talk` (Voice calls). Then ask, as
  ONE AskUserQuestion, "Shall I read my questions and replies aloud too? Anyone nearby will hear them." (Not now /
  Read them aloud); "Read them aloud" writes `Speak replies: on`. Then run the interview the voice way of
  RUNTIME.md, Voice: PLSI asks each question itself, one short spoken-style question per message.
- **6.3** As `plsi.md`: the voice path (RUNTIME.md, Voice) or the chat path, as chosen in 6.2. The physician's `+patients` e-mail address and its routine do not exist; say
  instead that patients send files through the Patient Drive folders (step 6.6) or that they save files to
  `<PLSI_HOME>/inbox/`.
- **6.4** The specialists list has more than four options, so it is a numbered list (Display name and Description,
  preselected ones marked "(recommended)") and the question "Reply with the numbers, 'all' or 'none' (Enter keeps
  the recommended ones)."
- **6.5** The extras: "Weekly talk" is "A weekly talk with me, by voice or text". "Daily research" asks for a cap in research
  runs per day instead of "usage you don't spend". If the five options with all/none exceed four, use the numbered list.
- **6.6** Tools and keys: as `plsi.md`, with the Claude Code setup column below. For keys, run `plsi keys scan` and
  `keys map` as `plsi.md` says, then ONE message naming each variable to add to `~/.config/plsi/env` with the
  command from RUNTIME.md (never in chat), then `plsi keys status` when the user says they are added.

  | Option | Claude Code setup |
  |---|---|
  | Methylation clocks | `.venv/bin/python -m pip install -q -e ".[clocks]"` |
  | Apple Health | `claude mcp add --scope local --transport http pro-health https://mcp.proapp.uk`, then the user signs in with the app's code through `/mcp` in the next session |
  | Wearables (Open Wearables) | the user's Open Wearables MCP server added with `claude mcp add --scope local ...` as its docs say (`plsi refs show open_wearables`), plus the two keys |
  | L-LLM | offered only when Claude in Chrome is available; otherwise left off the list |
  | Patient Drive folders | `.venv/bin/python -m pip install -q -e ".[drive]"`, then as `plsi.md` |
  | every other row | the keys as `plsi.md` lists them |

- **6.7** As `plsi.md`. The join card has more than four options when it lists data kinds: use the numbered list,
  with `mothership/consent.md` named above it. Research notes and feedback that `plsi.md` sends "from the user's Grok
  email" are prepared for the user's own email (RUNTIME.md, Outside services).

## 7. Create the specialists and the role section

```bash
python claude-code/gen_agents.py --add <role> ...   # every specialist chosen in 6.4, plus every roster row of the role's tier
```

Add them to **Team**. No sections, no Notifications or drag-and-drop line, no expert-room line. Milestone line:
"Team created: <Display names>. Restart Claude Code after setup (or run /agents) to load them."

## 8. Evipedia connector

If chosen: `claude mcp add --scope local --transport http evipedia https://mcp.evipedia.ai/mcp` (available from the
next session).

## 9. Create the instance

As `plsi.md`, without the "Other bots" part. Memory Hole requests in this step and Data Processor's interview record
need their subagents: they load only after a restart, so in this first session queue them as ledger rows in
`<PLSI_HOME>/work/setup/ledger.md` (status `planned`) and dispatch them at the start of the next session, before
anything else. Instance creation (`plsi init`) runs now, as PLSI.

## 10-12. Routines

Each routine of steps 10-12 that applies is enabled with `claude-code/routines.sh enable`. Before the first one,
ONE AskUserQuestion: "Schedule PLSI's routines on this computer with cron? They run Claude Code in the background
and leave their messages for your next session." (Schedule them (recommended) / Keep them manual). Then:

| Routine | Command | Default schedule |
|---|---|---|
| PLSI check-in | `/plsi-checkin` | `17 9 * * 1` (Mondays 09:17) |
| PLSI update check | `/plsi-update-check` | `41 10 */3 * *` |
| PLSI talk (if chosen) | `/plsi-talk` | `23 18 * * 0` |
| PLSI longevity digest (with Explorer) | `/plsi-digest` | `7 8 * * 6` (monthly: `7 8 1 * *`) |
| PLSI research (if chosen) | `/plsi-research` | `33 2 * * *` |
| PLSI Mothership (if joined) | `/plsi-mothership` | `51 11 * * 3` |

`claude-code/routines.sh enable "<name>" "<cron>"` for each (it updates a line that already exists and never adds
a second). "Keep them manual" or no cron: record each as `manual` under **Routines**. Step 11's daily-research
cards (share and topic) are asked now, in chat, as `plsi.md` says.

## 13. Tips

As `plsi.md` (`Tips:` line in `.plsi/memory.md`).

## 14. Welcome

As `plsi.md`, with these changes: write `PLSI version:` and `Setup: complete`; the bullet about the bots says they
work behind PLSI as Claude Code subagents (their work is in `<PLSI_HOME>/work/`); add one bullet "Restart Claude
Code now so your team and connectors load; the record of our interview is filed at the start of the next session."
The record card for the interview and the first Mothership sync run at the start of the next session (the queued
`setup` ledger), not now. "PLSI feedback" (with Feedback offers on) is enabled like the other routines with
`/plsi-feedback`, default `29 19 * * 5`.
