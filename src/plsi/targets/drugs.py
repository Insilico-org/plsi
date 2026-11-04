"""Drugs from Open Targets: against a target, against a target in one indication, and in one indication.

Phase, status and sponsor come from the trial records Open Targets carries; warnings and withdrawals come from
ChEMBL via the same endpoint.
"""

from __future__ import annotations

from typing import Any

from plsi.errors import NotFound
from plsi.models import external_str
from plsi.targets.opentargets import CAP_PROSE, DIRECTION_MEANING, query
from plsi.vocab.targets import ClinicalStage

MAX_ASSETS = 40
MAX_TRIALS = 4  # per asset
TRIAL_SOURCES = frozenset({"ClinicalTrials.gov"})

# Drugs against one target in one indication, with stage and direction of effect, from the pair's evidence.
INDICATION_DRUGS = """query IndDrugs($efo: String!, $ids: [String!]!, $n: Int!) {
  disease(efoId: $efo) {
    id name
    evidences(ensemblIds: $ids, datasourceIds: ["clinical_precedence"], size: $n) {
      count
      rows { clinicalStage directionOnTrait directionOnTarget drug { id name } }
    }
  }
}"""

ASSETS = """query Assets($id: String!) {
  target(ensemblId: $id) {
    approvedSymbol
    drugAndClinicalCandidates {
      count
      rows {
        maxClinicalStage
        drug { id name drugType mechanismsOfAction { rows { mechanismOfAction actionType } } }
        diseases { diseaseFromSource }
        clinicalReports { id trialPhase trialOverallStatus trialSponsor { name } source }
      }
    }
  }
}"""

DISEASE_ASSETS = """query DiseaseAssets($efo: String!) {
  disease(efoId: $efo) {
    id name
    drugAndClinicalCandidates {
      count
      rows {
        maxClinicalStage
        drug { id name drugType
               mechanismsOfAction { rows { mechanismOfAction targets { approvedSymbol } } } }
      }
    }
  }
}"""

MAX_INDICATION_DRUGS = 200  # evidence rows read for one pair; the counts below are over these


def indication_drugs(ensembl_id: str, efo_id: str) -> dict[str, Any]:
    """The drugs against this target in this indication (Open Targets' `clinical_precedence` evidence), the
    furthest stage reached for this disease, and the source's direction-of-effect pairs. A pair outside
    `DIRECTION_MEANING` is counted as unrecognised."""
    data = query(INDICATION_DRUGS, {"efo": efo_id, "ids": [ensembl_id], "n": MAX_INDICATION_DRUGS})
    disease = data.get("disease")
    if not disease:
        raise NotFound(f"Open Targets has no disease {efo_id!r}", code="DISEASE_NOT_FOUND")
    found = disease.get("evidences") or {}
    rows = found.get("rows") or []
    stages = [s for s in (ClinicalStage.parse(external_str(r.get("clinicalStage"))) for r in rows) if s]
    drugs: dict[str, str] = {}
    pairs: dict[tuple[str, str], int] = {}
    unread = 0
    for row in rows:
        drug = row.get("drug") or {}
        if name := external_str(drug.get("name")).strip():
            drugs.setdefault(name.lower(), name)
        trait, on_target = external_str(row.get("directionOnTrait")), external_str(row.get("directionOnTarget"))
        if not trait or not on_target:
            continue
        if (trait, on_target) in DIRECTION_MEANING:
            pairs[(trait, on_target)] = pairs.get((trait, on_target), 0) + 1
        else:
            unread += 1
    return {
        "id": disease.get("id"), "name": external_str(disease.get("name")),
        "evidence_rows": found.get("count") or 0, "sampled": len(rows),
        "stage": ClinicalStage.top(stages).value,
        "unrecognised_stage": len(rows) - len(stages),
        "drugs": sorted(drugs.values())[:MAX_ASSETS],
        "drugs_total": len(drugs),
        "directions": [{"on_trait": trait, "on_target": on_target, "rows": count,
                        "means": DIRECTION_MEANING[(trait, on_target)]}
                       for (trait, on_target), count in sorted(pairs.items(), key=lambda kv: -kv[1])],
        "direction_unrecognised": unread,
        "note": "stage, drugs and direction are all scoped to this indication. A stage from another "
                "indication is a different number and is reported under `stage_any_indication`.",
    }


def disease_assets(efo_id: str) -> dict[str, Any]:
    """Every drug and clinical candidate recorded in one indication, with the targets it acts on."""
    disease = query(DISEASE_ASSETS, {"efo": efo_id}).get("disease")
    if not disease:
        raise NotFound(f"Open Targets has no disease {efo_id!r}", code="DISEASE_NOT_FOUND")
    found = disease.get("drugAndClinicalCandidates") or {}
    rows = []
    for row in found.get("rows") or []:
        drug = row.get("drug") or {}
        targets, mechanisms = set(), set()
        for mechanism in (drug.get("mechanismsOfAction") or {}).get("rows") or []:
            if name := external_str(mechanism.get("mechanismOfAction")):
                mechanisms.add(name)
            for target in mechanism.get("targets") or []:
                if symbol := external_str(target.get("approvedSymbol")):
                    targets.add(symbol)
        rows.append({"drug": external_str(drug.get("name")), "chembl_id": external_str(drug.get("id")) or None,
                     "modality": external_str(drug.get("drugType")) or None,
                     "stage_as_sourced": external_str(row.get("maxClinicalStage")),
                     "targets": sorted(targets), "mechanisms": sorted(mechanisms)[:2]})
    return {"id": disease.get("id"), "name": external_str(disease.get("name")),
            "total": found.get("count") or 0, "read": len(rows), "rows": rows}


def assets(ensembl_id: str) -> dict[str, Any]:
    """Drugs and clinical candidates against the target, each with up to MAX_TRIALS of its trial records;
    `trials_total` says how many exist."""
    data = query(ASSETS, {"id": ensembl_id}).get("target")
    if not data:
        raise NotFound(f"Open Targets has no target {ensembl_id!r}", code="TARGET_NOT_FOUND")
    candidates = data.get("drugAndClinicalCandidates") or {}
    rows = []
    for row in (candidates.get("rows") or [])[:MAX_ASSETS]:
        drug = row.get("drug") or {}
        reports = row.get("clinicalReports") or []
        # `clinicalReports` also holds label, ATC and INN records; only ClinicalTrials.gov rows are trials.
        trials = [r for r in reports if str(r.get("source") or "") in TRIAL_SOURCES]
        rows.append({
            "drug": external_str(drug.get("name")), "chembl_id": external_str(drug.get("id")) or None,
            "modality": external_str(drug.get("drugType")),
            "mechanisms": sorted({external_str(m.get("mechanismOfAction"))
                                  for m in (drug.get("mechanismsOfAction") or {}).get("rows") or []})[:3],
            "max_stage_as_sourced": external_str(row.get("maxClinicalStage")),
            "indications": sorted({name for d in row.get("diseases") or []
                                   if (name := external_str(d.get("diseaseFromSource")).strip())})[:6],
            "trials_total": len(trials),
            "other_records": len(reports) - len(trials),
            "trials": [{"id": str(r.get("id") or "").upper(), "phase": external_str(r.get("trialPhase")),
                        "status": external_str(r.get("trialOverallStatus")),
                        "sponsor": external_str((r.get("trialSponsor") or {}).get("name")),
                        "source": external_str(r.get("source"))}
                       for r in trials[:MAX_TRIALS]],
        })
    warned = _warnings([r["chembl_id"] for r in rows if r["chembl_id"]])
    for row in rows:
        row["warnings"] = warned.get(row["chembl_id"] or "", [])
    return {"symbol": external_str(data.get("approvedSymbol")), "total": candidates.get("count"),
            "shown": len(rows), "rows": rows,
            "withdrawn": sorted({r["drug"] for r in rows
                                 if any(w["kind"] == WITHDRAWN for w in r["warnings"])}),
            "black_boxed": sorted({r["drug"] for r in rows
                                   if any(w["kind"] == BLACK_BOX for w in r["warnings"])})}


WARNINGS = """query Warnings($ids: [String!]!) {
  drugs(chemblIds: $ids) {
    id
    drugWarnings { warningType toxicityClass description year country }
  }
}"""
WITHDRAWN = "Withdrawn"
BLACK_BOX = "Black Box Warning"
MAX_WARNINGS = 6  # per drug
MAX_MARKETS = 3


def _markets(country: str) -> str | None:
    """Where a withdrawal applied: the first MAX_MARKETS countries and a count of the rest."""
    names = [n.strip() for n in str(country or "").split(";") if n.strip()]
    if not names:
        return None
    if len(names) <= MAX_MARKETS:
        return "; ".join(names)
    return f"{'; '.join(names[:MAX_MARKETS])} and {len(names) - MAX_MARKETS} more"


def _warnings(chembl_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Black box warnings and withdrawals for the gathered assets, in one batched `drugs(chemblIds:)` call,
    one row per (warning type, toxicity class)."""
    ids = [i for i in dict.fromkeys(chembl_ids) if i]
    if not ids:
        return {}
    rows = query(WARNINGS, {"ids": ids}).get("drugs") or []
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        found = []
        seen: set[tuple[str, str]] = set()
        for warning in (row.get("drugWarnings") or [])[: MAX_WARNINGS * 3]:
            kind, toxicity = external_str(warning.get("warningType")), external_str(warning.get("toxicityClass"))
            if (kind, toxicity) in seen:
                continue
            seen.add((kind, toxicity))
            found.append({"kind": kind, "toxicity": toxicity or None,
                          "description": external_str(warning.get("description"), CAP_PROSE) or None,
                          "year": warning.get("year"),
                          "country": _markets(external_str(warning.get("country")))})
        if found:
            out[external_str(row.get("id"))] = found[:MAX_WARNINGS]
    return out
