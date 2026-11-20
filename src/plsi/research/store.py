"""The research store: the public surface for reading and writing a topic on disk. The work is split by concern
across `frontmatter` (Markdown with YAML frontmatter, and the text operations on a node's body), `layout` (the
tree on disk, the project lock, and topic/project naming) and `graph` (the in-memory `Graph` read-model and the
writes that put a node or the topic back). This module re-exports that surface so `from plsi.research.store import
X` and `store.X` keep working from one place."""

from __future__ import annotations

from plsi.research.frontmatter import (LINK_MARK, clip, parse, prose, read_md, render, verify_quotes)
from plsi.research.graph import (Graph, create_topic, depth_of, load, summaries, write_node, write_topic)
from plsi.research.layout import (DATA_FOLDER, DAY_FILE, FOLDERS, LOG_FILE, NAME_MAX, NOTES_FOLDER, PROJECT_FILE,
                                  PROJECTS_FOLDER, RETIRED, STALE_LOCK_S, TOPIC_FILE, TOPICS_FOLDER, active_name,
                                  append_log, list_topics, locked, moves_logged, node_path, project_dirs,
                                  project_of, read_log, root, sanitise, today, topic_dir, topic_dirs, topic_meta,
                                  unique_name)

__all__ = [
    # frontmatter: Markdown with YAML frontmatter and node-body text
    "LINK_MARK", "parse", "read_md", "render", "prose", "clip", "verify_quotes",
    # layout: the tree on disk, the project lock, naming
    "TOPIC_FILE", "LOG_FILE", "PROJECT_FILE", "RETIRED", "PROJECTS_FOLDER", "DAY_FILE", "TOPICS_FOLDER",
    "NOTES_FOLDER", "DATA_FOLDER", "STALE_LOCK_S", "FOLDERS", "NAME_MAX",
    "sanitise", "unique_name", "root", "today", "locked", "project_dirs", "project_of", "topic_dirs",
    "topic_dir", "list_topics", "topic_meta", "active_name", "node_path", "append_log", "read_log",
    "moves_logged",
    # graph: the read-model and its writes
    "Graph", "load", "write_node", "write_topic", "create_topic", "depth_of", "summaries",
]
