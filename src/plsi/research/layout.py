"""The research tree on disk and the project lock: <PLSI_HOME>/research/projects/<project>/ holds project.md,
topics/, notes/ and data/; the day's budget (day.json) stays at research/, one allocation for all research.

A topic is <project>/topics/<topic>/ with topic.md, log.jsonl and one Markdown file per node. A topic's name is
unique across every project, so a topic is found by its name alone. A node's name is its sanitised title, unique
case-insensitively across the topic, so a `[[name]]` link always resolves to one file. Nothing is deleted: a node
that dies gets status `closed` and a reason. A topic folder is self-contained and opens as an Obsidian vault.

Every write inside a project folder holds that project's lock (`locked`), so parallel bots never interleave
their writes to one project.
"""

from __future__ import annotations

import contextlib
import re
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from plsi import files, paths
from plsi.clock import now
from plsi.errors import NotFound, ValidationError, warn
from plsi.research.frontmatter import read_md
from plsi.vocab.research import ResearchNodeKind, ResearchStatus

if TYPE_CHECKING:
    from plsi.research.graph import Graph

TOPIC_FILE, LOG_FILE, PROJECT_FILE = "topic.md", "log.jsonl", "project.md"
RETIRED = "retired.md"  # the retirement log in a project's notes/
PROJECTS_FOLDER, DAY_FILE = "projects", "day.json"  # in research/
TOPICS_FOLDER, NOTES_FOLDER, DATA_FOLDER = "topics", "notes", "data"  # in each project folder
STALE_LOCK_S = 60.0  # a project lock older than this was left by a crashed process
FOLDERS = {ResearchNodeKind.QUESTION: "questions", ResearchNodeKind.HYPOTHESIS: "hypotheses",
           ResearchNodeKind.FINDING: "findings"}
NAME_MAX = 150  # file names allow 255 bytes; Cyrillic costs two per character
_UNSAFE = re.compile(r'[\x00-\x1f/\\:*?"<>|\[\]#^]')


def sanitise(title: str) -> str:
    """A title as a file name: UTF-8 kept, path and wiki-link characters removed, length capped."""
    text = unicodedata.normalize("NFC", str(title or "")).replace("\n", " ")
    text = _UNSAFE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if len(text.encode("utf-8")) > NAME_MAX:
        cut = text.encode("utf-8")[:NAME_MAX].decode("utf-8", "ignore")
        text = cut.rsplit(" ", 1)[0].strip(" .") or cut.strip(" .")
        # the name is the link key, so the bot has to be told what it actually is
        warn("TITLE_SHORTENED", f"the node is named {text!r}; link to that, not to the full title")
    if paths.is_reserved(text):
        text = f"{text} node"
    if not text:
        raise ValidationError("a node title cannot be empty", hint="give the node a title in plain words")
    return text


def unique_name(graph: Graph, title: str) -> str:
    """`sanitise(title)`, with a numeric suffix on a genuine collision. The check is case-insensitive."""
    base = sanitise(title)
    taken = {n.lower() for n in graph.nodes}
    if base.lower() not in taken:
        return base
    for n in range(2, 1000):
        candidate = f"{base} {n}"
        if candidate.lower() not in taken:
            return candidate
    raise ValidationError(f"too many nodes named like {base!r}")


def root() -> Path:
    return paths.plsi_home() / "research"


def today() -> str:
    return now().date().isoformat()


_HELD: set[Path] = set()  # the project locks this process holds, so a nested write does not wait on itself


@contextlib.contextmanager
def locked(project_dir: Path) -> Iterator[None]:
    """The project's lock (`<project>/.lock`), re-entrant within one process; a stale one is broken."""
    key = project_dir.resolve()
    if key in _HELD:
        yield
        return
    project_dir.mkdir(parents=True, exist_ok=True)
    with files.lock(project_dir, stale=STALE_LOCK_S):
        _HELD.add(key)
        try:
            yield
        finally:
            _HELD.discard(key)


def project_dirs() -> list[Path]:
    base = root() / PROJECTS_FOLDER
    return sorted(p.parent for p in base.glob(f"*/{PROJECT_FILE}")) if base.is_dir() else []


def project_of(graph: Graph) -> Path:
    return graph.dir.parent.parent


def topic_dirs(project_dir: Path | None = None) -> list[Path]:
    folders = [project_dir] if project_dir else project_dirs()
    return sorted((p.parent for f in folders for p in (f / TOPICS_FOLDER).glob(f"*/{TOPIC_FILE}")),
                  key=lambda p: p.name.casefold())


def topic_dir(topic: str) -> Path:
    """A topic's folder, in whichever project holds it."""
    name = sanitise(topic).casefold()
    found = next((d for d in topic_dirs() if d.name.casefold() == name), None)
    if found is None:
        raise NotFound(f"no research topic {topic!r}", code="TOPIC_NOT_FOUND", hint="plsi research topic")
    return found


def list_topics(project_dir: Path | None = None) -> list[str]:
    return [d.name for d in topic_dirs(project_dir)]


def topic_meta(directory: Path) -> dict[str, Any]:
    return read_md(directory / TOPIC_FILE)[0]


def active_name(project_dir: Path, required: bool = True) -> str | None:
    """The project's one active topic (its daily topic). Several or none raise unless `required` is False, which
    gives the first or None."""
    active = [d.name for d in topic_dirs(project_dir) if topic_meta(d).get("status") == ResearchStatus.ACTIVE]
    if len(active) == 1:
        return active[0]
    if not required:
        return active[0] if active else None
    raise NotFound("this project has no single active topic" if not active else f"{len(active)} topics are active",
                   hint="plsi research topic --switch '<name>'")


def node_path(graph: Graph, kind: str, name: str) -> Path:
    return paths.safe_join(graph.dir, FOLDERS[ResearchNodeKind(kind)], f"{name}.md")


def append_log(graph: Graph, entry: dict[str, Any]) -> None:
    with locked(project_of(graph)):
        files.append_jsonl(graph.dir / LOG_FILE, {"at": now().isoformat(), **entry})


def read_log(graph: Graph) -> list[dict[str, Any]]:
    return files.read_jsonl(graph.dir / LOG_FILE)


def moves_logged(graph: Graph) -> int:
    return sum(1 for line in read_log(graph) if line.get("move"))
