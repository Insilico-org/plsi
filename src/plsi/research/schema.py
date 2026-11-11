"""The node schema: which fields each kind carries, which values the closed ones take, and what a node links to."""

from __future__ import annotations

from typing import Any

from plsi.errors import ValidationError
from plsi.research.tuning import DEFAULT_DEPTH
from plsi.vocab.research import (KIND_STATUSES, QuestionLink, ResearchDepth, ResearchDesign, ResearchNodeKind,
                                 ResearchSpecies)

# (required at creation, optional) per kind. `title` keeps the title as written, since the file name is
# sanitised; `updated` is set on every write.
FIELDS: dict[ResearchNodeKind, tuple[tuple[str, ...], tuple[str, ...]]] = {
    ResearchNodeKind.TOPIC: (
        ("question_in_chief", "status", "cursor", "cycles"),
        ("title", "updated", "source", "depth", "project", "ended_reason", "superseded", "reframed_at_move"),
    ),
    ResearchNodeKind.QUESTION: (
        ("status", "stakes"),
        ("title", "updated", "parent", "link", "gap", "gap_why", "angle", "last_search", "answer", "cites",
         "closed_reason"),
    ),
    ResearchNodeKind.HYPOTHESIS: (
        ("question", "if_false", "status"),
        ("title", "updated", "tested_by", "boundaries", "closed_reason"),
    ),
    ResearchNodeKind.FINDING: (
        ("question", "design", "species", "sources"),
        # `observed` is when the thing happened; free text, because nothing compares two of them
        ("title", "updated", "status", "supports", "contradicts", "population", "origin", "studies", "observed"),
    ),
}
NODE_KEYS = ("kind", "name", "body")  # held in memory beside the frontmatter, never written into it
CLOSED = {"design": (tuple(ResearchDesign), "the shape of the evidence"),
          "species": (tuple(ResearchSpecies), "what the result is about")}
# the fields that name other nodes: one name each, or a list of names (boundaries carry their own, below)
NAME_LINKS, LIST_LINKS = ("parent", "question"), ("tested_by", "supports", "contradicts", "cites")
FOOTER_LABELS = {"supports": "Supports", "contradicts": "Against", "tested_by": "Would be settled by",
                 "cites": "Cites"}


def meta_of(node: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in node.items() if k not in NODE_KEYS}


def search_counts(node: dict[str, Any] | None) -> dict[str, int]:
    """A question's `last_search` as whole numbers (`rounds`, `hits`, `new`), 0 where nothing is recorded."""
    search = (node or {}).get("last_search") or {}
    return {key: int(search.get(key) or 0) for key in ("rounds", "hits", "new")}


def where(section: str, index: int, label: Any) -> str:
    """A payload item's place, as errors and refusals name it: `nodes[0] <title>` or `update[1] <name>`."""
    return f"{section}[{index}] {label or ''}".strip()


def check_fields(kind: str, meta: dict[str, Any], written: dict[str, Any] | None = None) -> None:
    """Required fields present, no unknown field, status legal for the kind.

    Unknown fields are judged on `written` (what this payload sets) when given, else on `meta`."""
    required, optional = FIELDS[ResearchNodeKind(kind)]
    missing = [f for f in required if meta.get(f) in (None, "", [])]
    unknown = [f for f in (meta if written is None else written)
               if f not in required and f not in optional and f not in NODE_KEYS]
    if missing or unknown:
        raise ValidationError(
            f"{kind}: " + "; ".join([*(f"missing {f}" for f in missing), *(f"unknown field {f}" for f in unknown)]),
            hint=f"a {kind} carries: {', '.join(required)} (required), {', '.join(optional)}")
    status = meta.get("status")
    if status and status not in KIND_STATUSES[ResearchNodeKind(kind)]:
        raise ValidationError(f"{kind} cannot have status {status!r}",
                              hint=f"one of {', '.join(sorted(KIND_STATUSES[ResearchNodeKind(kind)]))}")
    if kind == ResearchNodeKind.QUESTION and meta.get("parent") and not meta.get("link"):
        raise ValidationError("a child question records how it hangs off its parent",
                              hint="link: decomposes (the parent waits and rolls up) or continues (the branch goes on)")


def check_vocabulary(kind: str, written: dict[str, Any]) -> None:
    """Refuse a finding's `design` or `species` outside its closed list, naming the list. Checks only what the
    payload writes."""
    if kind != ResearchNodeKind.FINDING:
        return
    for field_name, (allowed, where) in CLOSED.items():
        value = written.get(field_name)
        if value and str(value) not in allowed:
            raise ValidationError(f"finding: {field_name} {value!r} is not one of the {len(allowed)} values",
                                  code="CLOSED_VOCABULARY",
                                  hint=f"{field_name} is {where} and code counts on it: "
                                       f"{', '.join(allowed)}. The detail goes in `population` and the body")


def check_depth(value: Any) -> ResearchDepth:
    """A depth the user named, refused with the list when it is not one of the four; empty is the default."""
    if value in (None, ""):
        return DEFAULT_DEPTH
    if str(value) not in tuple(ResearchDepth):
        raise ValidationError(f"unknown depth {value!r}", code="CLOSED_VOCABULARY",
                              hint="one of " + ", ".join(ResearchDepth)
                                   + ". `fast` takes whatever answer the evidence allows; `deep` and "
                                     "`exhaustive` will not call a topic answered without replication")
    return ResearchDepth(str(value))


def links_of(meta: dict[str, Any]) -> list[str]:
    out = [str(meta[f]) for f in NAME_LINKS if meta.get(f)]
    for field_name in LIST_LINKS:
        out += [str(v) for v in (meta.get(field_name) or [])]
    for boundary in meta.get("boundaries") or []:
        out += [str(v) for v in (boundary.get("between") or [])]
        if boundary.get("spawned"):
            out.append(str(boundary["spawned"]))
    return out


def link_footer(kind: str, meta: dict[str, Any]) -> str:
    """The `[[name]]` lines written below a node's body, so the folder reads as an Obsidian vault."""
    parts = []
    if meta.get("parent"):
        parts.append(f"{'Part of' if meta.get('link') == QuestionLink.DECOMPOSES else 'Continues'} "
                     f"[[{meta['parent']}]].")
    if kind != ResearchNodeKind.QUESTION and meta.get("question"):
        parts.append(f"{'Proposed for' if kind == ResearchNodeKind.HYPOTHESIS else 'Bears on'} "
                     f"[[{meta['question']}]].")
    for key, label in FOOTER_LABELS.items():
        if meta.get(key):
            parts.append(f"{label} " + ", ".join(f"[[{v}]]" for v in meta[key]) + ".")
    return " ".join(parts)
