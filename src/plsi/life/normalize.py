"""Code and unit normalization (`normalize observations`): LOINC via NLM Clinical Tables, RxNorm via plsi.rxnav,
units via a local UCUM alias table. Unit spelling lives in plsi.life.units, LOINC resolution in plsi.life.loinc; this
module drives `plsi normalize observations` and re-exports both for `from plsi.life.normalize import ...`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from plsi import rxnav
from plsi.files import atomic_write_json, load_json
from plsi.life.importers import observation_items
from plsi.life.loinc import LOINC_MAX_LIST, loinc_candidates, loinc_search_url, same_analyte, shipped_coordinates, specimen_class
from plsi.life.models import ObservationInput
from plsi.life.units import UNIT_BASES, UNIT_PREFIXES, known_unit, normalize_unit
from plsi.models import Code, parse
from plsi.vocab import CodeSystem, ObservationKind

__all__ = [
    "normalize_unit", "known_unit", "UNIT_BASES", "UNIT_PREFIXES",
    "shipped_coordinates", "loinc_search_url", "loinc_candidates", "specimen_class", "same_analyte", "LOINC_MAX_LIST",
    "normalize_observations",
]

MAX_AMBIGUOUS_CANDIDATES = 5


def _rxnorm_groups(text: str) -> list[list[Code]]:
    """Ingredients per approximateTerm candidate (deduped by rxcui, best first)."""
    return [[Code(system=CodeSystem.RXNORM, code=p["rxcui"], display=p.get("name")) for p in rxnav.ingredients(rxcui).get("IN", [])]
            for rxcui in rxnav.candidates(text)]


def _flatten(groups: list[list[Code]]) -> list[Code]:
    out: dict[str, Code] = {}
    for c in (c for g in groups for c in g):
        out.setdefault(c.code, c)
    return list(out.values())


def normalize_observations(in_path: str, out_path: str) -> dict[str, Any]:
    """`plsi normalize observations --in F --out F` (network).

    Uncoded measurements get LOINC (auto-pick only when the top candidate is map-accepted, compatible AND names the
    printed analyte, `same_analyte`);
    uncoded medications get the RxNorm ingredient when the best match resolves to exactly one. Others pass through.
    Returns {out, counts: {total, coded, ambiguous, unchanged}, ambiguous: [{index, original_text, candidates}]}.
    """
    observations = [parse(ObservationInput, item, f"observation {i}") for i, item in enumerate(observation_items(load_json(in_path)))]
    out, ambiguous, coded = [], [], 0
    for i, obs in enumerate(observations):
        code, candidates = None, None
        if obs.code is None and obs.kind == ObservationKind.MEASUREMENT:
            ranked = loinc_candidates(obs.original_text, obs.unit, obs.specimen)
            if ranked and ranked[0]["map_accepted"] and ranked[0]["compatible"] and ranked[0]["same_analyte"]:
                code = Code(system=CodeSystem.LOINC, code=ranked[0]["code"], display=ranked[0]["display"])
            else:
                candidates = ranked[:MAX_AMBIGUOUS_CANDIDATES]
        elif obs.code is None and obs.kind == ObservationKind.MEDICATION:
            groups = _rxnorm_groups(obs.original_text)
            if groups and len(groups[0]) == 1:
                code = groups[0][0]
            else:
                candidates = [c.dump() for c in _flatten(groups)[:MAX_AMBIGUOUS_CANDIDATES]]
        if code is not None:
            obs, coded = obs.model_copy(update={"code": code}), coded + 1
        elif candidates is not None:
            ambiguous.append({"index": i, "original_text": obs.original_text, "candidates": candidates})
        out.append(parse(ObservationInput, obs.dump()).dump())
    target = Path(out_path).resolve()
    atomic_write_json(target, out)
    return {
        "out": str(target),
        "counts": {"total": len(out), "coded": coded, "ambiguous": len(ambiguous), "unchanged": len(out) - coded - len(ambiguous)},
        "ambiguous": ambiguous,
    }
