"""The code formats of the Mothership wire (WIRE §2), the same as the Mother's: each code system's pattern, the
LOINC mod-10 check digit and the SNOMED CT Verhoeff check digit. `free` and `cpg` codes are PLSI's own names: they
leave the computer only when a shipped or installed map declares them (`shareable`)."""

from __future__ import annotations

import re
from typing import Any

from plsi.vocab import CodeSystem

PATTERNS = {
    CodeSystem.LOINC: re.compile(r"[0-9]{1,7}-[0-9]"),
    CodeSystem.RXNORM: re.compile(r"[0-9]{1,10}"),
    CodeSystem.SNOMED: re.compile(r"[0-9]{6,18}"),
    CodeSystem.ICD10CM: re.compile(r"[A-TV-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?"),
    CodeSystem.CPG: re.compile(r"[a-z][a-z0-9_.:-]{0,63}"),
    CodeSystem.FREE: re.compile(r"[a-z][a-z0-9_.:-]{0,63}"),
}
LOCAL = frozenset({CodeSystem.FREE, CodeSystem.CPG})  # PLSI's own names: no id-number exemption, map-declared only
_D = ("0123456789", "1234067895", "2340178956", "3401289567", "4012395678",
      "5987604321", "6598710432", "7659821043", "8765932104", "9876543210")
_P = ("0123456789", "1576283094", "5803796142", "8916043527", "9453126870", "4286573901", "2793806415", "7046913285")


def _luhn(digits: str) -> int:
    """The LOINC check digit of the code's digits before the hyphen (mod 10, doubling from the right)."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch) * (2 if i % 2 == 0 else 1)
        total += d // 10 + d % 10
    return (10 - total % 10) % 10


def _verhoeff(digits: str) -> bool:
    """The whole SNOMED CT identifier, its last digit the check digit, passes the Verhoeff check."""
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = int(_D[c][int(_P[i % 8][int(ch)])])
    return c == 0


def valid(system: Any, code: Any) -> bool:
    """`code` is a string in the format of `system`, a known code system, with a valid check digit."""
    if not (isinstance(system, str) and system in tuple(CodeSystem) and isinstance(code, str)
            and PATTERNS[CodeSystem(system)].fullmatch(code)):
        return False
    if system == CodeSystem.LOINC:
        base, check = code.split("-")
        return _luhn(base) == int(check)
    return _verhoeff(code) if system == CodeSystem.SNOMED else True


def shareable(system: Any, code: Any, declared: set[tuple[str, str]]) -> bool:
    """A valid code that may leave the computer: a free or cpg code only when a map declares it (`declared`)."""
    return valid(system, code) and (system not in LOCAL or (system, code) in declared)
