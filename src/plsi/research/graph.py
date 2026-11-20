"""The in-memory read-model of one topic: the `Graph` that holds the topic frontmatter and every node, the
`load` that reads a topic folder whole, and the writes that put a node or the topic back on disk under the
project lock. A file whose declared kind differs from its folder is not part of the graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from plsi import paths
from plsi import files
from plsi.errors import ValidationError, warn
from plsi.research.frontmatter import LINK_MARK, prose, read_md, render, verify_quotes
from plsi.research.layout import (FOLDERS, TOPIC_FILE, TOPICS_FOLDER, list_topics, locked, node_path, project_of,
                                  sanitise, today, topic_dir)
from plsi.research.schema import check_depth, check_fields, link_footer, meta_of
from plsi.research.tuning import DEFAULT_DEPTH
from plsi.vocab.research import ResearchDepth, ResearchMove, ResearchNodeKind, ResearchStatus


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


def load(topic: str) -> Graph:
    """Read a whole topic. A file whose declared kind differs from its folder is skipped with a warning."""
    directory = topic_dir(topic)
    meta, body = read_md(directory / TOPIC_FILE)
    graph = Graph(name=directory.name, dir=directory, topic={**meta, "kind": ResearchNodeKind.TOPIC,
                                                             "name": directory.name, "body": body})
    for kind, folder in FOLDERS.items():
        for path in sorted((directory / folder).glob("*.md")) if (directory / folder).is_dir() else []:
            node_meta, node_body = read_md(path)
            declared = str(node_meta.get("kind") or kind)
            if declared != kind:
                warn("FOREIGN_NODE", f"{path.name} in {folder}/ declares kind {declared!r}; it is not part of "
                                     "the graph and was skipped. Notes belong in the project's notes/")
                continue
            graph.nodes[path.stem] = {**node_meta, "kind": kind, "name": path.stem, "body": node_body}
    return graph


def write_node(graph: Graph, kind: str, name: str, meta: dict[str, Any], body: str) -> Path:
    """Write one node and register it in the in-memory graph. Callers check links first (refusal 6)."""
    check_fields(kind, meta)
    if kind == ResearchNodeKind.FINDING:
        verify_quotes(meta)
    stored = {"kind": str(kind), **meta_of(meta), "updated": today()}
    footer = link_footer(kind, meta)
    text = render(stored, "\n\n".join(p for p in (prose(body), f"{LINK_MARK}\n{footer}" if footer else "") if p))
    path = node_path(graph, kind, name)
    with locked(project_of(graph)):
        files.atomic_write_text(path, text)
    graph.nodes[name] = {**stored, "kind": kind, "name": name, "body": body}
    return path


def write_topic(graph: Graph) -> Path:
    meta = meta_of(graph.topic)
    check_fields(ResearchNodeKind.TOPIC, meta)
    path = graph.dir / TOPIC_FILE
    with locked(project_of(graph)):
        files.atomic_write_text(path, render({"kind": str(ResearchNodeKind.TOPIC), **meta,
                                              "updated": today()}, graph.topic.get("body", "")))
    return path


def create_topic(title: str, question_in_chief: str, project_dir: Path, project: str,
                 source: dict[str, Any] | None = None, depth: str | None = None) -> Graph:
    """A new topic in the project's topics/; its name may be taken in no project."""
    name = sanitise(title)
    if name.casefold() in {n.casefold() for n in list_topics()}:
        raise ValidationError(f"topic {name!r} already exists", hint=f"plsi research topic --switch '{name}'")
    directory = paths.safe_join(project_dir, TOPICS_FOLDER, name)
    graph = Graph(name=name, dir=directory, topic={
        "kind": ResearchNodeKind.TOPIC, "name": name, "title": title, "question_in_chief": question_in_chief,
        "status": str(ResearchStatus.ACTIVE), "cursor": {"question": None, "move": str(ResearchMove.ASK), "attempt": 0},
        "cycles": 0, "source": source or {}, "depth": str(check_depth(depth)), "project": project,
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


def summaries(project_dir: Path | None = None) -> list[dict[str, Any]]:
    """Every topic, or one project's, one entry each with its project's id."""
    out = []
    for name in list_topics(project_dir):
        graph = load(name)
        out.append({"topic": name, "project": graph.topic.get("project"), "status": str(graph.topic.get("status")),
                    "question_in_chief": graph.topic.get("question_in_chief"), "depth": str(depth_of(graph)),
                    "cursor": graph.topic.get("cursor"), "cycles": graph.topic.get("cycles", 0),
                    "nodes": len(graph.nodes), "source": graph.topic.get("source") or {}})
    return out
