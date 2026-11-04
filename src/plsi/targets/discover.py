"""`plsi targets discover`: the candidate targets a disease's evidence points at, or the curated aging genes
under one hallmark. It ranks nothing itself and writes nothing."""

from __future__ import annotations

from typing import Any

from plsi.errors import ValidationError
from plsi.targets import aging, hallmarks, opentargets, rank

MAX_ROWS = 2_000  # ranked rows fetched before filtering; a clinical-stage target can rank in the thousands
DEFAULT_ROWS = 500
MAX_CANDIDATES = 100
DEFAULT_CANDIDATES = 25


def discover(disease: str | None = None, hallmark: str | None = None, limit: int = DEFAULT_CANDIDATES,
             band: str | None = None, depth: int = DEFAULT_ROWS, find: str | None = None,
             aging_only: bool = False) -> dict[str, Any]:
    """`plsi targets discover`: candidates from a disease (Open Targets' own ranking, banded by the evidence
    types behind each association) or from a hallmark of aging (Open Genes' curated genes, no band). `--find`
    reports one gene's rank; `--aging` keeps only Open Genes-curated candidates. `--band` and `--hallmark` are
    closed choices, checked by the command line."""
    if bool(disease) == bool(hallmark):
        raise ValidationError("name either --disease or --hallmark, and not both",
                              hint="a band comes from a disease and a hallmark has none; they are different "
                                   "questions and the answers are shaped differently")
    if not 1 <= limit <= MAX_CANDIDATES:
        raise ValidationError(f"limit must be between 1 and {MAX_CANDIDATES}")
    if hallmark:
        return hallmarks.candidates(hallmark, limit)
    if not 1 <= depth <= MAX_ROWS:
        raise ValidationError(f"depth must be between 1 and {MAX_ROWS}")
    found = opentargets.find_disease(disease)
    assoc = opentargets.associated_targets(found["id"], max(depth, limit))
    rows = rank.candidates(assoc["rows"])

    # One cached request for the whole Open Genes corpus.
    curated = aging.curated_symbols() if aging_only else frozenset()
    for row in rows:
        row["aging_curated"] = row["symbol"].upper() in curated if aging_only else None

    wanted = (find or "").strip().upper()
    located = [r for r in rows if r["symbol"].upper() == wanted] if wanted else []
    matching = [r for r in rows if band in (None, r["band"])
                and (not aging_only or r["aging_curated"])]
    shown = located or matching[:limit]
    # Counted over everything that matched, not only the rows shown.
    drug_side = [r["symbol"] for r in matching if r.get("drug_side_only")]
    shown_side = [r["symbol"] for r in shown if r.get("drug_side_only")]
    total = assoc["total"] or 0
    return {
        "asked": disease,
        # The ontology's label plus its exact synonyms, for registry searches.
        "disease": {**assoc["disease"], "also_known_as": found.get("also_known_as") or []},
        "also_matched": found["also_matched"],
        "targets_with_evidence": total,
        "searched": len(rows), "matching": len(matching), "shown": len(shown),
        "aging_filter": {
            "on": aging_only,
            "curated_in_search": sum(1 for r in rows if r.get("aging_curated")),
            "corpus": len(curated),
            "note": "candidates whose symbol is in the Open Genes curated corpus. Curation means somebody "
                    "has filed aging evidence for the gene; it does not mean the gene is involved in THIS "
                    "disease's aging biology, and the dossier's aging block is where that is read",
        } if aging_only else None,
        "aging_empty": (f"none of the {len(rows)} ranked rows is a curated aging gene. That is a statement "
                        "about Open Genes' coverage of this disease's targets, not about whether aging "
                        "bears on it" if aging_only and not matching else None),
        "bands": rank.by_band(rows), "candidates": shown,
        "found": {"symbol": wanted, "rank": located[0]["rank"] if located else None,
                  "searched": len(rows)} if wanted else None,
        "source": {"ref": "open_targets", "external_text": True},
        "note": "Open Targets ranks these, not PLSI. A band says what has been tried on a target, not how good "
                "it is: `novel` means the association rests on expression, pathways or text alone.",
        "rank_warning":
            f"ranked rows {len(rows)} of {total} - a clinical-stage target can sit far down this list. Raise "
            f"--depth, or name the gene with --find <SYMBOL> to get its rank directly."
            if total > len(rows) else None,
        "drug_side_only": shown_side or None,
        "drug_side_warning":
            (f"{len(drug_side)} of the {len(matching)} matching candidates are banded `clinical` on the drug "
             f"annotation ALONE"
             + (f", including {', '.join(shown_side)} among those shown" if shown_side else "")
             + ". A drug against the target reached a trial in this disease; nothing else links the "
               "target to it."
             if drug_side else None),
        "empty": (f"no candidate in the {len(rows)} ranked rows is banded `{band}` - the `bands` block below "
                  f"lists what was found, which is not a result for your filter" if band and not matching
                  else None),
        "next": f"plsi targets dossier --gene <symbol> --disease \"{assoc['disease']['name']}\"",
    }
