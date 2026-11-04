"""Question discovery from open sources: what is asserted about a subject, how heavily, and where that thins out.

`research propose` reads this person's record; this reads PubTator's relation annotations to find what is open
about a subject. It chooses nothing: it returns relations with their publication counts and the query that
produced them, and the bot and the user decide. It reads no research store, so either research bot can run it;
whether a candidate is already covered is `research propose`'s check.

PubTator covers PubMed and the PMC open-access subset only, so the bot's own web search is the other half of
discovery, and every reply says so in `caveats`.
"""

from __future__ import annotations

import re
from typing import Any

from plsi import net, references
from plsi.errors import NetworkError, ValidationError
from plsi.models import CAP_ABSTRACT, sanitize_external
from plsi.policy import evidence
from plsi.vocab.research import TopicSource

ORIGIN = "pubtator3"
CONCEPTS = ("CHEMICAL", "DISEASE", "GENE")      # the three a subject is most often one of
ENTITY_RE = re.compile(r"^@(CHEMICAL|DISEASE|GENE|VARIANT|SPECIES)_[A-Za-z0-9][\w,.'()/+-]*$")
MAX_CANDIDATES = 12
# The candidate band, in papers per relation and absolute whatever the subject. Below MIN_SUPPORT a relation is
# mostly extraction noise; from WELL_STUDIED up it is what the field has already settled.
MIN_SUPPORT = 3
THINLY_STUDIED = 25
WELL_STUDIED = 50
SUPPORT_FOR = 5    # candidates that get their own papers fetched; one request each, at 3/s


def _base() -> str:
    return references.api_base(ORIGIN)


def _text(value: Any) -> dict[str, Any]:
    return sanitize_external(str(value or ""), CAP_ABSTRACT, ORIGIN).model_dump(mode="json")


def _label(entity: str) -> str:
    """`@DISEASE_Diabetes_Mellitus_Type_2` as a person would read it."""
    return str(entity).split("_", 1)[-1].replace("_", " ") if "_" in str(entity) else str(entity)


def _kind(entity: str) -> str:
    return str(entity)[1:].split("_", 1)[0].lower() if str(entity).startswith("@") else ""


# ---------------------------------------------------------------- resolving a subject

def _relations(entity: str, relation: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"e1": entity}
    if relation:
        params["type"] = relation
    data = net.get_json(f"{_base()}/relations", params)
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _autocomplete(subject: str) -> str | None:
    """PubTator's own resolver; a network failure falls through to the constructed ids in `resolve`."""
    try:
        data = net.get_json(f"{_base()}/entity/autocomplete/", {"query": subject, "limit": 5})
    except NetworkError:
        return None
    for item in data if isinstance(data, list) else []:
        found = str((item or {}).get("_id") or (item or {}).get("id") or "")
        if ENTITY_RE.match(found):
            return found
    return None


def resolve(subject: str, entity: str | None = None) -> dict[str, Any]:
    """A subject as a PubTator entity id, and how it was arrived at.

    A wrong id answers with an empty list rather than an error, so an id counts as real only when it has
    relations. After autocomplete, `@TYPE_Subject` is tried for each usual type; that cannot find an entity
    PubTator knows under a different name."""
    if entity:
        if not ENTITY_RE.match(entity):
            raise ValidationError(f"{entity!r} is not a PubTator entity id",
                                  code="BAD_ENTITY", hint="@CHEMICAL_<Name>, @DISEASE_<Name>, @GENE_<SYMBOL>")
        return {"entity": entity, "resolved_by": "given", "relations": _relations(entity)}
    found = _autocomplete(subject)
    if found:
        rows = _relations(found)
        if rows:
            return {"entity": found, "resolved_by": "autocomplete", "relations": rows}
    stem = re.sub(r"\s+", "_", subject.strip()).replace("-", "_")
    for concept in CONCEPTS:
        guess = f"@{concept}_{stem[:1].upper()}{stem[1:]}"
        if not ENTITY_RE.match(guess):
            continue
        rows = _relations(guess)
        if rows:
            return {"entity": guess, "resolved_by": "constructed", "relations": rows}
    return {"entity": None, "resolved_by": None, "relations": []}


# ---------------------------------------------------------------- the candidates

def _pair(row: dict[str, Any], entity: str) -> dict[str, Any]:
    """One asserted relation, recording which end the subject is on, since several relation types are
    directional."""
    source, target = str(row.get("source") or ""), str(row.get("target") or "")
    other = target if source == entity else source
    return {"relation": str(row.get("type") or ""), "other": other,
            "other_label": _text(_label(other)), "other_kind": _kind(other),
            "subject_acts": source == entity,
            "publications": int(row.get("publications") or 0),
            "query": f"relations:{row.get('type')}|{source}|{target}"}


def _supporting(query: str, limit: int = 3) -> dict[str, Any]:
    """The first papers behind one relation: leads a topic opened on it would rest on. Nothing here has read
    them; the first Gather retrieves and quotes them like any other source."""
    try:
        data = net.get_json(f"{_base()}/search/", {"text": query})
    except NetworkError:  # a candidate without its papers is still a candidate
        return {"papers": [], "indexed": None}
    out = []
    for item in (data.get("results") or [])[:limit] if isinstance(data, dict) else []:
        pmid = str((item or {}).get("pmid") or "")
        if pmid.isdigit():
            out.append({"id": f"PMID:{pmid}", "title": _text(item.get("title")),
                        "journal": _text(item.get("journal")), "year": str(item.get("date") or "")[:4]})
    return {"papers": out, "indexed": int(data.get("count") or 0) if isinstance(data, dict) else None}


DIRECTED = {
    "treat": "does {a} do anything for {b}?",
    "prevent": "does {a} stop {b} happening?",
    "cause": "can {a} bring on {b}?",
    "inhibit": "does {a} shut down {b}, and does that matter?",
    "stimulate": "does {a} turn up {b}, and does that matter?",
    "convert": "does {a} turn into {b}, and does that matter?",
}
SYMMETRIC = {
    "interact": "what happens when {a} and {b} meet?",
    "drug_interact": "is it a problem to take {a} and {b} together?",
    "associate": "what is the connection between {a} and {b}?",
    "compare": "which does more, {a} or {b}?",
    "cotreat": "is {a} worth taking alongside {b}?",
    "positive_correlate": "do {a} and {b} rise together, and does one drive the other?",
    "negative_correlate": "does {b} fall when {a} rises, and does one drive the other?",
}


def _ask(subject: str, pair: dict[str, Any]) -> str:
    """The relation as a plain-language question, the way round it was asserted."""
    other = pair["other_label"]["text"]
    actor, acted_on = (subject, other) if pair.get("subject_acts") else (other, subject)
    if pair["relation"] in DIRECTED:
        return DIRECTED[pair["relation"]].format(a=actor, b=acted_on)
    return SYMMETRIC.get(pair["relation"], "what is the relationship between {a} and {b}?").format(
        a=subject, b=other)


def discover(about: str, entity: str | None = None, limit: int = 6,
             trials: bool = False) -> dict[str, Any]:
    """`research discover --about "<subject>"`: what is asserted about a subject and how heavily.

    `well_studied` is what not to open a topic on; `candidates` are relations standing on a handful of papers,
    either a thin edge of the field or an extraction artifact, which the first Gather tells apart."""
    if not str(about or "").strip():
        raise ValidationError("discover needs a subject", hint='--about "<a drug, gene or condition>"')
    if not 1 <= limit <= MAX_CANDIDATES:
        raise ValidationError(f"limit must be between 1 and {MAX_CANDIDATES}")
    subject = str(about).strip()
    found = resolve(subject, entity)
    caveats = [
        "every relation here is a model's reading of the literature, not curation, and `publications` is a "
        "count of papers it thinks say so. Retrieve and quote before any of it becomes a finding",
        "this covers PubMed and the PMC open-access subset. A preprint it has not indexed, a registry entry, "
        "a guideline and a question nobody has written a sentence about are all invisible to it - **your own "
        "web search is the other half of this, not the fallback for when it fails**",
    ]
    if not found["entity"]:
        return {"about": subject, "entity": None, "resolved": False,
                "why": f"nothing in PubTator resolves {subject!r}",
                "candidates": [], "well_studied": [], "caveats": caveats,
                "how_to_use": (
                    "Entity ids are name-based and case-sensitive and PubTator often uses a different name "
                    "than the one people say. Try the canonical name "
                    "(the INN, the MeSH term, the gene symbol), or pass it directly with "
                    "--entity '@CHEMICAL_<Name>'. If it still does not resolve, search the web yourself and "
                    "open the topic from what you find - an absence here is not an absence in the field."),
                }

    pairs = sorted((_pair(r, found["entity"]) for r in found["relations"]),
                   key=lambda p: -p["publications"])
    # never empty while relations exist, or a small subject would read as having nothing settled
    settled = [p for p in pairs if p["publications"] >= WELL_STUDIED] or pairs[:limit]
    thin = [p for p in pairs if MIN_SUPPORT <= p["publications"] <= THINLY_STUDIED]
    candidates = []
    for pair in thin[:limit]:
        ask = _ask(subject, pair)
        support = _supporting(pair["query"]) if len(candidates) < SUPPORT_FOR else {"papers": [], "indexed": None}
        candidates.append({
            "kind": str(TopicSource.OPEN_QUESTION), "about": f"{subject} and {pair['other_label']['text']}",
            "ask": ask, "relation": pair["relation"], "publications": pair["publications"],
            "rests_on": [p["id"] for p in support["papers"]],
            "papers": support["papers"], "indexed": support["indexed"], "query": pair["query"],
            "why": f"PubTator reads {pair['publications']} papers as saying {subject} {pair['relation']} "
                   f"{pair['other_label']['text']} - enough that somebody has looked, few enough that "
                   "nobody has settled it",
        })
    out: dict[str, Any] = {
        "about": subject, "entity": found["entity"], "resolved": True, "resolved_by": found["resolved_by"],
        "relations_found": len(pairs),
        "candidates": candidates,
        "well_studied": [{"ask": _ask(subject, p), "publications": p["publications"],
                          "relation": p["relation"], "about": p["other_label"]["text"]} for p in settled[:limit]],
        "caveats": caveats,
        "covered_check": (
            "this command reads no store and does not know what research already covers. "
            "`plsi research propose` says which candidates an existing topic or note covers, and holding "
            "that check in one place is what lets both research bots run this one"),
        "how_to_use": (
            "`well_studied` is what NOT to open a topic on - the field has answered it. `candidates` is where "
            "a question is open: offer two or three as a curious non-scientist would ask them, beside the "
            "personal ones from `plsi research propose`, and let the user pick. Then "
            "`plsi research topic --new '<title>' --question '<q>' --kind open_question "
            "--because '<why now>' --rests-on PMID:<one of its papers> --depth <how thorough>`. "
            "The papers are leads, not evidence: nothing here has read them."),
    }
    if trials:
        out["being_asked_now"] = _open_trials(subject)
    return out


def _open_trials(subject: str) -> dict[str, Any]:
    """ClinicalTrials.gov trials on the subject: a recruiting trial says the question is not settled yet."""
    try:
        results = evidence.search("ctgov", subject, limit=10)["results"]
    except NetworkError as exc:  # one source failing is not the command failing
        return {"trials": [], "note": f"ClinicalTrials.gov did not answer: {type(exc).__name__}"}
    return {"trials": [{"id": r["ref"]["id"], "title": r["title"], "status": r.get("pub_types")}
                       for r in results],
            "note": "a trial still recruiting is the field saying this question is not settled; one that "
                    "finished years ago with no publication is a different question worth asking"}
