"""Proactive blocking screening.

Context comes ONLY from plsi.map.mapper.context(); RxNav and openFDA via plsi.references + plsi.net.
(RxNorm ingredient resolution lives here, independent of Life's normalizer: Policy may not import Life.)
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from pydantic import RootModel

from plsi import net, references
from plsi.clock import now
from plsi.errors import NetworkError, ValidationError
from plsi.events import NewEvent
from plsi.files import load_json
from plsi.map import mapper
from plsi.map.models import CareContext
from plsi.models import CAP_LABEL, SourceRef, parse, sanitize_external
from plsi.policy.evidence import cite_url, label_query, label_title
from plsi.policy.models import ActionInput, Finding, PlanInput, ScreeningContext, ScreeningRecord, SourceConsulted
from plsi.vocab import ActionCategory, EventType, Severity, SourceKind, SourceStatus

SCREEN_MAX_AGE_DAYS = 7
LABEL_SECTIONS = (
    "boxed_warning", "contraindications", "warnings_and_cautions", "warnings",
    "precautions", "drug_interactions", "use_in_specific_populations",
)
SCREENED = (ActionCategory.DRUG, ActionCategory.SUPPLEMENT)
NO_LABEL_SUPPLEMENT = "no regulatory label; Grok must cite literature and the user must acknowledge"
EXCERPT_RADIUS = 300  # characters of label text kept on each side of a hit
AddedFindings = RootModel[dict[str, list[Finding]]]


def _rule(name: str) -> SourceRef:
    return SourceRef(kind=SourceKind.RULE, id=f"plsi.screen.{name}")


def _action_term(action: ActionInput) -> str:
    return (action.code.display if action.code and action.code.display else action.description).lower()


def screening_context(care: CareContext, plan: PlanInput, action: ActionInput) -> ScreeningContext:
    """care context + ingredient names of the OTHER drug/supplement actions in the plan (sorted, lower-case)."""
    others = {_action_term(a) for a in plan.actions if a.local_id != action.local_id and a.category in SCREENED}
    return ScreeningContext(**care.model_dump(), co_action_ingredients=sorted(others))


def _search_terms(context: ScreeningContext) -> list[str]:
    items = [*context.medications, *context.conditions, *context.allergies]
    terms = {t.lower().strip() for i in items for t in (i.text, i.code.display if i.code else None) if t}
    return sorted(t for t in terms | set(context.co_action_ingredients) if len(t) >= 3)


def _ingredient(action: ActionInput) -> str | None:
    """RxNorm ingredient name: the action's code, else RxNav approximateTerm -> related IN/PIN."""
    if action.code and action.code.display:
        return action.code.display
    base = references.api_base("rxnav")
    rxcui = action.code.code if action.code else None
    if rxcui is None:
        found = net.get_json(f"{base}/approximateTerm.json", {"term": action.description, "maxEntries": 10, "option": 1})
        candidates = found.get("approximateGroup", {}).get("candidate") or []
        rxcui = next((c["rxcui"] for c in candidates if c.get("rxcui")), None)
        if rxcui is None:
            return None
    related = net.get_json(f"{base}/rxcui/{rxcui}/related.json", {"tty": "IN PIN"})
    groups = related.get("relatedGroup", {}).get("conceptGroup") or []
    names = {g.get("tty"): [p["name"] for p in g.get("conceptProperties") or []] for g in groups}
    return next(iter(names.get("IN") or names.get("PIN") or []), None)


def _label(name: str) -> dict[str, Any] | None:
    """Newest openFDA label by substance_name.exact, then generic_name.exact (uppercase)."""
    for field in ("substance_name", "generic_name"):
        if results := label_query(f'openfda.{field}.exact:"{name.upper()}"', 5, sort="effective_time:desc").get("results"):
            return max(results, key=lambda r: str(r.get("effective_time", "")))
    return None


def _label_findings(label: dict[str, Any], terms: list[str]) -> list[Finding]:
    set_id = label.get("set_id", "unknown")
    src = SourceRef(kind=SourceKind.LABEL, id=set_id, title=label_title(label), url=cite_url(SourceKind.LABEL, set_id))
    findings = []
    for section in LABEL_SECTIONS:
        text = "\n".join(label.get(section) or [])
        if not text:
            continue
        if section == "boxed_warning":
            findings.append(Finding(severity=Severity.CAUTION, summary="label has a boxed warning", source=src,
                                    excerpt=sanitize_external(text, CAP_LABEL, f"openfda:{section}")))
        for term in terms:
            if hit := re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                start = max(0, hit.start() - EXCERPT_RADIUS)
                severity = Severity.BLOCK if section == "contraindications" else Severity.CAUTION
                findings.append(Finding(severity=severity, summary=f"{section} mentions {term!r}", source=src,
                                        excerpt=sanitize_external(text[start:hit.end() + EXCERPT_RADIUS], CAP_LABEL, f"openfda:{section}")))
    return findings


def screen_action(action: ActionInput, context: ScreeningContext, added: Sequence[Finding] = ()) -> ScreeningRecord:
    """Screen one action against the label (contraindication hit -> block, boxed warning / other section hit -> caution),
    plus the bot's own `added` findings (from reading labels and literature); they can only raise the outcome. Never
    raises for network problems."""
    findings: list[Finding] = list(added)
    consulted: list[SourceConsulted] = []
    if action.category not in SCREENED:
        findings.append(Finding(severity=Severity.NONE, summary=f"{action.category.value} action: no label screening applies",
                                source=_rule("non_drug")))
    else:
        source = "rxnav"
        try:
            ingredient = _ingredient(action)
            consulted.append(SourceConsulted(source="rxnav", status=SourceStatus.OK if ingredient else SourceStatus.NOT_FOUND))
            source = "openfda_label"
            label = _label(ingredient) if ingredient else None
            consulted.append(SourceConsulted(source="openfda_label", status=SourceStatus.OK if label else SourceStatus.NOT_FOUND))
        except NetworkError as exc:
            consulted.append(SourceConsulted(source=source, status=SourceStatus.ERROR))
            findings.append(Finding(severity=Severity.BLOCK, code="SCREENING_UNAVAILABLE", source=_rule("unavailable"),
                                    summary=f"screening source {source} unavailable: {exc.message}"))
        else:
            if label:
                findings += _label_findings(label, _search_terms(context))
            elif action.category == ActionCategory.DRUG:
                findings.append(Finding(severity=Severity.BLOCK, summary=f"no regulatory label found for {ingredient or action.description!r}",
                                        source=_rule("no_label")))
            else:
                findings.append(Finding(severity=Severity.CAUTION, summary=NO_LABEL_SUPPLEMENT, source=_rule("no_label")))
    return ScreeningRecord(
        action_hash=action.compute_action_hash(),
        context_hash=context.compute_context_hash(),
        context=context,
        findings=findings,
        outcome=Severity.top(f.severity for f in findings),
        sources_consulted=consulted,
        screened_at=now(),
    )


def screen(instance: str, file: str, findings: str | None = None) -> dict[str, Any]:
    """`plsi screen --instance N --file plan.json [--findings F]`: one `screening` event per action.
    F is {action local_id: [Finding]}, the bot's judgment added to the label floor."""
    plan = parse(PlanInput, load_json(file), "plan")
    added = parse(AddedFindings, load_json(findings), "findings").root if findings else {}
    if unknown := set(added) - {a.local_id for a in plan.actions}:
        raise ValidationError(f"findings for unknown actions: {sorted(unknown)}")
    care = mapper.context(instance)
    records = [screen_action(a, screening_context(care, plan, a), added.get(a.local_id, [])) for a in plan.actions]
    ids = mapper.event_store(instance).append_many([NewEvent(EventType.SCREENING, r) for r in records])
    return {
        "screening_event_ids": {a.local_id: eid for a, (eid, _) in zip(plan.actions, ids, strict=True)},
        "outcomes": {a.local_id: r.outcome.value for a, r in zip(plan.actions, records, strict=True)},
        "records": [r.dump() for r in records],
    }
