"""The topic folder: <PLSI_HOME>/research/<topic>/ with topic.md, log.jsonl and one Markdown file per node.

A node's name is its sanitised title, unique case-insensitively across the topic, so a `[[name]]` link always
resolves to one file. Nothing is deleted: a node that dies gets status `closed` and a reason. The folder is
self-contained and opens as an Obsidian vault.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from plsi import files, paths
from plsi.clock import now
from plsi.errors import NotFound, ValidationError, warn
from plsi.research.schema import DEFAULT_DEPTH, check_depth, check_fields, link_footer, meta_of
from plsi.vocab import fold
from plsi.vocab.research import ResearchDepth, ResearchMove, ResearchNodeKind, ResearchStatus

TOPIC_FILE, LOG_FILE = "topic.md", "log.jsonl"
NOTES_FOLDER, DAY_FILE = "notes", "day.json"  # the research root's own entries, which no topic may be named
LINK_MARK = "<!-- links -->"  # everything after it is generated; invisible in Obsidian
FOLDERS = {ResearchNodeKind.QUESTION: "questions", ResearchNodeKind.HYPOTHESIS: "hypotheses",
           ResearchNodeKind.FINDING: "findings"}
NAME_MAX = 150  # file names allow 255 bytes; Cyrillic costs two per character
_UNSAFE = re.compile(r'[\x00-\x1f/\\:*?"<>|\[\]#^]')
# An HTML tag opens with a letter or a slash, so a bare `<` in "p < 0.001" is not taken for one.
_TAGS = re.compile(r"</?[A-Za-z][^<>]*/?>")


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


@dataclass
class Graph:
    """One topic, read whole."""

    name: str
    dir: Path
    topic: dict[str, Any]
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [n for n in self.nodes.values() if n.get("kind") == kind]

    def children(self, name: str) -> list[dict[str, Any]]:
        return [n for n in self.of_kind(ResearchNodeKind.QUESTION) if n.get("parent") == name]

    def hypotheses_of(self, question: str) -> list[dict[str, Any]]:
        return [n for n in self.of_kind(ResearchNodeKind.HYPOTHESIS) if n.get("question") == question]

    def findings_of(self, question: str) -> list[dict[str, Any]]:
        return [n for n in self.of_kind(ResearchNodeKind.FINDING) if n.get("question") == question]

    def tops(self) -> list[dict[str, Any]]:
        """Every direction hanging straight off the question in chief, in a stable order."""
        return sorted((n for n in self.of_kind(ResearchNodeKind.QUESTION) if not n.get("parent")),
                      key=lambda n: n["name"])

    def root(self) -> dict[str, Any] | None:
        """The top-level question that is the question in chief, or None. The question in chief lives in
        topic.md and is usually not a node, so callers that need every top-level answer read `tops()`."""
        in_chief = str(self.topic.get("question_in_chief") or "")
        if not in_chief:
            return None
        key = sanitise(in_chief)
        return next((n for n in self.tops() if n.get("title") == in_chief or n["name"] == key), None)

    def ancestry(self, name: str) -> list[str]:
        """name, then its parents up to the root. Cycle-safe."""
        chain, seen = [], set()
        while name and name in self.nodes and name not in seen:
            seen.add(name)
            chain.append(name)
            name = self.nodes[name].get("parent")
        return chain


def root() -> Path:
    return paths.plsi_home() / "research"


def today() -> str:
    return now().date().isoformat()


def _topic_name(title: str) -> str:
    """A topic title as its folder name, refused when it would be one of the research root's own entries."""
    name = sanitise(title)
    if name.lower() in {NOTES_FOLDER, DAY_FILE}:
        raise ValidationError(f"{name!r} is reserved in the research folder", code="RESERVED_NAME",
                              hint="name the topic after its question")
    return name


def topic_dir(topic: str, *, must_exist: bool = True) -> Path:
    path = paths.safe_join(root(), _topic_name(topic))
    if must_exist and not (path / TOPIC_FILE).is_file():
        raise NotFound(f"no research topic {topic!r}", code="TOPIC_NOT_FOUND", hint="plsi research topic")
    return path


def list_topics() -> list[str]:
    base = root()
    return sorted(p.parent.name for p in base.glob(f"*/{TOPIC_FILE}")) if base.is_dir() else []


def active_name(required: bool = True) -> str | None:
    """The one active topic. Several or none raise unless `required` is False, which gives the first or None."""
    active = [n for n in list_topics() if load(n).topic.get("status") == ResearchStatus.ACTIVE]
    if len(active) == 1:
        return active[0]
    if not required:
        return active[0] if active else None
    raise NotFound("no single active research topic" if not active else f"{len(active)} topics are active",
                   hint="plsi research topic --switch '<name>'")


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Markdown with YAML frontmatter, as (frontmatter, body)."""
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return {}, text
    head, _, body = text[4:].partition("\n---")
    try:
        meta = yaml.safe_load(head)
    except yaml.YAMLError as exc:
        raise ValidationError(f"unreadable frontmatter: {exc}") from None
    return (meta if isinstance(meta, dict) else {}), body.lstrip("\n")


def render(meta: dict[str, Any], body: str) -> str:
    clean = {k: v for k, v in meta.items() if v not in (None, [], {}, "")}
    head = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False, width=100).rstrip("\n")
    return f"---\n{head}\n---\n\n{body.strip()}\n"


def load(topic: str) -> Graph:
    """Read a whole topic. A file whose declared kind differs from its folder is skipped with a warning."""
    directory = topic_dir(topic)
    meta, body = parse((directory / TOPIC_FILE).read_text(encoding="utf-8"))
    graph = Graph(name=directory.name, dir=directory, topic={**meta, "kind": ResearchNodeKind.TOPIC,
                                                             "name": directory.name, "body": body})
    for kind, folder in FOLDERS.items():
        for path in sorted((directory / folder).glob("*.md")) if (directory / folder).is_dir() else []:
            node_meta, node_body = parse(path.read_text(encoding="utf-8"))
            declared = str(node_meta.get("kind") or kind)
            if declared != kind:
                warn("FOREIGN_NODE", f"{path.name} in {folder}/ declares kind {declared!r}; it is not part of "
                                     "the graph and was skipped. Notes belong in research/notes/")
                continue
            graph.nodes[path.stem] = {**node_meta, "kind": kind, "name": path.stem, "body": node_body}
    return graph


def prose(body: str) -> str:
    """The bot's own words, without the generated link footer."""
    return str(body or "").split(LINK_MARK)[0].rstrip()


def _flat(text: Any) -> str:
    """Letters and digits only, with markup removed, so the quote check ignores case, spacing and typography."""
    return fold(_TAGS.sub("", str(text or "")))


def verify_quotes(meta: dict[str, Any]) -> dict[str, Any]:
    """Set each source's `quote_verified`: true when the quote occurs in the `text` passed with it.

    This checks the quote against the passage the bot supplied, not against the publication itself. The text
    is dropped rather than stored; a source passed without text keeps its earlier value."""
    for source in meta.get("sources") or []:
        if not isinstance(source, dict):
            continue
        was = bool(source.get("quote_verified"))
        quote, text = _flat(source.get("quote")), _flat(source.pop("text", ""))
        source["quote_verified"] = bool(quote and quote in text) if text else was
    return meta


def node_path(graph: Graph, kind: str, name: str) -> Path:
    return paths.safe_join(graph.dir, FOLDERS[ResearchNodeKind(kind)], f"{name}.md")


def write_node(graph: Graph, kind: str, name: str, meta: dict[str, Any], body: str) -> Path:
    """Write one node and register it in the in-memory graph. Callers check links first (refusal 6)."""
    check_fields(kind, meta)
    if kind == ResearchNodeKind.FINDING:
        verify_quotes(meta)
    stored = {"kind": str(kind), **meta_of(meta), "updated": today()}
    footer = link_footer(kind, meta)
    text = render(stored, "\n\n".join(p for p in (prose(body), f"{LINK_MARK}\n{footer}" if footer else "") if p))
    path = node_path(graph, kind, name)
    files.atomic_write_text(path, text)
    graph.nodes[name] = {**stored, "kind": kind, "name": name, "body": body}
    return path


def write_topic(graph: Graph) -> Path:
    meta = meta_of(graph.topic)
    check_fields(ResearchNodeKind.TOPIC, meta)
    path = graph.dir / TOPIC_FILE
    files.atomic_write_text(path, render({"kind": str(ResearchNodeKind.TOPIC), **meta,
                                          "updated": today()}, graph.topic.get("body", "")))
    return path


def create_topic(title: str, question_in_chief: str, source: dict[str, Any] | None = None,
                 depth: str | None = None) -> Graph:
    name = _topic_name(title)
    directory = paths.safe_join(root(), name)
    if (directory / TOPIC_FILE).is_file():
        raise ValidationError(f"topic {name!r} already exists", hint=f"plsi research topic --switch '{name}'")
    graph = Graph(name=name, dir=directory, topic={
        "kind": ResearchNodeKind.TOPIC, "name": name, "title": title, "question_in_chief": question_in_chief,
        "status": str(ResearchStatus.ACTIVE), "cursor": {"question": None, "move": str(ResearchMove.ASK), "attempt": 0},
        "cycles": 0, "source": source or {}, "depth": str(check_depth(depth)),
        "body": f"# {title}\n\n{question_in_chief}\n"})
    write_topic(graph)
    return graph


def depth_of(graph: Graph) -> ResearchDepth:
    """This topic's depth; a missing or hand-edited value reads as the default, with a warning, rather than
    failing every command."""
    try:
        return check_depth(graph.topic.get("depth"))
    except ValidationError:
        warn("BAD_DEPTH", f"topic {graph.name!r} has depth {graph.topic.get('depth')!r}; it reads as {DEFAULT_DEPTH}")
        return DEFAULT_DEPTH


def append_log(graph: Graph, entry: dict[str, Any]) -> None:
    files.append_jsonl(graph.dir / LOG_FILE, {"at": now().isoformat(), **entry})


def read_log(graph: Graph) -> list[dict[str, Any]]:
    return files.read_jsonl(graph.dir / LOG_FILE)


def moves_logged(graph: Graph) -> int:
    """How many moves the topic's log holds."""
    return sum(1 for line in read_log(graph) if line.get("move"))
