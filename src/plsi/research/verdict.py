"""The arithmetic: independent lines, the verdict, and how strong an answer is allowed to be.

Independence is distinct origins among human, non-personal findings; an aggregate is its own origin and weighs
the minimum that means replicated; unattributed evidence supports nothing and still counts against. Verdicts
are computed from those counts on every read and never stored.
"""

from __future__ import annotations

from typing import Any

from plsi.research.store import Graph
from plsi.vocab import fold
from plsi.vocab.research import (LIVE, OFF_TARGET_SPECIES, RESOLVED, ResearchDepth, ResearchDesign, ResearchNodeKind,
                                 ResearchVerdict)

AGGREGATE_WEIGHT = 2  # replicated by construction; never the pooled count, which is a number nobody can check
MIN_ABSENCE_ROUNDS = 2  # "none found" is earned by two rounds with different vocabularies, not by one
# The weakest verdict an answer may have for the topic to finish as `answered`; `None` is no bar. Below the
# floor the topic ends `exhausted` once the frontier empties. `fast` has no bar because `refuted` is a real
# result and ranks lowest.
DEPTH_FLOOR: dict[ResearchDepth, ResearchVerdict | None] = {
    ResearchDepth.FAST: None,
    ResearchDepth.STANDARD: ResearchVerdict.THIN,
    ResearchDepth.DEEP: ResearchVerdict.SUPPORTED,
    ResearchDepth.EXHAUSTIVE: ResearchVerdict.SUPPORTED,
}


def floor_words(depth: ResearchDepth) -> str:
    """What an answer must reach for a topic at this depth to finish, as `answer_must_reach` says it."""
    return str(DEPTH_FLOOR[depth] or "any answer at all")


def live_hypotheses(graph: Graph, question: str) -> list[dict[str, Any]]:
    return [h for h in graph.hypotheses_of(question) if h.get("status") in LIVE]


def canonical_origin(origin: Any) -> str:
    """The key an origin is counted under: lower-case letters and digits only, so "NCT 0431" and "nct0431" are
    one line. A source named two different ways still makes two lines, which is why `next` hands over the
    origins already in use."""
    return fold(origin) or "unrecorded"


def lines(findings: list[dict[str, Any]], *, unattributed_counts: bool = False) -> list[dict[str, Any]]:
    """Independent lines of evidence: distinct origins, each with its weight.

    The key is the origin alone, never the free-text `design`, so rewording cannot inflate the count. Findings
    with no origin share one line that weighs nothing unless `unattributed_counts` is set (it is, for evidence
    against a claim). The user's own record keys to itself."""
    by_origin: dict[str, dict[str, Any]] = {}
    for f in findings:
        key = canonical_origin(f.get("origin") or implicit_origin(f))
        shown = str(f.get("origin") or implicit_origin(f) or "unrecorded")
        counts = key != "unrecorded" or unattributed_counts
        line = by_origin.setdefault(key, {"origin": shown, "spellings": set(), "designs": set(), "weight": 1,
                                          "findings": [], "counts": counts})
        line["findings"].append(f["name"])
        line["spellings"].add(shown)
        line["designs"].add(str(f.get("design") or "unrecorded"))
        pooled = AGGREGATE_WEIGHT if f.get("design") == ResearchDesign.AGGREGATE else 1
        line["weight"] = max(line["weight"], pooled) if counts else 0
    return sorted(({**line, "designs": sorted(line["designs"]), "spellings": sorted(line["spellings"]),
                    "design": " / ".join(sorted(line["designs"]))}
                   for line in by_origin.values()), key=lambda line: line["origin"])


def weight(lines_: list[dict[str, Any]]) -> int:
    return sum(line["weight"] for line in lines_)


def counts_for_support(finding: dict[str, Any]) -> bool:
    """Whether a finding may support a claim about people: not off-target and not the user's own record (n = 1,
    which may only refute)."""
    return (str(finding.get("species") or "") not in OFF_TARGET_SPECIES
            and finding.get("design") != ResearchDesign.PERSONAL_RECORD)


def implicit_origin(f: dict[str, Any]) -> str:
    """The origin a finding has without one being written: the user's record is this person, and an aggregate
    is its own publication (its first source id)."""
    if f.get("design") == ResearchDesign.PERSONAL_RECORD:
        return ResearchDesign.PERSONAL_RECORD.value
    if f.get("design") == ResearchDesign.AGGREGATE:
        first = (f.get("sources") or [{}])[0]
        return str(first.get("id") or f.get("name") or "")
    return ""


def evidence(graph: Graph, hypothesis: str) -> dict[str, Any]:
    """Supporting and contradicting lines for one hypothesis, and the findings set aside.

    A boundary dissolves a contradiction, never support, so its findings leave only the `against` side."""
    node = graph.nodes.get(hypothesis, {})
    dissolved = {name for b in (node.get("boundaries") or []) for name in (b.get("between") or [])}
    pool = graph.of_kind(ResearchNodeKind.FINDING)
    support = [f for f in pool if hypothesis in (f.get("supports") or []) and counts_for_support(f)]
    against = [f for f in pool if hypothesis in (f.get("contradicts") or []) and f["name"] not in dissolved
               and str(f.get("species") or "") not in OFF_TARGET_SPECIES]
    set_aside = {f["name"] for f in pool
                 if hypothesis in (f.get("supports") or []) + (f.get("contradicts") or [])
                 and (f["name"] in dissolved or str(f.get("species") or "") in OFF_TARGET_SPECIES
                      or (f.get("design") == ResearchDesign.PERSONAL_RECORD
                          and hypothesis in (f.get("supports") or [])))}
    return {"for": lines(support), "against": lines(against, unattributed_counts=True),
            "set_aside": sorted(set_aside)}


def independent(lines_: list[dict[str, Any]]) -> int:
    """How many distinct sources stand behind this. An aggregate weighs 2 but is still one source, and
    `supported` is a claim about independence, so it is decided on this count rather than on weight."""
    return sum(1 for line in lines_ if line["weight"] > 0)


def verdict(graph: Graph, hypothesis: str) -> str:
    """Five words, computed. `supported` is the ceiling; there is no stronger one."""
    ev = evidence(graph, hypothesis)
    for_, against = weight(ev["for"]), weight(ev["against"])
    if against and not for_:
        return str(ResearchVerdict.REFUTED)
    if against and for_:
        return str(ResearchVerdict.CONTESTED)
    if independent(ev["for"]) >= 2:
        return str(ResearchVerdict.SUPPORTED)
    return str(ResearchVerdict.THIN) if for_ else str(ResearchVerdict.UNTESTED)


def verdicts(graph: Graph) -> dict[str, str]:
    return {h["name"]: verdict(graph, h["name"]) for h in graph.of_kind(ResearchNodeKind.HYPOTHESIS)}


def weakest(values: list[str]) -> str:
    """An answer is only as strong as its weakest cited step."""
    return str(min(map(ResearchVerdict, values), key=lambda v: v.rank, default=ResearchVerdict.UNTESTED))


def meets(verdict_: str, floor: Any) -> bool:
    """Whether a verdict is at least as strong as `floor`; a floor of None is no bar."""
    return floor is None or ResearchVerdict(verdict_).rank >= ResearchVerdict(floor).rank


def question_verdict(graph: Graph, question: str, _seen: frozenset[str] = frozenset()) -> str:
    """The weakest of what a question rests on: its citations once answered, else its live hypotheses.
    Findings alone never make a question `supported`."""
    node = graph.nodes.get(question, {})
    cited = [c for c in (node.get("cites") or []) if c in graph.nodes and c not in _seen]
    if str(node.get("answer") or "").strip() and cited:
        return _answer_verdict(graph, question, cited, _seen | {question})["verdict"]
    return weakest([verdict(graph, h["name"]) for h in live_hypotheses(graph, question)])


def _answer_verdict(graph: Graph, question: str, cited: list[str], seen: frozenset[str]) -> dict[str, Any]:
    """How strong an answer may be, and what caps it.

    Cited claims (live hypotheses and child questions) are steps and the answer takes the weakest of them.
    Cited findings are the evidence under those steps and are not graded as steps; an answer that cites only
    findings stops at `thin`, because no link code reads can show two findings disagreeing. Recorded absences
    and hypotheses the answer ruled out are reported beside the verdict, outside the cap."""
    absences = [c for c in cited if is_recorded_absence(graph, c)]
    settled = [c for c in cited if c not in absences
               and graph.nodes[c]["kind"] == ResearchNodeKind.HYPOTHESIS
               and graph.nodes[c].get("status") in RESOLVED]
    claims = [c for c in cited if c not in absences and c not in settled
              and graph.nodes[c]["kind"] in (ResearchNodeKind.HYPOTHESIS, ResearchNodeKind.QUESTION)]
    evidence_ = [graph.nodes[c] for c in cited if graph.nodes[c]["kind"] == ResearchNodeKind.FINDING]
    graded = {c: (verdict(graph, c) if graph.nodes[c]["kind"] == ResearchNodeKind.HYPOTHESIS
                  else question_verdict(graph, c, seen)) for c in claims}
    if graded:
        verdict_ = weakest(list(graded.values()))
    else:
        ev = lines([f for f in evidence_ if counts_for_support(f)])
        verdict_ = str(ResearchVerdict.THIN if weight(ev) else ResearchVerdict.UNTESTED)
    return {"verdict": verdict_, "graded": graded, "absences": absences,
            "rests_on": sorted(f["name"] for f in evidence_),
            "ruled_out": sorted(settled),
            "limited_by": sorted(c for c, v in graded.items() if v == verdict_)}


def is_recorded_absence(graph: Graph, name: str) -> bool:
    """A question that was searched and holds nothing: a boundary of what is known, distinct from `untested`."""
    node = graph.nodes.get(name, {})
    return (node.get("kind") == ResearchNodeKind.QUESTION
            and int((node.get("last_search") or {}).get("rounds") or 0) >= MIN_ABSENCE_ROUNDS
            and not graph.findings_of(name) and not graph.hypotheses_of(name))


def answered(graph: Graph, question: str) -> dict[str, Any] | None:
    """The answer, its verdict, and the steps that cap it; None when the question has no answer."""
    node = graph.nodes.get(question, {})
    if not str(node.get("answer") or "").strip():
        return None
    cited = [c for c in (node.get("cites") or []) if c in graph.nodes]
    read = _answer_verdict(graph, question, cited, frozenset({question}))
    return {"question": question, "answer": node["answer"], "verdict": read["verdict"],
            "cites": cited, "cited_verdicts": read["graded"], "ruled_out": read["ruled_out"],
            "rests_on": read["rests_on"], "limited_by": read["limited_by"],
            "nothing_found_for": read["absences"]}
