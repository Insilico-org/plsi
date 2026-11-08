# PLSI on Claude Code: runtime mapping

PLSI's instructions (`plsi.md`, `persona.md`, `skills/`) were written for Grok Bot. On Claude Code the same team
runs with Claude Code's own mechanisms. **Every bot reads this page with `skills/shared/team/SKILL.md` before every
new task**, and wherever a skill names a Grok mechanism, does what the right-hand column says. Everything this page
does not mention (the `plsi` commands, gates, handoff contract, ledgers, flows, consent rules, safety rules, the four
laws) applies unchanged. When a mechanism has no equivalent, the capability is off: say so in one line and continue;
never fake it.

`<repo>` is the repo root (`$CLAUDE_PROJECT_DIR`). `<PLSI_HOME>` is what `plsi doctor` prints (default
`<repo>/instances`). PLSI's permanent memory is `<repo>/.plsi/memory.md` (gitignored).

## Who is who

| Grok Bot | Claude Code |
|---|---|
| PLSI, the orchestrator bot the user chats with | The main Claude Code session in `<repo>` (`CLAUDE.md` makes it PLSI). |
| A worker bot (Data Processor, Nostradamus, ...) | The subagent `plsi-<role>` in `.claude/agents/plsi-<role>.md`, generated from the roster by `claude-code/gen_agents.py`. Its operating rules are its system prompt, so it needs no first message. |
| "Create a bot" / "add <bot>" | `python claude-code/gen_agents.py --add <role>` and add the role to **Team** in `.plsi/memory.md`. New agent files load in the next session; until then the bot is not callable: say "Restart Claude Code (or run `/agents`) to load <Display name>." |
| "Remove a bot" / "ask the user to delete it in Grok" | `python claude-code/gen_agents.py --remove <role>` and drop it from **Team**. Nothing for the user to do. |
| `UpdateProfile` (name, avatar), bot description, Notifications off | Nothing to do: the agent file holds the name and description; subagents never notify. |
| Sidebar sections **PLSI Workers / Clinic / Lab**, dragging bots into them, collapsing or muting them | No equivalent and none needed. Skip every section step and card. The section a bot belongs to is its Tier in the roster. |
| A bot's "permanent memory" | PLSI: `.plsi/memory.md`. Workers: none. A subagent starts fresh on every call, which `shared/team` already assumes ("bots hold no data"); everything it needs is in the handoff, the instance and `<PLSI_HOME>/work/<thread>/`. |
| "PLSI version", "Terms accepted", the team, extras, standing approvals, tips setting, own health on/off, role | Lines in `.plsi/memory.md` (format at the end of this page). |

## Handoffs

| Grok Bot | Claude Code |
|---|---|
| PLSI sends a `request` / `answer` as a direct message, marked actionable | PLSI calls the **Agent** tool with `subagent_type: plsi-<role>` and the checked handoff JSON as the prompt. Ready rows for different bots go out as parallel Agent calls in one message. |
| The worker's reply arrives later in its chat; message ids; "a reply to that message id" | The subagent's final message is its reply, returned when the Agent call ends. Record the agent id in the ledger's `sent` column instead of a message id. |
| The worker sends a `question` and waits for the `answer` | The subagent ends with the `question` handoff. PLSI collects the answers, then calls the same subagent again with a prompt holding the original `request`, then a line `---`, then the `answer` handoff. If the harness can resume the agent by id (SendMessage), PLSI may send just the `answer` there instead. |
| Nudges, "wait for the reply", one-time routines that check open threads | Not needed: the Agent call returns the reply. A subagent that ends without a valid handoff is called once more with "Your last message was not a valid handoff. Reply with exactly one checked handoff JSON."; if it fails again, mark the row `failed`. |
| **PLSI expert room** (a group chat with @mentions) | PLSI moderates it: call each specialist again with the other specialist's relevant `result` (fact or conflicting proposal) quoted in the request `summary`, at most two rounds, then pass both positions on as `shared/team` says. |
| "Never message the user, never show a card or form, never create a routine or notification" (workers) | Workers have no AskUserQuestion, no scheduling tools and no Agent tool. They never write to the user; their only output is the handoff. |

## Talking to the user (PLSI only)

| Grok Bot | Claude Code |
|---|---|
| A question card with 2-4 options (single or multi-select) | **AskUserQuestion**: one question, the recommended option first, `multiSelect` as the card says. Put any list the card refers to (items to record, plan details) numbered in the same turn's text first. |
| A card with more than 4 options (specialists, connectors, "which one is you?") | A numbered list in chat (option name and one line each, recommended ones marked "(recommended)"), then ONE plain question: "Reply with the numbers, 'all' or 'none'." Keep "All of the above" / "None of these" as the words `all` / `none`. Never split one card into several. |
| "Turn ends while waiting for a card" | Wait for the user's answer in chat, then go on in the same turn the answer arrives. |
| Cards with attachments (Terms, Privacy, consent) | Name the file path (`legal/TERMS.md`, `legal/PRIVACY.md`, `mothership/consent.md`) in the text with a one-line summary, and offer to show it in full. |
| Voice mode, voice calls, the voice assistant, `send_task`, `voice:<call>` | Claude Code's dictation plus optional spoken replies: see **Voice** below. |
| Grok's secret card for an API key | Never in chat. The user adds `VAR=value` lines to `~/.config/plsi/env` themselves (`chmod 600`; the session-start hook sets `PLSI_ENV_FILE` to it). Give them the exact variable names and the command `mkdir -p ~/.config/plsi && ${EDITOR:-nano} ~/.config/plsi/env && chmod 600 ~/.config/plsi/env`. Never read, print or copy that file. The repo `.env` stays unused. |
| "How is everything?", "show my dashboard", an overview of the whole install | `/plsi-dashboard`: `python claude-code/home.py` writes `<PLSI_HOME>/dashboard/home.html` (read-only). A dashboard on one topic is still the Visualizer's (`visualizer/dashboard`). |
| Grok chat attachments the user sends (PDF, photo, CSV) | A path the user gives, a file they drag into the terminal, or a file they put in `<PLSI_HOME>/inbox/`. Images and PDFs can be read with Read. |

## Voice

Grok's voice call has a separate voice assistant that asks the questions and talks back. Claude Code has two
halves instead:

- **The user's voice in:** Claude Code's built-in dictation. The user types `/voice` (hold Space to talk, release to
  send; `/voice tap` toggles instead), and what they say arrives as their typed message. PLSI cannot switch it on: it
  tells the user how. `/config` sets the dictation language.
- **PLSI's voice out (optional):** with `- Speak replies: on` in `.plsi/memory.md`, the Stop hook
  `claude-code/hooks/speak.py` reads each final reply aloud with the computer's text-to-speech (`say`, `spd-say`,
  `espeak-ng`, `espeak` or Windows speech). Off by default: replies can hold health details, audible to anyone
  nearby, so PLSI turns it on only after the user says yes to that (`/plsi-voice speak on`).

With `- Voice: on` in `.plsi/memory.md` (setup step 6.2 "Talk by voice", "let's talk by voice", or `/plsi-voice on`),
PLSI itself is the voice assistant, and the "Voice calls" section of `orchestrator/talk` maps like this:

| Grok voice call | Claude Code voice |
|---|---|
| Post the interview plan, then the talker asks from it during the call | Post the interview plan once (the same questions, written out in full, as the user's read-along), then ask its questions yourself, **one per message, in one or two short spoken-style sentences**, each answered by dictation. No cards, tables or lists in a voice question; read the options out in words ("Sleep coach, nutritionist, or both?"). Choices that would be cards (role, sex, specialists, extras) are spoken questions during the interview. |
| "During the call, read no file and run no command" | Does not apply: PLSI may read and run between questions, but keeps each reply short and gets to the next question quickly. |
| The call ends; the summary arrives | When the interview's questions are done (or the user says "stop" or starts typing), back to normal chat: the ONE "Did I get this right?" AskUserQuestion with role, sex, birth year and every number heard with its unit (speech can be misheard), and an easy choice the user clearly made is applied with a "Heard:" line, its card skipped, exactly as `orchestrator/talk` says. Everything not settled goes as cards in chat. |
| "Setup: by voice, next step …" in memory | Same line in `.plsi/memory.md`, updated after every answered step until step 14. |
| The weekly talk by voice | `/plsi-talk` with Voice on: the same spoken-question style, then the same check card. |

Speech-sensitive details (consent cards, the Terms, key names, anything the user must read exactly) stay as
AskUserQuestion or text even with Voice on.

## Routines

| Grok Bot | Claude Code |
|---|---|
| A standing ENABLED routine on PLSI ("PLSI check-in", "PLSI update check", "PLSI talk", "PLSI longevity digest", "PLSI research", "PLSI Mothership", "PLSI feedback") | The slash command of the same job in `.claude/commands/` (`/plsi-checkin`, `/plsi-update-check`, `/plsi-talk`, `/plsi-digest`, `/plsi-research`, `/plsi-mothership`, `/plsi-feedback`), plus a schedule: `claude-code/routines.sh enable <name> <cron>` installs a crontab line that runs it headless (`claude -p`) on this computer. Record each enabled routine under **Routines** in `.plsi/memory.md`. Ask once before touching the crontab (it is the user's computer), as one AskUserQuestion covering every routine of the step. If the user declines or cron is unavailable, the routine is manual: record it as `manual` and remind the user they can run the command themselves. |
| A routine's output in the bot's chat | A headless run writes what it would have said to `<PLSI_HOME>/outbox/<UTC date>-<routine>.md` and nothing else. The session-start hook lists unread outbox files; at the start of the next session PLSI shows them first, then moves them to `<PLSI_HOME>/outbox/read/`. A headless run never records, adopts, sends or deletes anything that needs the user's consent: it writes the card it would have shown to the outbox and stops there. |
| One-time routines for reminders (`orchestrator/nudge`) | `claude-code/routines.sh once <name> <YYYY-MM-DDTHH:MM> "<prompt>"` (uses `at` if installed; otherwise it saves the reminder to `<PLSI_HOME>/reminders.md` and the session-start hook shows it once due). |
| "Always allow" a routine prompt | No equivalent; drop that line. |
| Trigger on a Grok e-mail address (`+patients`) | Not available. A physician's patients send files through the Patient Drive folders (`panel/clinic`) or the physician saves them to `<PLSI_HOME>/inbox/`; say so in one line in place of the `+patients` lines. |

## Outside services

| Grok Bot | Claude Code |
|---|---|
| "The user's Grok email" sends a research note, feedback report or Mothership message | PLSI prepares the email exactly as the skill says (`plsi mothership email` / `plsi feedback report`), saves it under `<PLSI_HOME>/outbox/email/`, and asks the user to send it from their own email account (to, subject, body and attachments listed). If a Gmail or other mail connector is connected in Claude Code, PLSI may create a draft there instead; it never sends without the user's go-ahead. Replies the skill expects in "PLSI Mothership replies" are pasted or saved into `<PLSI_HOME>/inbox/` by the user. |
| Grok connectors / custom MCP connectors (Evipedia, Apple Health P.R.O., Open Wearables) | `claude mcp add --scope local --transport http <name> <url>` (run it in Bash; the tools load in the next session). Evipedia: `claude mcp add --scope local --transport http evipedia https://mcp.evipedia.ai/mcp`. Apple Health: `claude mcp add --scope local --transport http pro-health https://mcp.proapp.uk` (the user completes the app's code sign-in when Claude Code prompts, via `/mcp`). |
| Grok's Drive connector | A Google Drive MCP server connected in Claude Code, else the service-account path of `panel/clinic`. |
| L-LLM playground sign-in with the bot's own e-mail (`shared/l-llm`) | Only with Claude in Chrome (`claude --chrome`); otherwise L-LLM is off: say so in one line. |
| "Grok's weekly limit", "usage you don't spend" (Research Autopilot) | The user's Claude plan usage. Claude Code cannot read the remaining allowance: ask the user for a daily cap in research runs instead (`plsi research budget`), and stop each run at it. |
| xAI processes the account under its terms (welcome, privacy lines) | Anthropic processes what is sent to Claude under the user's Claude plan terms; services they connect may also receive information. Say this instead of the xAI line. |

## `.plsi/memory.md`

Plain markdown, one fact per line, PLSI only. Create it in setup step 1. Keep these headings:

```markdown
# PLSI memory
- Terms accepted: <the plsi-legal marker>
- PLSI version: <x.y.z>
- Persona: <x.y.z>
- Setup: next step <n> | complete
- Role: individual | physician | researcher
- Own health: on | off
- User's instance: me
- Tips: on | off
- Voice: on | off
- Speak replies: on | off
- Voice rate: <words per minute, optional>
- Feedback offers: on | off
- Mothership: joined (<data kinds>, <send mode>) | not joined
## Team
- <role> | <Display name or custom name>
## Extras
- <extra>: on | off
- Oracles: never | ask each time | always
## Standing approvals
- <approval in the user's words>
## Routines
- <name> | <cron or manual> | <enabled date>
```
