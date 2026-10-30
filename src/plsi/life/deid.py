"""Deidentification profile `plsi-limited-v1`.

Event dates are kept, so this is NOT HIPAA Safe Harbor. The profile:
- subject.json keeps only birth_year and sex (age >= 90 -> birth_year null, age_group "90+"; see deid_subject_fields,
  applied by plsi.life.store, which owns subject.json);
- Origin keeps file_sha256 and page, never a path or filename;
- FHIR allowlist: code.coding, value[x], effective[x] (Period -> effective_at + effective_end), clinicalStatus,
  component[] (one observation each), medication dose text and doseQuantity. Everything else is dropped (identifier,
  subject, performer, note, text, contained, extension, attachments);
- Patient name parts, identifier values, telecom and address are held in memory only; any observation from
  that bundle whose text contains one of them is rejected with IDENTIFIER_IN_TEXT.
"""

from __future__ import annotations

import re
from typing import Any

from plsi.clock import now
from plsi.vocab import Sex

PROFILE = "plsi-limited-v1"
AGE_GROUP_90 = "90+"
MIN_LEN = 3  # shorter strings would produce false hits
SHORT_LEN = 6  # identifiers shorter than this must match a whole token

_GENDER = {"male": Sex.M, "female": Sex.F, "other": Sex.X, "unknown": Sex.UNKNOWN}


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def patient_identifiers(patient: dict[str, Any]) -> set[str]:
    """Collect identifying strings from a FHIR Patient resource, in memory only.

    Output: name parts (given/family/prefix/suffix/text), identifier values, telecom values and address parts
    (line, city, postalCode, text), each stripped; strings shorter than 3 chars are skipped. Never written anywhere.
    """
    found: list[str] = []
    for name in patient.get("name") or []:
        for key in ("given", "family", "prefix", "suffix", "text"):
            found += _strings(name.get(key))
    for key in ("identifier", "telecom"):
        found += [str(item.get("value")) for item in patient.get(key) or [] if item.get("value") is not None]
    for addr in patient.get("address") or []:
        for key in ("line", "city", "postalCode", "text"):
            found += _strings(addr.get(key))
    return {s.strip() for s in found if len(s.strip()) >= MIN_LEN}


def contains_identifier(text: str, identifiers: set[str]) -> bool:
    """True if `text` contains any identifier (case-insensitive; whole-token for short ones)."""
    low = text.lower()
    for ident in identifiers:
        needle = ident.lower()
        if len(needle) >= SHORT_LEN:
            if needle in low:
                return True
        elif re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", low):
            return True
    return False


def patient_subject_fields(patient: dict[str, Any]) -> dict[str, Any]:
    """FHIR Patient -> {"birth_year": int | None, "sex": Sex | None}; birthDate keeps only the year.
    Absent fields are None so they never overwrite subject.json."""
    match = re.match(r"^(\d{4})", str(patient.get("birthDate") or ""))
    return {
        "birth_year": int(match[1]) if match else None,
        "sex": _GENDER.get(str(patient.get("gender") or "").lower()),
    }


def deid_subject_fields(birth_year: int | None, sex: Sex | str | None) -> dict[str, Any]:
    """Keep birth_year and sex only; age >= 90 -> birth_year null, age_group "90+"."""
    over_90 = birth_year is not None and now().year - birth_year >= 90
    return {
        "birth_year": None if over_90 else birth_year,
        "age_group": AGE_GROUP_90 if over_90 else None,
        "sex": Sex(sex) if sex is not None else Sex.UNKNOWN,
    }
