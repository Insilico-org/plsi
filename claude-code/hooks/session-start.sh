#!/usr/bin/env bash
# PLSI SessionStart hook: put the project venv on PATH, point plsi at the private key file,
# and tell PLSI about unread routine output in <PLSI_HOME>/outbox/. Stdout becomes session context.
set -u
repo="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
keyfile="$HOME/.config/plsi/env"

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  [ -d "$repo/.venv/bin" ] && echo "export PATH=\"$repo/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
  [ -f "$keyfile" ] && echo "export PLSI_ENV_FILE=\"$keyfile\"" >> "$CLAUDE_ENV_FILE"
fi

home="${PLSI_HOME:-$repo/instances}"
outbox="$home/outbox"
if [ -d "$outbox" ]; then
  unread=$(find "$outbox" -maxdepth 1 -type f -name '*.md' | sort)
  if [ -n "$unread" ]; then
    echo "PLSI: unread routine output in $outbox (show it to the user first, then move each file to $outbox/read/):"
    echo "$unread"
  fi
fi

if [ -f "$home/reminders.md" ]; then
  now="$(date +%Y-%m-%dT%H:%M)"
  due=$(awk -v now="$now" '$1 == "-" && $2 == "due" && substr($3, 1, 16) <= now' "$home/reminders.md")
  if [ -n "$due" ]; then
    echo "PLSI: reminders now due (tell the user, then delete these lines from $home/reminders.md):"
    echo "$due"
  fi
fi

if [ ! -f "$repo/.plsi/memory.md" ]; then
  echo "PLSI: not set up yet (.plsi/memory.md missing). Offer /plsi-setup."
elif ! grep -q '^- Setup: complete' "$repo/.plsi/memory.md"; then
  echo "PLSI: setup unfinished ($(grep -m1 '^- Setup:' "$repo/.plsi/memory.md" | sed 's/^- //')). Offer to resume /plsi-setup."
fi
if [ -f "$home/work/setup/ledger.md" ] && grep -q '| planned |' "$home/work/setup/ledger.md"; then
  echo "PLSI: queued setup work in $home/work/setup/ledger.md - dispatch it before anything else."
fi
exit 0
