"""`plsi skills lint`: every skill page (skills/<bot>/<skill>/SKILL.md) checked against the rules code can see -
AGENTS.md "Where a skill goes" and the roster in skills/shared/team. Reads files only and changes nothing.

Refused (one violation each, rule from SkillRule): a bot the roster, BotRole and the skill folders do not all name;
a command the roster or a page names that `plsi` does not have; a page without frontmatter, whose `name:` is not its
folder, or whose `description:` does not open as AGENTS.md says. Warned: a page longer than LONG_PAGE lines.
Commands are read only from code (inline backticks and fenced blocks), so prose such as "the plsi toolbelt" is not one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from plsi import errors
from plsi.commands import COMMANDS
from plsi.errors import GateFailed, violation
from plsi.paths import REPO_ROOT
from plsi.vocab import BotRole, SkillRule

SKILLS_DIR = REPO_ROOT / "skills"
SHARED = "shared"
ROSTER = Path(SHARED) / "team" / "SKILL.md"  # relative to the skills folder
LONG_PAGE = 300  # lines: AGENTS.md's soft limit for a module, used as a warning for a page
OWN_OPENING, SHARED_OPENING = "Use as ", "Use when "

_FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_FENCE = re.compile(r"^[ \t]*```[^\n]*\n(.*?)^[ \t]*```", re.S | re.M)  # also fences indented under a list item
_INLINE = re.compile(r"`([^`\n]+)`")
_CALL = re.compile(r"(?:^|(?<!from)(?<!import)[\s(;|&])plsi((?: [a-z][a-z0-9-]*){1,3})")  # not Python's "from plsi import keys"
_ROW = re.compile(r"^\|(.+)\|\s*$")


@dataclass(frozen=True)
class Page:
    rel: str  # e.g. "lab/research", for messages
    bot: str  # the folder under skills/
    folder: str  # the skill's folder name
    text: str


def _pages(root: Path) -> list[Page]:
    out = []
    for path in sorted(root.glob("*/*/SKILL.md")):
        bot, folder = path.parent.parent.name, path.parent.name
        out.append(Page(f"{bot}/{folder}", bot, folder, path.read_text(encoding="utf-8")))
    return out


def _code(text: str) -> str:
    """Only the code in a page: fenced blocks and inline backtick spans, one per line."""
    return "\n".join([m.group(1) for m in _FENCE.finditer(text)]
                     + [m.group(1) for m in _INLINE.finditer(_FENCE.sub("", text))])


def _known(words: list[str], commands: set[str]) -> bool:
    """A command followed by its arguments (`plsi refs show us_npi`), or a group named alone (`plsi research`,
    `plsi oracle pandaomics`); a group followed by a word that is not its command (`plsi plan approve`) is not."""
    if any(" ".join(words[:n]) in commands for n in range(len(words), 0, -1)):
        return True
    group = " ".join(words) + " "
    return any(c.startswith(group) for c in commands)


def _calls(text: str) -> list[list[str]]:
    return [m.group(1).split() for m in _CALL.finditer(_code(text))]


def _expand(cell: str) -> list[list[str]]:
    """A roster Commands cell -> command words: `calc range/convert` is calc range and calc convert; flags dropped."""
    out = []
    for token in _INLINE.findall(cell):
        token = token.split(" --")[0].strip()
        if not token or token.startswith("-") or "<" in token:
            continue
        head, _, tail = token.partition(" ")
        out += [[head, *sub.split()] for sub in tail.split("/")] if tail else [[head]]
    return out


def roster(text: str) -> dict[str, str]:
    """The roster table of skills/shared/team -> {role slug: Commands cell}."""
    out = {}
    for line in text.splitlines():
        if (m := _ROW.match(line)) and len(cells := [c.strip() for c in m.group(1).split("|")]) == 5:
            if slug := re.fullmatch(r"`([a-z]+)`", cells[2]):
                out[slug.group(1)] = cells[4]
    return out


def _bots(rows: dict[str, str], folders: set[str]) -> list[dict[str, str]]:
    named = {"roster": set(rows), "BotRole": {r.value for r in BotRole}, "skill folders": folders}
    out = []
    for slug in sorted(set().union(*named.values())):
        if missing := [where for where, slugs in named.items() if slug not in slugs]:
            out.append(violation(str(ROSTER), SkillRule.BOT_LISTED,
                                 f"bot `{slug}` is missing from: {', '.join(missing)}",
                                 "the roster row, BotRole in plsi.vocab and skills/<bot>/ change together"))
    return out


def _roster_commands(rows: dict[str, str], commands: set[str]) -> list[dict[str, str]]:
    return [violation(str(ROSTER), SkillRule.COMMAND_EXISTS, f"the `{slug}` row lists `plsi {' '.join(words)}`, "
                      "which plsi does not have", "plsi --help lists the commands")
            for slug, cell in rows.items() for words in _expand(cell) if not _known(words, commands)]


def _page_commands(page: Page, commands: set[str]) -> list[dict[str, str]]:
    seen, out = set(), []
    for words in _calls(page.text):
        if not _known(words, commands) and (name := " ".join(words)) not in seen:
            seen.add(name)
            out.append(violation(page.rel, SkillRule.COMMAND_EXISTS, f"names `plsi {name}`, which plsi does not have",
                                 "plsi --help lists the commands"))
    return out


def _page_front(page: Page) -> list[dict[str, str]]:
    m = _FRONT.match(page.text)
    front = yaml.safe_load(m.group(1)) if m else None
    if not isinstance(front, dict):
        return [violation(page.rel, SkillRule.FRONTMATTER, "no frontmatter (--- name, description ---) at the top")]
    out = []
    if front.get("name") != page.folder:
        out.append(violation(page.rel, SkillRule.NAME_MATCHES_FOLDER,
                             f"name `{front.get('name')}` is not the folder name `{page.folder}`"))
    opening = SHARED_OPENING if page.bot == SHARED else OWN_OPENING
    if not str(front.get("description") or "").startswith(opening):
        kind = "a shared page" if page.bot == SHARED else "a bot's own page"
        out.append(violation(page.rel, SkillRule.DESCRIPTION_OPENING,
                             f"description must open \"{opening}…\" ({kind})", "AGENTS.md, Where a skill goes"))
    return out


def check(root: Path, commands: set[str]) -> tuple[list[dict[str, str]], list[str]]:
    """-> (violations, long pages). Pure over the folder and the command names, for tests."""
    pages = _pages(root)
    roster_path = root / ROSTER
    rows = roster(roster_path.read_text(encoding="utf-8")) if roster_path.is_file() else {}
    found = _bots(rows, {p.bot for p in pages} - {SHARED}) + _roster_commands(rows, commands)
    for page in pages:
        found += _page_front(page) + _page_commands(page, commands)
    long = [f"{p.rel} has {n} lines" for p in pages if (n := len(p.text.splitlines())) > LONG_PAGE]
    return found, long


def lint() -> dict[str, Any]:
    """`skills lint`: every skill page against the rules; GATE_FAILED lists every violation."""
    found, long = check(SKILLS_DIR, set(COMMANDS))
    if found:
        raise GateFailed(found, "skill pages break the rules")
    for line in long:
        errors.warn("LONG_PAGE", f"{line} (over {LONG_PAGE}); a page read on every run stays short")
    return {"pages": len(_pages(SKILLS_DIR)), "bots": len(roster((SKILLS_DIR / ROSTER).read_text(encoding="utf-8"))),
            "commands": len(COMMANDS)}
