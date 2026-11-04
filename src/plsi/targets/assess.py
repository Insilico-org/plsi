"""`plsi targets assess`: the bot's judgment on a target, and the refusals it has to pass to be recorded.

The refusals (`target-refusal-N`) check grounding, never the verdict: (1) every claim carries a source
identifier; (2) a hand-harvested asset carries a trial id and is not already in the gathered record; (3) a claim
about the whole field ("the only", "first-in-class", "no identified") has a source in the same sentence, and
`limitations` is not checked for it; (4) every verifiable identifier is in the verification ledger inside its
age limit; (7) a platform read names a platform the egress ledger shows was asked within that age limit. The
schema adds closed rating words and a required `falsifier` and non-empty `limitations`. None of this checks
that a resolving citation is relevant to its sentence; every identifier is kept so a reader can.
"""

from __future__ import annotations

import re
from typing import Any

from plsi.errors import GateFailed, violation
from plsi.files import load_json
from plsi.models import SourceRef, parse
from plsi.policy import evidence, oracles
from plsi.targets import rank, store
from plsi.targets.models import Assessment
from plsi.vocab import SourceKind
from plsi.vocab.targets import ExternalSource

# Claims about the whole field, allowed only in a sentence that also carries a source id: trials are indexed
# by drug, not by gene, so an absence from a harvested table is not proof. Grammatical patterns matched on
# word boundaries, so "console" does not match "sole", once Markdown emphasis (`*`, `_`) is removed.
TARGET_SUPERLATIVE_RE = re.compile(
    r"\b(?:"
    # "the only / sole / first / best / leading / strongest / largest / most advanced ..."
    r"the\s+(?:only|sole|first|best|leading|strongest|largest|lone|single|one|most\b\s*\w*)"
    # "nobody / no one has ..."
    r"|(?:nobody|no\s?one|none)\b"
    # "no other / no company / no sponsor / no clinical programme / no competitor ..."
    r"|no\s+(?:other|further|competing|competitor|company|sponsor|clinical|published|identified|known|"
    r"approved|disclosed|existing|rival|drug|asset|molecule|programme|program|trial|compound)\w*"
    # fixed phrases
    r"|first[-\s]in[-\s]class|only\s+clinical|unprecedented|never\s+been|has\s+ever\b"
    r"|unique(?:ly)?\b|untouched\b|uncontested\b"
    r")",
    re.IGNORECASE)

# The identifiers an assessment may cite; `skills/targets/grounding` lists the same set. A PDB entry needs the
# literal `PDB` prefix, because a bare four-character code cannot be told from a year.
TARGET_CITATION_RE = re.compile(
    r"(?:PMID[:\s]?\d{1,9}"
    r"|NCT\d{8}"
    r"|\b10\.\d{4,9}/\S+"
    r"|CHEMBL\d+"
    r"|ENSG\d{11}"
    r"|EFO_\d+|MONDO_\d+|MGI:\d+"
    r"|\brs\d+"
    r"|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"  # openFDA/DailyMed label set id
    r"|PDB[:\s]+\d[A-Za-z0-9]{3}\b"
    r"|AF-[A-Z0-9]+-F\d+"
    r"|\b[OPQ][0-9][A-Z0-9]{3}[0-9]\b|\b[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}\b)",
    re.IGNORECASE)

# The kinds the verification ledger can check. ChEMBL, Ensembl, EFO and MGI accessions count as sources for
# target-refusal-1 but have no `plsi evidence verify` kind, so target-refusal-4 does not cover them.
VERIFIABLE = {"pmid": SourceKind.PMID, "nct": SourceKind.NCT, "doi": SourceKind.DOI,
              "label": SourceKind.LABEL}
SENTENCE_RE = re.compile(r"[^.;\n]+")
EMPHASIS_RE = re.compile(r"[*_]")


def _ids(text: str) -> list[tuple[str, str]]:
    """(kind, id) for every verifiable identifier in a string, normalised the way the ledger stores them."""
    out = []
    for match in TARGET_CITATION_RE.findall(text or ""):
        token = match.strip()
        upper = token.upper()
        if upper.startswith("PMID"):
            out.append(("pmid", re.sub(r"\D", "", token)))
        elif upper.startswith("NCT"):
            out.append(("nct", upper.rstrip(".,);")))
        elif token.startswith("10."):
            out.append(("doi", token.rstrip(".,);")))
        elif re.fullmatch(r"[0-9a-f-]{36}", token.lower()):  # a DailyMed/openFDA label set id
            out.append(("label", token.lower()))
    return out


def _sourced(where: str, label: str, text: str) -> list[dict[str, str]]:
    """Refusal 1: a claim carries an identifier, or it is not a claim this file may hold."""
    if TARGET_CITATION_RE.search(text or ""):
        return []
    return [violation(where, "target-refusal-1", f"{label} carries no source identifier",
                      "write the id inline - (PMID 12345678), (NCT01234567), a DOI, a ChEMBL or Ensembl "
                      "accession. If there is none, say so in `limitations` instead of asserting it")]


def _superlatives(where: str, label: str, text: str) -> list[dict[str, str]]:
    """Refusal 3: a claim about the whole field needs a source in the same sentence. Checked per sentence on
    the rationale, risks and strategies; not on `limitations`, which exists for stating gaps."""
    out = []
    for sentence in SENTENCE_RE.findall(text or ""):
        found = TARGET_SUPERLATIVE_RE.search(EMPHASIS_RE.sub("", sentence))
        if found and not TARGET_CITATION_RE.search(sentence):
            out.append(violation(where, "target-refusal-3",
                                 f"{label} claims {found.group(0).lower()!r} with no source",
                                 "a drug missing from a table is not proof it does not exist - trials are "
                                 "indexed by drug, not by gene. Put the absence in `limitations` ('no identified "
                                 "programme in the registries searched'), or keep it here with the source "
                                 "identifier in the same sentence"))
    return out


def _known_drugs(facts: dict[str, Any]) -> set[str]:
    return {str(row.get("drug") or "").strip().lower()
            for row in (facts.get("assets") or {}).get("rows") or []}


def check(assessment: Assessment, facts: dict[str, Any]) -> None:
    """Every refusal at once, so a bot that got three things wrong learns all three."""
    bad: list[dict[str, str]] = []
    known = _known_drugs(facts)

    bad += _sourced("rationale", "the rationale", assessment.rationale)
    bad += _superlatives("rationale", "the rationale", assessment.rationale)
    for index, risk in enumerate(assessment.risks):
        where = f"risks[{index}] {risk.dimension}"
        bad += _sourced(where, "the evidence for this risk", risk.evidence)
        bad += _superlatives(where, "this risk", f"{risk.evidence} {risk.mitigation}")
    for index, strategy in enumerate(assessment.strategies):
        where = f"strategies[{index}] {strategy.name}"
        bad += _sourced(where, "this strategy", strategy.description)
        bad += _superlatives(where, "this strategy", strategy.description)

    # Refusal 4: every verifiable id anywhere in the file resolves in the ledger (this also covers the NCT
    # the schema requires on a hand-harvested asset).
    harvested = {a.drug.strip().lower() for a in assessment.harvested_assets}
    seen: set[tuple[str, str]] = set()
    for where, text in _claims(assessment):
        for kind, ident in _ids(text):
            if (kind, ident) in seen:
                continue
            seen.add((kind, ident))
            if not evidence.is_verified(SourceRef(kind=VERIFIABLE[kind], id=ident)):
                bad.append(violation(where, "target-refusal-4", f"{kind} {ident} is not verified",
                                     f"plsi evidence verify --kind {kind} --id {ident} "
                                     f"(a check older than {evidence.LEDGER_MAX_AGE_DAYS} days has expired)"))
    # Refusal 7: a platform read is recorded only when the egress ledger holds a billed call to that platform
    # inside the verification age limit.
    for index, read in enumerate(assessment.platform_reads):
        if not oracles.asked(read.source.value, read.tool, evidence.LEDGER_MAX_AGE_DAYS):
            bad.append(violation(f"platform_reads[{index}] {read.source.value}", "target-refusal-7",
                                 f"no {read.source.value} call"
                                 + (f" to {read.tool}" if read.source == ExternalSource.PANDAOMICS else "")
                                 + f" in the last {evidence.LEDGER_MAX_AGE_DAYS} days is in the egress ledger, "
                                   "so nothing here shows the platform was asked",
                                 f"ask it through plsi oracle {read.source.value} first, or remove the entry"))
    if known and harvested & known:
        overlap = ", ".join(sorted(harvested & known))
        bad.append(violation("harvested_assets", "target-refusal-2",
                             f"{overlap} is already in the gathered record",
                             "harvested_assets is for what the structured sources missed; a duplicate makes "
                             "the landscape look wider than it is"))
    if bad:
        raise GateFailed(bad, "the assessment was refused")


def _claims(assessment: Assessment) -> list[tuple[str, str]]:
    """Every field that may carry an identifier, with where it is, for the ledger check."""
    out = [("rationale", assessment.rationale), ("falsifier", assessment.falsifier),
           ("next_experiment", assessment.next_experiment)]
    out += [(f"limitations[{i}]", text) for i, text in enumerate(assessment.limitations)]
    out += [(f"risks[{i}]", f"{r.evidence} {r.mitigation}") for i, r in enumerate(assessment.risks)]
    out += [(f"strategies[{i}]", s.description) for i, s in enumerate(assessment.strategies)]
    out += [(f"harvested_assets[{i}]", a.nct) for i, a in enumerate(assessment.harvested_assets)]
    return out


def assess(gene: str, file: str) -> dict[str, Any]:
    """`plsi targets assess --gene <SYMBOL> --file assessment.json`: record the judgment, or refuse it whole
    with every violation at once. The gathered facts are never changed."""
    document = store.load(gene)
    assessment = parse(Assessment, load_json(file), "target assessment", code="CLOSED_VOCABULARY")
    facts = document.get("facts") or {}
    check(assessment, facts)
    path = store.save(gene, facts, assessment.dump())
    return {"gene": document.get("gene"), "verdict": assessment.verdict.value,
            "indication": assessment.indication or None,
            "ratings": {"druggability": assessment.druggability.value, "safety": assessment.safety.value,
                        "competition": assessment.competition.value},
            "risks": len(assessment.risks), "strategies": len(assessment.strategies),
            "harvested_assets": len(assessment.harvested_assets),
            "platform_reads": [{"source": r.source.value, "tool": r.tool, "asked": r.asked}
                               for r in assessment.platform_reads],
            "limitations": assessment.limitations, "path": str(path),
            "still_open": rank.summary(facts)["open_questions"],
            "note": "the gathered facts were not changed; an assessment is an opinion about them",
            "next": f"plsi targets show --gene {document.get('gene')}"}
