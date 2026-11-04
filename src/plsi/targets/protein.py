"""UniProt: the protein itself - length, annotated domains and sites with their positions, mutagenesis
results and activity regulation. Positions come from the record or are absent; nothing is interpreted.
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from plsi import net, references
from plsi.models import external_str

# UniProt feature types read, mapped onto the dossier's feature groups. `Region` counts as a domain because
# some proteins record their architecture only as regions.
UNIPROT_FEATURE_KINDS = {"Domain": "domain", "Region": "domain", "Binding site": "binding",
                         "Active site": "active-site", "Transmembrane": "transmembrane",
                         "Signal": "signal-peptide", "Mutagenesis": "mutagenesis"}

MAX_FEATURES = 12
FIELDS = ("accession,id,protein_name,length,ft_domain,ft_region,ft_binding,ft_act_site,ft_transmem,"
          "ft_signal,cc_subcellular_location,xref_pdb,ft_mutagen,cc_activity_regulation,"
          "cc_catalytic_activity")
MAX_MUTAGENESIS = 8


def _position(location: dict[str, Any]) -> tuple[int | None, int | None]:
    start = (location or {}).get("start", {}).get("value")
    end = (location or {}).get("end", {}).get("value")
    return start, end


def _features(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for feature in record.get("features") or []:
        kind = UNIPROT_FEATURE_KINDS.get(str(feature.get("type") or ""))
        if not kind:
            continue
        start, end = _position(feature.get("location") or {})
        rows = out.setdefault(kind, [])
        if len(rows) < MAX_FEATURES:
            rows.append({"start": start, "end": end,
                         "description": external_str(feature.get("description")) or None,
                         "span": f"{start}-{end}" if start and end and start != end else str(start or "")})
    return out


MAX_COMMENTS = 3


def _comments(record: dict[str, Any], kind: str) -> list[str]:
    """One kind of UniProt free-text comment (e.g. ACTIVITY REGULATION, CATALYTIC ACTIVITY), relayed verbatim."""
    out = []
    for comment in record.get("comments") or []:
        if str(comment.get("commentType") or "").upper() != kind:
            continue
        for text_block in comment.get("texts") or []:
            if value := external_str(text_block.get("value")):
                out.append(value)
        if reaction := (comment.get("reaction") or {}).get("name"):
            out.append(external_str(reaction))
    return out[:MAX_COMMENTS]


def features(accession: str) -> dict[str, Any]:
    """`{known, length, features{...}, pdb_entries}` for one UniProt accession. An unknown accession answers
    HTTP 400 or 404 and reads as not held."""
    record = net.get_json(f"{references.api_base('uniprot')}/{urllib.parse.quote(accession.strip(), safe='')}",
                          {"fields": FIELDS, "format": "json"}, missing=(400, 404))
    if not isinstance(record, dict) or not record.get("primaryAccession"):
        return {"known": False, "accession": external_str(accession),
                "note": f"UniProt holds no reviewed entry for {accession}"}
    found = _features(record)
    names = (record.get("proteinDescription") or {}).get("recommendedName") or {}
    return {
        "known": True,
        "accession": external_str(record.get("primaryAccession")),
        "entry": external_str(record.get("uniProtkbId")) or None,
        "protein": external_str((names.get("fullName") or {}).get("value")) or None,
        "length_aa": (record.get("sequence") or {}).get("length"),
        "features": found,
        "counts": {kind: len(rows) for kind, rows in found.items()},
        "mutagenesis": [{"residue": row["span"], "effect": row["description"]}
                        for row in (found.get("mutagenesis") or [])[:MAX_MUTAGENESIS]
                        if row.get("description")],
        "regulation": _comments(record, "ACTIVITY REGULATION"),
        "catalysis": _comments(record, "CATALYTIC ACTIVITY"),
        # UniProt's PDB cross-reference count, compared with the PDB search in `gaps`.
        "pdb_entries": sum(1 for x in record.get("uniProtKBCrossReferences") or []
                           if str(x.get("database") or "") == "PDB"),
        "note": "positions are UniProt's annotation on the canonical sequence; a residue number not from here "
                "or from a deposited structure is an estimate",
    }
