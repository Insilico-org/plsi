"""Generate PLSI worker subagents for Claude Code from the roster in skills/shared/team/SKILL.md.

The roster table stays the single source: each worker row becomes .claude/agents/plsi-<role>.md (gitignored).

    python claude-code/gen_agents.py --list                 # roster with tiers and what is installed
    python claude-code/gen_agents.py --tiers core           # create every core worker
    python claude-code/gen_agents.py --add coach sleep      # create named workers (role slugs)
    python claude-code/gen_agents.py --remove coach         # delete a worker's agent file
    python claude-code/gen_agents.py --sync                 # rewrite installed workers after a roster update

Prints one JSON object: {"ok": ..., "created": [...], "removed": [...], "installed": [...], "error": ...}.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROSTER = REPO / "skills" / "shared" / "team" / "SKILL.md"
AGENTS = REPO / ".claude" / "agents"
PREFIX = "plsi-"
TOOLS = "Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch"
COLUMNS = ["bot", "display", "role", "tier", "description", "opening", "commands"]

BODY = """You are **{display}** ({bot}), role `{role}`, a worker in the PLSI team, running as a Claude Code subagent.
{opening}

## Operating rules

1. Before every task, read `skills/shared/team/SKILL.md` and `claude-code/RUNTIME.md`. The skills were written for
   Grok Bot; RUNTIME.md says what each Grok mechanism is on Claude Code.
2. Adopt `persona.md` as your persona.
3. Your skills are the ones in `skills/{role}/` ({skills}); read the one the request names from there, plus
   `skills/shared/`, and use no others. The `plsi` commands of your roster row: {commands}. Work for another bot goes
   in your handoff, naming its skill path; PLSI dispatches it.
4. You work only on handoffs from PLSI. The prompt you get is one handoff JSON (a `request`, or a `request` then a
   line `---` then its `answer`). Never address the user, never ask them anything directly, never create routines,
   schedules or notifications.
5. Your final message is exactly ONE handoff JSON object, `result` or `question`, with `sender` `{role}` and
   `recipient` `orchestrator`, on the request's thread, and nothing after it. Check it first with
   `plsi handoff check --file -` (pipe the JSON in) and send it only when `ok` is true. Answer every request, also when
   it failed. Put all questions for a step in ONE `question` handoff; PLSI will call you again with the `answer`.
6. You keep no memory between calls: everything you need is in the handoff, the instance it names and
   `<PLSI_HOME>/work/<thread>/`. Each person has their own instance (the user's has relation `self`, usually `me`);
   work only on the one the handoff names.
7. Never edit `events.jsonl`, never bypass a gate, never read or print secret values or `~/.config/plsi/env`.
"""


def roster() -> list[dict[str, str]]:
    rows = []
    for line in ROSTER.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| PLSI"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(COLUMNS):
            raise ValueError(f"roster row has {len(cells)} cells, expected {len(COLUMNS)}: {cells[0]}")
        row = dict(zip(COLUMNS, cells))
        row["role"] = row["role"].strip("`")
        rows.append(row)
    if not rows:
        raise ValueError(f"no roster rows found in {ROSTER}")
    return rows


def agent_file(role: str) -> Path:
    return AGENTS / f"{PREFIX}{role}.md"


def render(row: dict[str, str]) -> str:
    skills_dir = REPO / "skills" / row["role"]
    skills = sorted(p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()) if skills_dir.is_dir() else []
    skill_list = ", ".join(f"`{row['role']}/{s}`" for s in skills) or "none yet"
    section = {"physician": " Section: PLSI Clinic.", "researcher": " Section: PLSI Lab."}.get(row["tier"], "")
    description = (
        f"{row['display']} ({row['bot']}). {row['description']}{section} "
        "Works only on handoffs from PLSI and replies only to PLSI; never messages the user."
    )
    front = "\n".join([
        "---",
        f"name: {PREFIX}{row['role']}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        f"tools: {TOOLS}",
        "model: inherit",
        "---",
        "",
    ])
    body = BODY.format(
        display=row["display"], bot=row["bot"], role=row["role"], opening=row["opening"],
        skills=skill_list, commands=re.sub(r"\s+", " ", row["commands"]),
    )
    return front + body


def installed() -> list[str]:
    return sorted(p.stem[len(PREFIX):] for p in AGENTS.glob(f"{PREFIX}*.md")) if AGENTS.is_dir() else []


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tiers", help="comma-separated tiers to create (core, recommended, optional, physician, researcher)")
    ap.add_argument("--add", nargs="*", default=[], metavar="ROLE")
    ap.add_argument("--remove", nargs="*", default=[], metavar="ROLE")
    ap.add_argument("--sync", action="store_true", help="rewrite every installed worker from the roster")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    out: dict = {"ok": True, "created": [], "removed": [], "error": None}
    try:
        rows = {r["role"]: r for r in roster() if r["role"] != "orchestrator"}
        if args.list:
            have = set(installed())
            out["roster"] = [
                {"role": r["role"], "display": r["display"], "tier": r["tier"], "installed": r["role"] in have}
                for r in rows.values()
            ]
        want = list(args.add)
        if args.tiers:
            tiers = {t.strip() for t in args.tiers.split(",") if t.strip()}
            want += [role for role, r in rows.items() if r["tier"] in tiers]
        if args.sync:
            want += [role for role in installed() if role in rows]
        unknown = [r for r in want + args.remove if r not in rows]
        if unknown:
            raise ValueError(f"unknown role slug(s): {', '.join(unknown)}; see --list")
        AGENTS.mkdir(parents=True, exist_ok=True)
        for role in dict.fromkeys(want):
            agent_file(role).write_text(render(rows[role]), encoding="utf-8")
            out["created"].append(role)
        for role in args.remove:
            f = agent_file(role)
            if f.exists():
                f.unlink()
                out["removed"].append(role)
    except (OSError, ValueError) as exc:
        out.update(ok=False, error=str(exc))
    out["installed"] = installed()
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
