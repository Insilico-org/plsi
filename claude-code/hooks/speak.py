"""PLSI Stop hook: read PLSI's last reply aloud when "Speak replies: on" is in .plsi/memory.md.

Claude Code's /voice is dictation only (you speak, it types). This hook adds the other half with the computer's own
text-to-speech: `say` (macOS), `spd-say`, `espeak-ng` or `espeak` (Linux), or PowerShell's speech synthesizer
(Windows / WSL). Speech runs in the background and a new reply stops the previous one. It never blocks the session
and never fails it: any problem means silence.

    echo '{"transcript_path": "..."}' | python claude-code/hooks/speak.py         # what Claude Code runs
    python claude-code/hooks/speak.py --text "Hello" [--dry-run]                   # test the voice
    python claude-code/hooks/speak.py --stop                                       # stop speaking now
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
MEMORY = REPO / ".plsi" / "memory.md"
PIDFILE = REPO / ".plsi" / "speak.pid"
MAX_CHARS = 1500
TAIL = " The rest is on screen."


def setting(name: str) -> str:
    try:
        for line in MEMORY.read_text(encoding="utf-8").splitlines():
            m = re.match(rf"\s*-\s*{re.escape(name)}:\s*(.+?)\s*$", line, re.I)
            if m:
                return m.group(1).strip().lower()
    except OSError:
        pass
    return ""


def last_reply(transcript: Path) -> str:
    """Text of the assistant messages since the user's last real prompt (tool results do not count)."""
    texts: list[str] = []
    for raw in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        kind = entry.get("type")
        content = (entry.get("message") or {}).get("content")
        if kind == "user":
            is_tool_result = isinstance(content, list) and any(
                isinstance(c, dict) and c.get("type") == "tool_result" for c in content
            )
            if not is_tool_result:
                texts = []
        elif kind == "assistant":
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                texts += [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
    # Only the final block of text is the reply; earlier ones are progress notes between tool calls.
    return texts[-1] if texts else ""


def speakable(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)              # code blocks
    text = re.sub(r"`([^`]*)`", r"\1", text)                          # inline code
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)            # links and images: keep the label
    text = re.sub(r"https?://\S+", " ", text)                         # bare URLs
    text = re.sub(r"^\s*\|?\s*:?-{3,}.*$", " ", text, flags=re.M)     # table rules
    text = re.sub(                                                    # table rows: "a, b."
        r"^\s*\|(.*)\|\s*$",
        lambda m: ", ".join(c.strip() for c in m.group(1).split("|") if c.strip()) + ".",
        text, flags=re.M,
    )
    text = re.sub(r"^\s{0,3}(#{1,6}|>|[-*+]|\d+[.)])\s+", "", text, flags=re.M)  # headings, quotes, bullets
    text = re.sub(r"[*_~]{1,3}", "", text)                            # emphasis
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        text = (cut[: end + 1] if end > MAX_CHARS // 2 else cut) + TAIL
    return text


def engine(rate: str) -> list[str] | None:
    wpm = rate if rate.isdigit() else ""
    if shutil.which("say"):
        return ["say"] + (["-r", wpm] if wpm else [])
    if shutil.which("spd-say"):
        return ["spd-say", "--wait"]
    for name in ("espeak-ng", "espeak"):
        if shutil.which(name):
            return [name] + (["-s", wpm] if wpm else [])
    ps = shutil.which("powershell.exe") or shutil.which("powershell")
    if ps:
        script = ("Add-Type -AssemblyName System.Speech; "
                  "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak([Console]::In.ReadToEnd())")
        return [ps, "-NoProfile", "-Command", script]
    return None


def stop() -> None:
    try:
        pid = int(PIDFILE.read_text(encoding="utf-8").strip())
        os.killpg(pid, signal.SIGTERM)
    except (OSError, ValueError, ProcessLookupError, AttributeError):
        pass
    PIDFILE.unlink(missing_ok=True)


def speak(text: str, dry_run: bool) -> dict:
    cmd = engine(setting("Voice rate"))
    if not cmd:
        return {"ok": False, "error": "no text-to-speech found (say, spd-say, espeak-ng, espeak or PowerShell)"}
    if dry_run:
        return {"ok": True, "engine": cmd[0], "text": text}
    stop()
    uses_stdin = cmd[0].lower().startswith("powershell")
    proc = subprocess.Popen(
        cmd if uses_stdin else cmd + [text],
        stdin=subprocess.PIPE if uses_stdin else subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    if uses_stdin and proc.stdin:
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    PIDFILE.write_text(str(proc.pid), encoding="utf-8")
    return {"ok": True, "engine": cmd[0], "chars": len(text)}


def main(argv: list[str]) -> int:
    if "--stop" in argv:
        stop()
        print(json.dumps({"ok": True, "stopped": True}))
        return 0
    dry_run = "--dry-run" in argv
    if "--text" in argv:
        i = argv.index("--text")
        text = speakable(argv[i + 1] if i + 1 < len(argv) else "")
        print(json.dumps(speak(text, dry_run)))
        return 0
    # Hook mode: Claude Code passes the event as JSON on stdin. Stay silent unless the user turned speech on.
    try:
        event = json.load(sys.stdin)
        if setting("Speak replies") != "on":
            return 0
        text = speakable(event.get("last_assistant_message") or last_reply(Path(event["transcript_path"])))
        if text:
            speak(text, dry_run)
    except Exception:  # a hook must never break the session
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
