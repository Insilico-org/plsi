"""`plsi targets unmet`: what an indication already has, read off the record.

Three counts from Open Targets - approved molecules (salt forms collapsed), the pipeline by stage, and the
distinct proteins the approved drugs act on - plus ClinicalTrials.gov's interventional trials and how many
stopped. There is no unmet-need score: the counts do not share an axis. Prevalence, burden and efficacy are
not in these sources and are listed as unknown.
"""

from __future__ import annotations

from typing import Any

from plsi.models import external_str
from plsi.policy import ctgov
from plsi.targets import drugs, opentargets, rank
from plsi.vocab.targets import ClinicalStage

# ClinicalTrials.gov overall statuses counted as stopped.
CTGOV_STOPPED = frozenset({"TERMINATED", "WITHDRAWN", "SUSPENDED"})

LATE = ClinicalStage.PHASE_3  # "late stage" in the pipeline count: phase 3 or beyond, short of approval
MAX_NAMED = 12
MAX_CONDITION_STUDIES = 200  # one page; the total comes from the registry's own count
MAX_STOP_REASONS = 8


def _molecules(rows: list[dict[str, Any]]) -> list[str]:
    """Distinct molecules, salts collapsed, in the source's own spelling."""
    seen: dict[str, str] = {}
    for row in rows:
        name = str(row.get("drug") or "").strip()
        if name:
            seen.setdefault(rank.molecule(name), name)
    return sorted(seen.values())


def by_condition(condition: str) -> dict[str, Any]:
    """Interventional trials registered against one disease, their statuses, and the sponsors' stop reasons,
    verbatim and unclassified. Counts are over the page read."""
    data = ctgov.studies({"query.cond": f'"{condition}"',
                          "filter.advanced": f"AREA[StudyType]{ctgov.INTERVENTIONAL}",
                          "pageSize": MAX_CONDITION_STUDIES, "countTotal": "true",
                          "fields": "NCTId,OverallStatus,Phase,WhyStopped,StartDate"})
    studies = [ctgov.record(raw) for raw in data.get("studies") or []]
    statuses: dict[str, int] = {}
    for study in studies:
        statuses[study["status"]] = statuses.get(study["status"], 0) + 1
    reasons = [{"nct": s["nct"], "said": s["why_stopped"]} for s in studies if s["why_stopped"]]
    stopped = sum(count for status, count in statuses.items() if status in CTGOV_STOPPED)
    return {
        "condition": external_str(condition),
        "interventional_total": data.get("totalCount"),
        "read": len(studies),
        "statuses": dict(sorted(statuses.items(), key=lambda kv: -kv[1])),
        "stopped": stopped,
        "stopped_of_read": f"{stopped} of {len(studies)}" if studies else None,
        "reasons": reasons[:MAX_STOP_REASONS],
        "note": "statuses and stop counts are over the page read, not the whole registry; the reasons are the "
                "sponsors' own words and are not classified, so a stop count is not a failure count.",
    }


def unmet(disease: str) -> dict[str, Any]:
    """`plsi targets unmet --disease "<name>"`: what is approved, what is in the pipeline, what stopped."""
    found = opentargets.find_disease(disease)
    assets = drugs.disease_assets(found["id"])
    rows = assets["rows"]

    staged = [(row, ClinicalStage.parse(row["stage_as_sourced"])) for row in rows]
    approved = [row for row, stage in staged if stage is ClinicalStage.APPROVED]
    late = [row for row, stage in staged if stage is not None and stage.rank >= LATE.rank
            and stage is not ClinicalStage.APPROVED]
    by_stage: dict[str, int] = {}
    for _, stage in staged:
        key = stage.value if stage else "unrecognised"
        by_stage[key] = by_stage.get(key, 0) + 1

    approved_targets = sorted({t for row in approved for t in row["targets"]})
    all_targets = sorted({t for row in rows for t in row["targets"]})
    molecules = _molecules(approved)

    return {
        "disease": {"id": found["id"], "name": found["name"],
                    "also_known_as": found.get("also_known_as") or []},
        "approved": {
            "rows": len(approved), "molecules": len(molecules), "named": molecules[:MAX_NAMED],
            "targets": approved_targets[:MAX_NAMED], "distinct_targets": len(approved_targets),
            "modalities": sorted({row["modality"] for row in approved if row["modality"]}),
        },
        "pipeline": {
            "assets": assets["total"], "read": assets["read"], "by_stage": by_stage,
            "late_stage": len(late), "distinct_targets": len(all_targets),
        },
        "trials": by_condition(found["name"]),
        "reads": _reads(approved, molecules, approved_targets, late, all_targets, found["name"]),
        "unknown": [
            "how many people have it: no prevalence or incidence in any source read here",
            "how well the approved drugs work: no efficacy, no effect size, no comparison to standard care",
            "what patients are actually left with: no quality-of-life or symptom burden anywhere in this",
            "whether a stopped trial stopped for a scientific reason: the registry's reasons are free text "
            "and are handed back unsorted",
        ],
        "no_score": "There is no unmet-need score. A drug count, a trial count and a stop rate do not "
                    "share an axis.",
        "source": {"refs": ["open_targets", "ctgov"], "external_text": True},
        "next": f"plsi targets discover --disease \"{found['name']}\"",
    }


def _reads(approved: list[dict[str, Any]], molecules: list[str], approved_targets: list[str],
           late: list[dict[str, Any]], all_targets: list[str], name: str) -> list[str]:
    """The counts as plain sentences, each naming the number it rests on. Interpretation is the skill's."""
    out = []
    if not approved:
        out.append(f"no asset is recorded as approved for {name} in Open Targets; check the source's coverage "
                   "before relying on this")
    else:
        out.append(f"{len(molecules)} approved molecule(s) on record"
                   + (f", from {len(approved)} rows once salt forms are collapsed"
                      if len(approved) > len(molecules) else ""))
    if approved_targets:
        out.append(f"the approved molecules act on {len(approved_targets)} distinct protein(s) "
                   f"({', '.join(approved_targets[:MAX_NAMED])})"
                   + (f"; a multi-target molecule counts once as a molecule and once per protein, so "
                      f"{len(approved_targets)} proteins come from {len(molecules)} molecule(s)"
                      if len(approved_targets) > len(molecules) else ""))
    elif approved:
        out.append("no target is recorded behind any approved molecule here")
    if late:
        out.append(f"{len(late)} asset(s) reached phase 3 or beyond without an approval on record")
    if all_targets:
        out.append(f"{len(all_targets)} distinct protein(s) are recorded across every asset, approved or not")
    return out
