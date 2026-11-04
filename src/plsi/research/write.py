"""Turning one save payload into node files.

Names are allocated before anything is written so nodes in one save can link to each other, and every shape is
checked before the first write.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import ValidationError
from plsi.research import store
from plsi.research.schema import check_fields, check_vocabulary, meta_of
from plsi.vocab.research import ResearchNodeKind, ResearchStatus, Stakes


def _accumulate_search(node: dict[str, Any], update: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """Add this move's `last_search` rounds and hits to the question's totals; `new` stays this round's."""
    fresh, prior = update.get("last_search"), node.get("last_search")
    if not isinstance(fresh, dict) or not isinstance(prior, dict):
        return meta
    meta["last_search"] = {**fresh,
                           "rounds": int(prior.get("rounds") or 0) + int(fresh.get("rounds") or 0),
                           "hits": int(prior.get("hits") or 0) + int(fresh.get("hits") or 0)}
    return meta


def _node_meta(node: dict[str, Any]) -> dict[str, Any]:
    """A new node's fields with defaults. A question's `link` is not defaulted: only the bot knows it."""
    meta = {k: v for k, v in node.items() if k not in ("kind", "title", "body")}
    meta.setdefault("title", node.get("title") or "")
    meta.setdefault("status", str(ResearchStatus.OPEN))
    if node.get("kind") == ResearchNodeKind.QUESTION:
        meta.setdefault("stakes", str(Stakes.SOME))
    return meta


def check_shapes(graph: store.Graph, nodes: list[dict[str, Any]], updates: list[dict[str, Any]]) -> None:
    """Field-level validation of the whole payload, up front. Fields are checked on the node as it will be
    stored; closed vocabularies only on what the payload writes."""
    for index, node in enumerate(nodes):
        meta = _node_meta(node)
        try:
            check_fields(str(node["kind"]), meta)
            check_vocabulary(str(node["kind"]), meta)
        except ValidationError as exc:
            raise ValidationError(f"nodes[{index}] {node.get('title') or ''}: {exc.message}",
                                  code=exc.code, hint=exc.hint) from None
    for index, update in enumerate(updates):
        node = graph.nodes[str(update["name"])]
        written = {k: v for k, v in update.items() if k != "name"}
        try:
            check_fields(str(node["kind"]), {**meta_of(node), **written}, written)
            check_vocabulary(str(node["kind"]), written)
        except ValidationError as exc:
            raise ValidationError(f"update[{index}] {update['name']}: {exc.message}",
                                  code=exc.code, hint=exc.hint) from None


def allocate(graph: store.Graph, nodes: list[dict[str, Any]]) -> dict[int, str]:
    """A name per new node before anything is written, so nodes in one save can link to each other."""
    provisional = store.Graph(name=graph.name, dir=graph.dir, topic=graph.topic, nodes=dict(graph.nodes))
    names: dict[int, str] = {}
    for index, node in enumerate(nodes):
        if not node.get("kind") or node["kind"] not in tuple(ResearchNodeKind) or node["kind"] == ResearchNodeKind.TOPIC:
            raise ValidationError(f"nodes[{index}]: kind must be question, hypothesis or finding")
        names[index] = store.unique_name(provisional, node.get("title") or "")
        provisional.nodes[names[index]] = {"kind": node["kind"], "name": names[index]}
    return names


def resolve_name(value: str, by_title: dict[str, str]) -> str:
    """The stored name for a title, when the node is one this save is creating."""
    return by_title.get(store.sanitise(value), value)


def _as_names(value: Any, where: str, by_title: dict[str, str]) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{where} is one node name or a list of them, not {type(value).__name__}",
                              code="NOT_A_NAME_LIST", hint=f'{where}: ["<a node>", "<another>"]')
    return [resolve_name(str(v), by_title) for v in value]


def resolve_links(graph: store.Graph, nodes: list[dict[str, Any]], updates: list[dict[str, Any]],
                  names: dict[int, str]) -> dict[str, str]:
    """Rewrite every link in the payload to a stored name. A link may name an existing node or the title of one
    created in this save; an existing node always wins, so re-proposing a title cannot redirect links to the
    suffixed copy. Returns the title-to-name map for new nodes."""
    by_title: dict[str, str] = {}
    for index, node in enumerate(nodes):
        key = store.sanitise(node.get("title") or "")
        if key in graph.nodes or key in by_title:
            continue
        by_title[key] = names[index]
    for item in [*nodes, *updates]:
        for key in ("parent", "question"):
            if item.get(key):
                item[key] = resolve_name(str(item[key]), by_title)
        for key in ("tested_by", "supports", "contradicts", "cites"):
            if item.get(key):
                item[key] = _as_names(item[key], key, by_title)
        boundaries = item.get("boundaries")
        if isinstance(boundaries, dict):
            boundaries = item["boundaries"] = [boundaries]
        for boundary in boundaries or []:
            if boundary.get("between"):
                boundary["between"] = _as_names(boundary["between"], "boundaries.between", by_title)
            if boundary.get("spawned"):
                boundary["spawned"] = resolve_name(str(boundary["spawned"]), by_title)
    return by_title


def _keep(graph: store.Graph, kind: str, name: str, undo: dict[Path, str | None]) -> None:
    """Record a node file's text before its first write in this save; None when the file is new."""
    path = store.node_path(graph, kind, name)
    undo.setdefault(path, path.read_text(encoding="utf-8") if path.is_file() else None)


def write_nodes(graph: store.Graph, nodes: list[dict[str, Any]], names: dict[int, str],
                undo: dict[Path, str | None]) -> list[str]:
    """Write the new nodes, recording each file in `undo` so the caller can roll the save back."""
    out = []
    for index, node in enumerate(nodes):
        meta = _node_meta(node)
        meta["title"] = node.get("title") or names[index]
        _keep(graph, str(node["kind"]), names[index], undo)
        store.write_node(graph, str(node["kind"]), names[index], meta, str(node.get("body") or ""))
        out.append(names[index])
    return out


def apply_updates(graph: store.Graph, updates: list[dict[str, Any]], undo: dict[Path, str | None]) -> list[str]:
    """Merge each update into its stored node and rewrite it, recording each file's old text in `undo`."""
    touched = []
    for update in updates:
        name = str(update["name"])
        node = graph.nodes[name]
        meta = {**meta_of(node), **{k: v for k, v in update.items() if k != "name"}}
        meta = _accumulate_search(node, update, meta)
        _keep(graph, str(node["kind"]), name, undo)
        store.write_node(graph, str(node["kind"]), name, meta, str(update.get("body") or node.get("body") or ""))
        touched.append(name)
    return touched


def rollback(undo: dict[Path, str | None]) -> None:
    """Put every file a failed save wrote back as it was: new files removed, updated ones restored."""
    for path, text in undo.items():
        if text is None:
            path.unlink(missing_ok=True)
        else:
            files.atomic_write_text(path, text)
