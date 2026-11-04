"""ClinicalTrials.gov v2: the `/studies` search, the one-study lookup and the study-record parse, the only calls
to it and the only reading of its record shape."""

from __future__ import annotations

from typing import Any

from plsi import net, references
from plsi.models import external_str

INTERVENTIONAL = "INTERVENTIONAL"  # the registry's StudyType word
MAX_COUNTRIES = 6


def studies(params: dict[str, Any]) -> dict[str, Any]:
    """One `/studies` search with the given query parameters -> the registry's JSON reply ({} when empty)."""
    return net.get_json(f"{references.api_base('ctgov')}/studies", params) or {}


def study(nct_id: str, fields: str) -> Any:
    """One registry record, `/studies/<NCT id>`, limited to `fields`; None when the registry holds no such study."""
    return net.get_json(f"{references.api_base('ctgov')}/studies/{nct_id}", {"fields": fields}, missing=(404,))


def record(raw: dict[str, Any]) -> dict[str, Any]:
    """One study of a `/studies` reply as flat fields in the registry's own words. A field the search did not
    ask for comes back empty."""
    section = raw.get("protocolSection") or {}
    ident = section.get("identificationModule") or {}
    status = section.get("statusModule") or {}
    design = section.get("designModule") or {}
    sponsors = section.get("sponsorCollaboratorsModule") or {}
    return {
        "nct": external_str(ident.get("nctId")).upper(),
        "title": external_str(ident.get("briefTitle")),
        "status": external_str(status.get("overallStatus")),
        "why_stopped": external_str(status.get("whyStopped")) or None,
        "started": external_str((status.get("startDateStruct") or {}).get("date"))[:10] or None,
        "completed": external_str((status.get("completionDateStruct") or {}).get("date"))[:10] or None,
        "has_results": bool(raw.get("hasResults")),
        "phases": [external_str(p) for p in design.get("phases") or []],
        "study_type": external_str(design.get("studyType")),
        "enrollment": (design.get("enrollmentInfo") or {}).get("count"),
        "sponsor": external_str((sponsors.get("leadSponsor") or {}).get("name")),
        "collaborators": [external_str(c.get("name")) for c in sponsors.get("collaborators") or []][:4],
        "countries": sorted({external_str(loc.get("country")) for loc in
                             (section.get("contactsLocationsModule") or {}).get("locations") or []
                             if loc.get("country")})[:MAX_COUNTRIES],
        "conditions": [external_str(c) for c in (section.get("conditionsModule") or {}).get("conditions") or []][:6],
        # One entry per intervention with its own synonyms, so a partner drug's names stay with that drug.
        "interventions": [{"name": external_str(i.get("name")), "type": external_str(i.get("type")),
                           "other_names": [external_str(n) for n in i.get("otherNames") or []]}
                          for i in (section.get("armsInterventionsModule") or {}).get("interventions") or []],
    }
