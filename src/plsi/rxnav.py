"""RxNav (the NLM RxNorm API): approximate-term candidates and a concept's ingredients. HTTP only through plsi.net."""

from __future__ import annotations

from typing import Any

from plsi import net, references

MAX_ENTRIES = 10  # approximateTerm candidates per name
MIN_SCORE = 2.0  # false hits score < 1 (e.g. an abbreviation matching a brand), true hits ~8-19


def candidates(term: str, min_score: float | None = MIN_SCORE) -> list[str]:
    """The rxcuis approximateTerm finds for `term`, best first and deduplicated; min_score None keeps every one."""
    reply = net.get_json(f"{references.api_base('rxnav')}/approximateTerm.json",
                         {"term": term, "maxEntries": MAX_ENTRIES, "option": 1})
    out: list[str] = []
    for cand in (reply.get("approximateGroup") or {}).get("candidate") or []:
        rxcui = cand.get("rxcui")
        if rxcui and rxcui not in out and (min_score is None or float(cand.get("score") or 0) >= min_score):
            out.append(rxcui)
    return out


def ingredients(rxcui: str) -> dict[str, list[dict[str, Any]]]:
    """Term type (IN, PIN) -> the conceptProperties ({rxcui, name, ...}) of the concept's related ingredients."""
    related = net.get_json(f"{references.api_base('rxnav')}/rxcui/{rxcui}/related.json", {"tty": "IN PIN"})
    out: dict[str, list[dict[str, Any]]] = {}
    for group in (related.get("relatedGroup") or {}).get("conceptGroup") or []:
        out.setdefault(group.get("tty"), []).extend(group.get("conceptProperties") or [])
    return out
