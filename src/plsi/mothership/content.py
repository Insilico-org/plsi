"""What a contribution may carry (WIRE §2): coded fields only, the field tables below and nothing else; codes valid
in their system (plsi.codes), finite bounded numbers. The same rules, rule names and paths as the Mother's gate: a
coordinate key is `#key[<n>]`, an unknown key `#unknown[<n>]` (n = its position), never the key text."""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import partial
from typing import Any

from plsi import codes
from plsi.mothership.scan import HEX64, ID, MAX_NUMBER, MONTH, flag, keyed, listed
from plsi.vocab import ClinicalStatus, Comparator, ContributionKind, Ethnicity, Sex, ValueStatus

CONSENT_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
MAP_VERSION = re.compile(r"[0-9A-Za-z.+-]{1,32}")
UNIT = re.compile(r"[A-Za-z0-9%/.*^()\[\]{}'_-]{1,32}")  # UCUM-like, no whitespace
AGE_BANDS = frozenset({*(f"{lo}-{lo + 4}" for lo in range(0, 116, 5)), "90+"})
YEARS = range(1900, 2101)
SCORE_KEYS = frozenset({"n_scored", "n_missed", "within_interval_rate", "nominal_level", "mean_abs_error",
                        "beat_persistence_rate", "direction_accuracy"})
Check = Callable[[Any, str], list[dict[str, str]]]


def number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) <= MAX_NUMBER  # False for NaN, inf


def _num(v: Any, at: str) -> list[dict[str, str]]:
    return [] if number(v) else [flag(at, "bad_number")]


def _year(v: Any, at: str) -> list[dict[str, str]]:
    return [] if number(v) and isinstance(v, int) and v in YEARS else [flag(at, "bad_number")]


def _positive(v: Any, at: str) -> list[dict[str, str]]:
    return [] if number(v) and v > 0 else [flag(at, "bad_number")]


def _count(v: Any, at: str) -> list[dict[str, str]]:
    """How many values a mean covers: an integer of at least 1."""
    return [] if isinstance(v, int) and not isinstance(v, bool) and v >= 1 else [flag(at, "bad_number")]


def _rate(v: Any, at: str) -> list[dict[str, str]]:
    return [] if v is None else _num(v, at)


def _code(v: Any, at: str) -> list[dict[str, str]]:
    """Exactly {system, code}, a valid code of its system."""
    ok = isinstance(v, dict) and set(v) == {"system", "code"} and codes.valid(v["system"], v["code"])
    return [] if ok else [flag(at, "bad_code")]


def check_match(pattern: re.Pattern[str], rule: str, v: Any, at: str) -> list[dict[str, str]]:
    """`rule` at `at` unless `v` is a string all in `pattern`."""
    return [] if isinstance(v, str) and pattern.fullmatch(v) else [flag(at, rule)]


def _one_of(allowed: frozenset[str], v: Any, at: str) -> list[dict[str, str]]:
    return [] if isinstance(v, str) and v in allowed else [flag(at, "bad_format")]


def _each(check: Check, v: Any, at: str) -> list[dict[str, str]]:
    if not isinstance(v, list):
        return [flag(at, "bad_section")]
    return [x for n, item in enumerate(v) for x in check(item, f"{at}[{n}]")]


def _fields(required: set[str], fields: dict[str, Check], v: Any, at: str) -> list[dict[str, str]]:
    """An object of these fields only (`unknown_field`), the required ones present (`missing_field`)."""
    if not isinstance(v, dict):
        return [flag(at, "bad_section")]
    out = [flag(f"{at}.{k}", "missing_field") for k in sorted(required - set(v))]
    for n, (k, item) in enumerate(v.items()):
        out += fields[k](item, f"{at}.{k}") if k in fields else [flag(f"{at}.#unknown[{n}]", "unknown_field")]
    return out


def _keyed(check: Check, v: Any, at: str) -> list[dict[str, str]]:
    """An object keyed by identifiers (`bad_id`), each key shown as `#key[<n>]`, each value checked."""
    if not isinstance(v, dict):
        return [flag(at, "bad_section")]
    out = []
    for n, (k, item) in enumerate(v.items()):
        sub = f"{at}.#key[{n}]"
        out += ([] if isinstance(k, str) and ID.fullmatch(k) else [flag(sub, "bad_id")]) + check(item, sub)
    return out


def _closed(values: type) -> Check:
    return partial(_one_of, frozenset(values))


_id = partial(check_match, ID, "bad_id")
_month = partial(check_match, MONTH, "bad_format")
_unit = partial(check_match, UNIT, "bad_format")
POINT = {"t": _month, "value": _num, "n": _count}


def _series(v: Any, at: str) -> list[dict[str, str]]:
    """Points of {t, value}, at most one per month: a month is the finest grain a package carries."""
    out = _each(partial(_fields, {"t", "value"}, POINT), v, at)
    months = [p.get("t") for p in v if isinstance(p, dict)] if isinstance(v, list) else []
    return out + [flag(f"{at}[{n}]", "repeat_month") for n, m in enumerate(months) if m in months[:n]]


SUMMARY = dict.fromkeys(SCORE_KEYS, _rate)
DOSE = {"value": _positive, "unit": _unit}
ITEM = {"code": _code, "clinical_status": _closed(ClinicalStatus), "dose": partial(_fields, {"value", "unit"}, DOSE)}
COORDINATE = {"status": _closed(ValueStatus), "value": _num, "unit": _unit, "comparator": _closed(Comparator),
              "observed": _month, "series": _series, "items": partial(_each, partial(_fields, {"code"}, ITEM))}
STATE = {"map_id": _id, "map_version": partial(check_match, MAP_VERSION, "bad_format"),
         "map_hash": partial(check_match, HEX64, "bad_format"), "as_of": _month, "gaps": partial(_each, _id),
         "coordinates": partial(_keyed, partial(_fields, set(), COORDINATE))}
EVENT = {"kind": _id, "year": _year, "until": _year, "basis": _id, "code": _code, "value": _num, "unit": _unit,
         "clinical_status": ITEM["clinical_status"], "dose": ITEM["dose"]}
SCORES = {"overall": partial(_fields, set(), SUMMARY), "by_coordinate": partial(_keyed, partial(_fields, set(), SUMMARY))}
SUBJECT = {"sex": _closed(Sex), "age_band": partial(_one_of, AGE_BANDS), "ethnicity": _closed(Ethnicity)}
SECTIONS = {ContributionKind.STATES: partial(_each, partial(_fields, {"map_id", "coordinates"}, STATE)),
            ContributionKind.LIFE_EVENTS: partial(_each, partial(_fields, {"kind", "year", "basis", "code"}, EVENT)),
            ContributionKind.SCORES: partial(_fields, set(), SCORES)}
# every field name above: the only key text a path shows
NAMES = frozenset({"system", *(k for fields in (POINT, SUMMARY, DOSE, ITEM, COORDINATE, STATE, EVENT, SCORES, SUBJECT)
                               for k in fields)})


def code_objects(doc: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    """{path: (system, code)} of every code object (a dict) of the set items and life events."""
    found = {f"states[{n}].coordinates.#key[{c}].items[{j}].code": keyed(item).get("code")
             for n, state in enumerate(listed(doc.get("states")))
             for c, value in enumerate(keyed(keyed(state).get("coordinates")).values())
             for j, item in enumerate(listed(keyed(value).get("items")))}
    found |= {f"life_events[{n}].code": keyed(e).get("code") for n, e in enumerate(listed(doc.get("life_events")))}
    return {at: (code.get("system"), code.get("code")) for at, code in found.items() if isinstance(code, dict)}


def violations(doc: dict[str, Any]) -> list[dict[str, str]]:
    """Everything wrong with a contribution's own fields and sections beyond the string rules (plsi.mothership.scan)."""
    out = []
    kinds = doc.get("kinds")
    if not isinstance(kinds, list) or not all(isinstance(k, str) and k in tuple(ContributionKind) for k in kinds):
        out.append(flag("kinds", "unknown_kind"))
    else:
        out += [flag(s, "not_in_kinds") for s in ContributionKind if s in doc and s not in kinds]
    checks = {"packed": _month, "consent_version": partial(check_match, CONSENT_VERSION, "bad_format"),
              "subject": partial(_fields, set(), SUBJECT), **SECTIONS}
    return out + [x for field, check in checks.items() if field in doc for x in check(doc[field], field)]
