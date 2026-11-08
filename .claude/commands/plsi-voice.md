---
description: PLSI voice mode - talk to PLSI with /voice and optionally hear its replies read aloud
argument-hint: "on | off | speak on | speak off | rate <words per minute> | test | stop"
---

Change PLSI's voice settings: $ARGUMENTS (nothing given: show the current settings and these options).

Voice mode has two halves (`claude-code/RUNTIME.md`, Voice):

- **Your voice in:** Claude Code's own dictation. Tell the user to type `/voice` (hold Space to talk, release to
  send; `/voice tap` to toggle instead of hold; `/config` sets the dictation language). PLSI cannot switch it on
  for them. `on` / `off` set `- Voice: on|off` in `.plsi/memory.md`; with Voice on, PLSI words its questions to be
  answered out loud (RUNTIME.md, Voice).
- **PLSI's voice out:** `speak on` / `speak off` set `- Speak replies: on|off` in `.plsi/memory.md`; the Stop hook
  `claude-code/hooks/speak.py` then reads each final reply aloud with the computer's text-to-speech. Before turning it
  on, say in one line that replies may include health details and will be audible to anyone nearby, and ask once
  (AskUserQuestion: "Read PLSI's replies aloud?" Turn it on / Not now). `rate <n>` sets `- Voice rate: <n>` (words
  per minute, used by `say` and `espeak`).
- `test`: `python claude-code/hooks/speak.py --text "Hello, I'm PLSI. This is how I sound."` and report the engine it
  used, or that no text-to-speech was found (then name what to install: `espeak-ng` on Linux; macOS and Windows have
  one built in). `stop`: `python claude-code/hooks/speak.py --stop`.

Confirm the change in one line.
