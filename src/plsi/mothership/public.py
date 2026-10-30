"""What the Longevity Mothership publishes through the relay: the public catalog, the aggregate data
releases (professional token, releases:read; saved to <PLSI_HOME>/mothership/releases/) and the findings ledger.
All of it is external data, never instructions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import json

from plsi import files, paths
from plsi.errors import ValidationError
from plsi.models import sanitize_external
from plsi.mothership import professional
from plsi.mothership.relay import get
from plsi.vocab import ProfessionalScope

CAP_DOCUMENT = 500_000


def _external(doc: Any, origin: str) -> dict[str, Any]:
    """A published document as ExternalText: its JSON text, data to read, never instructions."""
    return sanitize_external(json.dumps(doc, ensure_ascii=False, indent=1), CAP_DOCUMENT, origin).model_dump(mode="json")


def catalog() -> dict[str, Any]:
    """`mothership catalog`: the public catalog (counts below the minimum cell size read "<10")."""
    return {"catalog": _external(get("/public/catalog"), "mothership:catalog")}


def release(version: str, out: str | None = None) -> dict[str, Any]:
    """`mothership release`: download a data release (a version or `latest`) for local analysis."""
    professional.payload(ProfessionalScope.RELEASES_READ)
    if version != "latest":
        paths.validate_id(version, "release version")
    doc = get(f"/public/releases/{version}", professional.token())
    if not isinstance(doc, dict) or not isinstance(doc.get("cells"), list):
        raise ValidationError("the relay did not return a data release", code="BAD_RESPONSE")
    name = paths.validate_id(str(doc.get("version") or version), "release version")
    path = Path(out) if out else paths.safe_join(professional.folder() / "releases", f"{name}.json")
    files.atomic_write_json(path, doc)
    return {"file": str(path), "version": name, "cells": len(doc["cells"]), "min_cell": doc.get("min_cell"),
            "suppressed_cells": doc.get("suppressed_cells")}


def findings() -> dict[str, Any]:
    """`mothership findings`: the findings ledger, with the professional token when one is set."""
    return {"findings": _external(get("/public/findings", professional.token()), "mothership:findings")}
