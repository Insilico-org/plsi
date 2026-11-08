#!/usr/bin/env bash
# PLSI routines on Claude Code: crontab lines that run a PLSI slash command headless.
#
#   claude-code/routines.sh enable "PLSI check-in" "17 9 * * 1"   # add or update the routine's crontab line
#   claude-code/routines.sh disable "PLSI check-in"               # remove it
#   claude-code/routines.sh list                                  # PLSI lines in the crontab
#   claude-code/routines.sh run "PLSI check-in"                   # run it once now, headless (what cron runs)
#   claude-code/routines.sh once <name> <YYYY-MM-DDTHH:MM> "<prompt>"   # one-time reminder via `at`
#
# Each line is tagged "# PLSI:<name>", so enabling twice updates instead of duplicating.
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
home="${PLSI_HOME:-$repo/instances}"
tools='Bash(plsi:*) Bash(.venv/bin/plsi:*) Bash(git -C:*) Bash(date:*) Bash(mkdir:*) Bash(mv:*) Read Write Edit Glob Grep Agent WebSearch WebFetch'

command_for() {
  case "$1" in
    "PLSI check-in") echo plsi-checkin ;;
    "PLSI update check") echo plsi-update-check ;;
    "PLSI talk") echo plsi-talk ;;
    "PLSI longevity digest") echo plsi-digest ;;
    "PLSI research") echo plsi-research ;;
    "PLSI Mothership") echo plsi-mothership ;;
    "PLSI feedback") echo plsi-feedback ;;
    *) echo "unknown routine: $1 (expected one of: PLSI check-in, PLSI update check, PLSI talk, PLSI longevity digest, PLSI research, PLSI Mothership, PLSI feedback)" >&2; return 1 ;;
  esac
}

job_line() {  # the shell command cron runs
  local cmd claude_bin
  cmd="$(command_for "$1")"
  claude_bin="$(command -v claude || true)"
  [ -n "$claude_bin" ] || { echo "claude not found on PATH" >&2; return 1; }
  printf 'cd %q && mkdir -p %q && PATH=%q:%q:/usr/local/bin:/usr/bin:/bin %q -p %q --allowedTools %q < /dev/null >> %q 2>&1' \
    "$repo" "$home/outbox" "$repo/.venv/bin" "$(dirname "$claude_bin")" "$claude_bin" \
    "/$cmd headless" "$tools" "$home/outbox/.routines.log"
}

current() { crontab -l 2>/dev/null || true; }
need_cron() {
  command -v crontab >/dev/null || { echo '{"ok": false, "error": "crontab not available: keep this routine manual"}'; exit 1; }
}

case "${1:-}" in
  enable)
    [ $# -eq 3 ] || { echo "usage: $0 enable <name> <cron>" >&2; exit 2; }
    need_cron
    command_for "$2" >/dev/null || exit 2
    job="$(job_line "$2")" || exit 1
    line="$3 $job # PLSI:$2"
    { current | grep -vF "# PLSI:$2" || true; echo "$line"; } | crontab -
    echo "{\"ok\": true, \"enabled\": \"$2\", \"cron\": \"$3\"}"
    ;;
  disable)
    [ $# -eq 2 ] || { echo "usage: $0 disable <name>" >&2; exit 2; }
    need_cron
    { current | grep -vF "# PLSI:$2" || true; } | crontab -
    echo "{\"ok\": true, \"disabled\": \"$2\"}"
    ;;
  list)
    need_cron
    current | grep -F "# PLSI:" || true
    ;;
  run)
    [ $# -eq 2 ] || { echo "usage: $0 run <name>" >&2; exit 2; }
    job="$(job_line "$2")" || exit 1
    eval "$job"
    ;;
  once)
    [ $# -eq 4 ] || { echo "usage: $0 once <name> <YYYY-MM-DDTHH:MM> <prompt>" >&2; exit 2; }
    mkdir -p "$home/outbox"
    if command -v at >/dev/null; then
      when="$(date -d "$3" '+%H:%M %Y-%m-%d' 2>/dev/null || date -j -f '%Y-%m-%dT%H:%M' "$3" '+%H:%M %m/%d/%Y')"
      printf 'cd %q && printf "%%s\\n" %q > %q\n' "$repo" "$4" "$home/outbox/${3%%T*}-$2.md" | at "$when" 2>/dev/null
      echo "{\"ok\": true, \"scheduled\": \"$2\", \"at\": \"$3\"}"
    else
      printf -- '- due %s: %s\n' "$3" "$4" >> "$home/reminders.md"
      echo "{\"ok\": true, \"scheduled\": \"$2\", \"at\": \"$3\", \"note\": \"at not installed: saved to reminders.md; the session-start hook shows it once due\"}"
    fi
    ;;
  *)
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 2
    ;;
esac
