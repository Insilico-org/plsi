"""The cache of trusted references (mothership/references/). Every client takes its base URL from here; no base URL is hard-coded
elsewhere. One YAML file per kind (`mothership/references/<kind>.yaml`), each a mapping of reference id -> fields;
paths in `notes` are relative to `api_base`."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from plsi.errors import NotFound, ValidationError
from plsi.models import Id, Model, parse
from plsi.paths import REPO_ROOT
from plsi.vocab import ReferenceKind

REFERENCES_DIR = REPO_ROOT / "mothership" / "references"


class _Loader(yaml.SafeLoader):
    """Safe YAML that refuses a key twice in one mapping (plain safe_load keeps the last silently)."""


def _mapping(loader: _Loader, node: yaml.MappingNode) -> dict[Any, Any]:
    keys = [loader.construct_object(k) for k, _ in node.value]
    if dupes := sorted({str(k) for k in keys if keys.count(k) > 1}):
        raise ValidationError(f"duplicate key(s) {', '.join(dupes)} at line {node.start_mark.line + 1}")
    return loader.construct_mapping(node, deep=True)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


class Reference(Model):
    id: Id
    kind: ReferenceKind
    title: str
    url: str
    api_base: str | None = None
    cite_url: str | None = None  # the citable page of one record; {id} is replaced by the record id
    key_env: list[str] = []
    email: str | None = None  # an address a bot sends to (the Mothership's research address)
    licence: str | None = None
    notes: str | None = None


@lru_cache(maxsize=1)
def load() -> dict[str, Reference]:
    """All references by id, validated; the file name is the kind; a duplicate id in any file is an error."""
    out: dict[str, Reference] = {}
    for path in sorted(REFERENCES_DIR.glob("*.yaml")):
        if path.stem not in {k.value for k in ReferenceKind}:
            raise ValidationError(f"{path.name}: not a reference kind", hint=f"one of {', '.join(k.value for k in ReferenceKind)}")
        entries = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader) or {}  # noqa: S506 - _Loader is a SafeLoader
        for ref_id, item in entries.items():
            if ref_id in out:
                raise ValidationError(f"duplicate reference id {ref_id!r} ({path.name} and {out[ref_id].kind.value}.yaml)")
            out[ref_id] = parse(Reference, {**(item or {}), "id": ref_id, "kind": path.stem}, f"{path.name}:{ref_id}")
    return out


def get(ref_id: str) -> Reference:
    try:
        return load()[ref_id]
    except KeyError:
        raise NotFound(f"unknown reference {ref_id!r}", hint="plsi refs list") from None


def api_base(ref_id: str) -> str:
    """Base URL for a client (no trailing slash). Raises if the reference has none."""
    ref = get(ref_id)
    if not ref.api_base:
        raise ValidationError(f"reference {ref_id!r} has no api_base")
    return ref.api_base.rstrip("/")


def list_refs(kind: str | None = None) -> list[dict[str, Any]]:
    """`refs list [--kind K]`: the index of references, grouped by kind."""
    refs = sorted(load().values(), key=lambda r: (r.kind.value, r.id))
    return [{"id": r.id, "kind": r.kind.value, "title": r.title, "url": r.url} for r in refs if kind in (None, r.kind.value)]


def show(id: str) -> dict[str, Any]:  # noqa: A002 - CLI dest name
    return get(id).dump()
