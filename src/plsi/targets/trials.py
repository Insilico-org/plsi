"""`plsi targets trials`: grounding hand-harvested asset names on the ClinicalTrials.gov records that exist.

Trials are indexed by drug, not by gene, so the names come from the bot and this turns each name into records.
A study counts only when one of its interventions is the asset, by primary name or by `otherNames`; studies
that only mention it are counted in `near_misses`, and those naming it in the title are handed back for the
bot to judge. A stage is reported per (asset x condition), because a phase belongs to an indication.
"""

from __future__ import annotations

import re
from typing import Any

from plsi.errors import ValidationError
from plsi.models import external_str
from plsi.policy import ctgov
from plsi.vocab import fold
from plsi.vocab.targets import ClinicalStage

MAX_ASSETS = 12
MAX_STUDIES = 50  # per asset; beyond this the asset is too broadly named to roll up
MAX_SYNONYMS = 8
MAX_TITLED = 5
# An intervention entry named as a combination carries several drugs' names, so none is attributed to the asset.
COMBINATION = (" in combination", " combined with", " plus ", " with ", " and ", "+", "/")
MAX_SYNONYM_WORDS = 3  # longer intervention names are descriptions, not names
# Arm and formulation words: an intervention name containing one is not another name for the drug.
NOT_A_NAME = ("sequence", "cohort", "arm", "part", "group", "dose", "placebo", "tablet", "capsule",
              "injection", "infusion", "solution", "gel", "cream", "ointment", "release", "formulation",
              "vehicle", "comparator", "period", "treatment", "regimen", "mg", "ml")
FIELDS = ("NCTId,BriefTitle,OverallStatus,Phase,StartDate,PrimaryCompletionDate,LeadSponsorName,"
          "EnrollmentCount,Condition,InterventionName,InterventionOtherName,InterventionType,"
          "WhyStopped,StudyType,HasResults,CompletionDate,LocationCountry,CollaboratorName")


def _search(name: str) -> list[dict[str, Any]]:
    data = ctgov.studies({"query.intr": f'"{name}"', "pageSize": MAX_STUDIES, "fields": FIELDS})
    return [ctgov.record(raw) for raw in data.get("studies") or []]


def _matched(study: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """The interventions in this study that are the asset, by primary name or by `otherNames` (a code name is
    often filed only as a synonym)."""
    wanted = fold(name)
    if not wanted:
        return []
    return [i for i in study["interventions"]
            if any(wanted in fold(given) for given in [i["name"], *i["other_names"]])]


def _titled(study: dict[str, Any], name: str) -> bool:
    """The asset is in the title but in none of the interventions: either a comparator mention or the same drug
    filed under another name with no synonym recorded. Handed back with what the study administers; the bot
    decides which."""
    wanted = fold(name)
    return bool(wanted) and wanted in fold(study.get("title")) and not _matched(study, name)


def _other_names(studies: list[dict[str, Any]], asset: str) -> list[str]:
    """The asset's other names as the registry files them, read only from the matching intervention entries.
    Combination entries are skipped whole, a comma-joined entry is split into names, and arm labels, dosage
    forms and descriptions are dropped."""
    wanted = fold(asset)
    found = set()
    for study in studies:
        for intervention in _matched(study, asset):
            if _is_combination(intervention["name"]):
                continue  # its names belong to several drugs; none can be attributed to this one
            found.update([intervention["name"], *intervention["other_names"]])
    out: dict[str, str] = {}
    for name in sorted({part.strip() for whole in found for part in str(whole or "").split(",")}):
        folded = fold(name)
        if not folded or folded == wanted or wanted in folded:
            continue  # the asset itself, or the asset with a dose or a prefix attached
        if _is_combination(name) or len(name.split()) > MAX_SYNONYM_WORDS:
            continue  # a combination or a description, not a name
        if any(word in NOT_A_NAME for word in re.split(r"[\s-]+", name.lower())):
            continue  # an arm label or a dosage form
        out.setdefault(folded, name)  # spelling variants of one name collapse
    return sorted(out.values())[:MAX_SYNONYMS]


def _is_combination(name: str) -> bool:
    lowered = f" {str(name or '').lower()} "
    return any(marker in lowered for marker in COMBINATION)


def _furthest(studies: list[dict[str, Any]]) -> str:
    stages = [s for s in (ClinicalStage.parse(phase) for study in studies for phase in study["phases"]) if s]
    return ClinicalStage.top(stages).value


def _condition(name: str) -> str:
    """One condition folded mechanically (case, a trailing parenthetical, an inverted "Noun, Adjective" form,
    hyphens) so one disease's spellings make one row. Real synonyms ("cancer" / "carcinoma") stay apart."""
    text_ = re.sub(r"\s*\([^)]*\)\s*$", "", str(name or "").strip())
    if text_.count(",") == 1:
        tail, head = (part.strip() for part in text_.split(","))
        text_ = f"{head} {tail}"
    text_ = re.sub(r"\s+", " ", text_.replace("-", " ")).strip()
    return text_.lower().capitalize() or "(no condition recorded)"


def _by_indication(studies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per condition, with its own furthest stage, statuses and sponsors. A trial with several
    conditions counts under each, as registered."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for study in studies:
        for condition in {_condition(c) for c in study["conditions"]} or {"(no condition recorded)"}:
            grouped.setdefault(condition, []).append(study)
    rows = []
    for condition, group in grouped.items():
        rows.append({
            "indication": condition,
            "stage": _furthest(group),
            "trials": len(group),
            "statuses": sorted({s["status"] for s in group if s["status"]}),
            "with_results": sum(1 for s in group if s["has_results"]),
            "sponsors": sorted({s["sponsor"] for s in group if s["sponsor"]})[:4],
            "ncts": sorted({s["nct"] for s in group})[:8],
            "stopped": [{"nct": s["nct"], "why": s["why_stopped"]} for s in group if s["why_stopped"]][:3],
        })
    rows.sort(key=lambda r: (-ClinicalStage(r["stage"]).rank, -r["trials"]))
    return rows


def rollup(gene: str, assets: list[str]) -> dict[str, Any]:
    """`plsi targets trials --gene <SYMBOL> --asset <NAME> ...`: each asset's trial records, for the NCT ids
    `harvested_assets` needs. Writes nothing."""
    names = [a for a in dict.fromkeys(a.strip() for a in assets or []) if a]
    if not 1 <= len(names) <= MAX_ASSETS:
        raise ValidationError(f"name between 1 and {MAX_ASSETS} assets",
                              hint="plsi targets trials --gene <SYMBOL> --asset test-drug-a --asset test-drug-b")
    rows = []
    for name in names:
        found = _search(name)
        kept = [s for s in found if _matched(s, name)]  # the study gives the asset, not only names it
        interventional = [s for s in kept if s["study_type"] == ctgov.INTERVENTIONAL]
        titled = [{"nct": s["nct"], "title": s["title"],
                   "administers": [i["name"] for i in s["interventions"]][:4]}
                  for s in found if _titled(s, name)][:MAX_TITLED]
        rows.append({
            "asset": external_str(name),
            "also_known_as": _other_names(kept, name),
            "trials": len(kept), "interventional": len(interventional),
            "near_misses": len(found) - len(kept),  # returned for the name but not administering it
            "named_in_title": titled,
            # For an asset with no trials of its own: what the studies naming it in their title administer.
            "try_instead": sorted({given for s in titled for given in s["administers"]
                                   if fold(given) != fold(name)
                                   and given.lower() not in ("placebo", "comparator")}) if not kept else [],
            "stage": _furthest(interventional),
            "with_results": sum(1 for s in interventional if s["has_results"]),
            "by_indication": _by_indication(interventional),
            "records": [{k: s[k] for k in ("nct", "title", "status", "sponsor", "started", "completed",
                                           "enrollment", "has_results", "countries", "collaborators")}
                        for s in sorted(interventional, key=lambda s: s["started"] or "", reverse=True)[:6]],
            "found": bool(kept),
        })
    missing = [r["asset"] for r in rows if not r["found"]]
    same = _same_drug(rows)
    return {
        "gene": external_str(gene), "assets": len(rows), "rows": rows, "no_trials": missing,
        "same_drug": same or None,
        "merge": ("these are the same drug under two names and their rows do NOT overlap - take the union, "
                  "and check which name the registrational trials are filed under" if same else None),
        "source": {"ref": "ctgov", "external_text": True},
        "note": "Phase, status and sponsor are the registration's own words. A study that names the asset "
                "without administering it was dropped and counted in `near_misses`. A stage is per "
                "indication: never carry one across.",
        "unfound": "An asset with no trial is not disproved - it may be preclinical, ex-US, or named "
                   "differently here. **Read `named_in_title` and `try_instead` first**: a study that names "
                   "it and administers something else is usually the same drug under the name the registry "
                   "filed it under, and `try_instead` is that name."
        if missing else None,
        "retry": sorted({name for row in rows for name in row["try_instead"]}) or None,
    }


def _same_drug(rows: list[dict[str, Any]]) -> list[list[str]]:
    """Pairs of queried names the registry links (by synonym or by title): one drug under two names."""
    folded = {fold(r["asset"]): r for r in rows}
    pairs: list[list[str]] = []
    for row in rows:
        for alias in [*row["also_known_as"], *row["try_instead"]]:
            other = folded.get(fold(alias))
            pair = sorted((row["asset"], other["asset"])) if other and other["asset"] != row["asset"] else None
            if pair and pair not in pairs:
                pairs.append(pair)
    return pairs
