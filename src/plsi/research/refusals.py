"""The seven refusals a save is checked against. None of them is about research judgment: they refuse an
unsourced finding, an unfalsifiable hypothesis, an unearned absence, an uncited answer, a finding from an empty or
unreported search, a dangling link, and a computed field written by the bot.

The budget is not a refusal: a move's cost arrives after the work, so `next` stops a day before a move starts and
`save` only requires the reading.
"""

from __future__ import annotations

from typing import Any

from plsi.errors import GateFailed, violation
from plsi.research.schema import links_of, meta_of
from plsi.research.store import Graph
from plsi.research.verdict import MIN_ABSENCE_ROUNDS
from plsi.vocab.research import ResearchDesign, ResearchGap, ResearchMove, ResearchNodeKind, ResearchVerdict

COMPUTED_FIELDS = ("verdict", "route", "independent_lines", "rank", "confidence")


def check(graph: Graph, move: str, nodes: list[dict[str, Any]], updates: list[dict[str, Any]],
          names: dict[int, str]) -> None:
    """Raise every violation at once. `names` maps the index of a payload node to the name it will take."""
    bad: list[dict[str, str]] = []
    known = set(graph.nodes) | set(names.values())
    search = _search_of(move, nodes, updates, graph)

    for index, node in enumerate(nodes):
        where = f"nodes[{index}] {node.get('title') or ''}".strip()
        meta = meta_of(node)
        bad += _honesty(where, node.get("kind"), meta, search)
        bad += _integrity(where, meta, known)
    for index, update in enumerate(updates):
        where = f"update[{index}] {update.get('name') or ''}".strip()
        if update.get("name") not in graph.nodes:
            bad.append(violation(where, "refusal-6", f"no node named {update.get('name')!r} in this topic",
                                 "update only a node that exists; create new ones in `nodes`"))
            continue
        stored = graph.nodes[update["name"]]
        bad += _honesty(where, stored.get("kind"), meta_of({**stored, **update}), search)
        bad += _integrity(where, update, known)
    # a gather that reports no search at all is refused like one that reports an empty search;
    # the user's own record comes from no search and is exempt
    if move == ResearchMove.GATHER and search is None:
        searched = [n for n in nodes if n.get("kind") == ResearchNodeKind.FINDING
                    and n.get("design") != ResearchDesign.PERSONAL_RECORD]
        if searched:
            bad.append(violation(f"nodes[{nodes.index(searched[0])}] {searched[0].get('title') or ''}".strip(),
                                 "refusal-5", "findings saved without saying what search produced them",
                                 "record last_search {rounds, hits, new} on the question in the same save; "
                                 "without it a search that returned nothing cannot be told from one nobody ran"))
    if bad:
        raise GateFailed(bad, "the save was refused")


def _search_of(move: str, nodes: list[dict[str, Any]], updates: list[dict[str, Any]],
               graph: Graph) -> dict[str, Any] | None:
    """The search this save reports, if any: `last_search` on a question, new or updated."""
    if move != ResearchMove.GATHER:
        return None
    for item in [*updates, *nodes]:
        if item.get("last_search"):
            return dict(item["last_search"])
    for item in updates:
        stored = graph.nodes.get(str(item.get("name")), {}).get("last_search")
        if stored:
            return dict(stored)
    return None


def _honesty(where: str, kind: str | None, meta: dict[str, Any], search: dict[str, Any] | None) -> list[dict[str, str]]:
    out = []
    if kind == ResearchNodeKind.FINDING:
        sources = meta.get("sources") or []
        if not sources:
            out.append(violation(where, "refusal-1", "a finding with no source",
                                 "every finding carries at least one {id, quote, text}"))
        for source in sources:
            if not isinstance(source, dict) or not str(source.get("id") or "").strip() \
                    or not str(source.get("quote") or "").strip():
                out.append(violation(where, "refusal-1", "a source with no id or no verbatim quote",
                                     "quote the results sentence as written; never retype a number"))
        if search and not int(search.get("hits") or 0):
            out.append(violation(where, "refusal-5", "a finding saved from a search that returned nothing",
                                 "the only permitted output of an empty search is a recorded absence"))
    if kind == ResearchNodeKind.HYPOTHESIS and not str(meta.get("if_false") or "").strip():
        out.append(violation(where, "refusal-2", "a hypothesis with no if_false",
                             "say what we would see if it were wrong; without that it is a story"))
    if kind == ResearchNodeKind.QUESTION:
        rounds = int((meta.get("last_search") or {}).get("rounds") or 0)
        if ResearchGap.canonical(meta.get("gap")) == ResearchGap.UNSTUDIED and rounds < MIN_ABSENCE_ROUNDS:
            out.append(violation(where, "refusal-3", "a claim of absence without a recorded search",
                                 f"gap: unstudied needs last_search.rounds >= {MIN_ABSENCE_ROUNDS}, "
                                 "with different vocabularies"))
        if str(meta.get("answer") or "").strip() and not (meta.get("cites") or []):
            out.append(violation(where, "refusal-4", "an answer that cites no node",
                                 "every claim in an answer points at the findings and resolved questions it rests on"))
    return out


def _integrity(where: str, meta: dict[str, Any], known: set[str]) -> list[dict[str, str]]:
    """Checks what the payload sends, never the merged node: `quote_verified` on a stored node is code's."""
    out = []
    for source in meta.get("sources") or []:
        if isinstance(source, dict) and "quote_verified" in source:
            out.append(violation(where, "refusal-7", "quote_verified is computed, not written",
                                 "pass the retrieved text as the source's `text`; code checks the quote "
                                 "occurs in it and then drops it"))
    for stray in [f for f in COMPUTED_FIELDS if f in meta]:
        out.append(violation(where, "refusal-7", f"{stray} is computed, not written",
                             "code counts distinct origins and names the result"))
    if str(meta.get("status") or "") in tuple(ResearchVerdict):
        out.append(violation(where, "refusal-7", f"{meta['status']!r} is a verdict, not a status",
                             "a verdict is arithmetic; set open, answered, superseded or closed"))
    for target in links_of(meta):
        if target not in known:
            out.append(violation(where, "refusal-6", f"link to {target!r}, which is not a node in this topic",
                                 "link only to a node that exists or is created in the same save"))
    return out
