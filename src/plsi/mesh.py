"""MeSH descriptors from NLM (`plsi mesh find`), and the tags of a research note resolved from their ids: the label
and tree numbers come from NLM, never from the bot. Base URL from plsi.references.api_base("nlm_mesh")."""

from __future__ import annotations

from typing import Any

from plsi import net, references
from plsi.errors import NetworkError, UsageError, ValidationError
from plsi.mothership.note import MAX_TAGS, MESH

REF = "nlm_mesh"
MAX_FIND = 20


def _id(resource: str) -> str:
    return resource.rstrip("/").rsplit("/", 1)[-1]


def find(term: str, limit: int = 10) -> list[dict[str, str]]:
    """`mesh find`: descriptors whose name contains `term`, exact matches first, as {mesh, label}."""
    if not term.strip():
        raise UsageError("name a term", hint="plsi mesh find --term 'cellular senescence'")
    base, n = references.api_base(REF), max(1, min(limit, MAX_FIND))
    seen: dict[str, str] = {}
    for match in ("exact", "contains"):
        for hit in net.get_json(f"{base}/lookup/descriptor", {"label": term.strip(), "match": match, "limit": n}) or []:
            seen.setdefault(_id(hit["resource"]), hit["label"])
    return [{"mesh": k, "label": v} for k, v in list(seen.items())[:n]]


def descriptor(mesh: str) -> dict[str, Any]:
    """One active descriptor as a note tag {mesh, label, tree}; BAD_MESH for an id NLM does not know."""
    if not isinstance(mesh, str) or not MESH.fullmatch(mesh):
        raise ValidationError(f"{mesh!r} is not a MeSH descriptor id (D followed by 6 or 9 digits)", code="BAD_MESH",
                              hint="plsi mesh find --term '<term>'")
    try:
        doc = net.get_json(f"{references.api_base(REF)}/{mesh}.json", missing=(404,)) or {}
    except NetworkError as exc:
        raise NetworkError(f"NLM MeSH did not answer for {mesh}: {exc.message}", status=exc.status, code=exc.code) from None
    label, trees = (doc.get("label") or {}).get("@value"), doc.get("treeNumber") or []
    trees = [trees] if isinstance(trees, str) else trees
    if not label or doc.get("active") is False or not trees:
        raise ValidationError(f"NLM knows no active MeSH descriptor {mesh}", code="BAD_MESH",
                              hint="plsi mesh find --term '<term>'")
    return {"mesh": mesh, "label": label, "tree": sorted(_id(t) for t in trees)}


def tags(given: Any, at: str) -> list[dict[str, Any]]:
    """An item's `tags` as written (ids, or {mesh, ...}), resolved: 1-MAX_TAGS distinct descriptors."""
    ids = [e.get("mesh") if isinstance(e, dict) else e for e in given] if isinstance(given, list) else []
    if not ids or len(ids) > MAX_TAGS or len(set(map(str, ids))) != len(ids):
        raise ValidationError(f"{at}: 1-{MAX_TAGS} distinct MeSH descriptor ids", code="BAD_MESH",
                              hint="plsi mesh find --term '<term>'")
    return [descriptor(i) for i in ids]
