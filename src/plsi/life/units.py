"""UCUM unit normalization (`normalize_unit`): a reported unit string to UCUM spelling via a local alias table, with no
network and no change of quantity. Dimension families group units that are inter-convertible by generic scaling."""

from __future__ import annotations

import re

# Whole spellings, lower-cased and space-free -> UCUM. IU/L stays U/L, as labs print enzyme activity.
_UNIT_ALIASES = {
    "k/ul": "10*3/uL", "thou/ul": "10*3/uL", "m/ul": "10*6/uL", "mill/ul": "10*6/uL",
    "u/l": "U/L", "iu/l": "U/L", "fl": "fL", "%": "%", "percent": "%", "pct": "%",
    "mmhg": "mm[Hg]", "kg/m2": "kg/m2", "kg/m^2": "kg/m2", "bpm": "/min", "beats/min": "/min",
    "uiu/ml": "u[IU]/mL", "miu/l": "m[IU]/L", "miu/ml": "m[IU]/mL",
    "mg%": "mg/dL", "g%": "g/dL",  # per 100 mL, as older and some national reports print it
    "%oftotalhgb": "%", "%oftotalhb": "%",  # HbA1c as US labs print it
    # eGFR per 1.73 m2 of body surface, with or without the m2 printed
    "ml/min/1.73": "mL/min/{1.73_m2}", "ml/min/1.73m2": "mL/min/{1.73_m2}", "ml/min/1.73sqm": "mL/min/{1.73_m2}",
    "ml/min/{1.73_m2}": "mL/min/{1.73_m2}",
}
# whole spellings whose case carries the meaning: German G/l (giga, 10^9 per litre) and T/l (tera), never grams
_CASE_ALIASES = {"G/l": "10*9/L", "G/L": "10*9/L", "T/l": "10*12/L", "T/L": "10*12/L",
                 "Gpt/l": "10*9/L", "Gpt/L": "10*9/L", "Tpt/l": "10*12/L", "Tpt/L": "10*12/L"}
# a label printed with the unit that names the method, not the quantity: "% (NGSP)" is %, "mg/dL (calc)" is mg/dL;
# a trailing bracket of words only, so "U/L (37C)" keeps its temperature
_ANNOTATION_RE = re.compile(r"\((?:NGSP|DCCT)\)|\s*\([A-Za-z][A-Za-z .-]*\)\s*$", re.I)
# spelled-out words, before the spaces go: "per" is a slash, "cubic millimeter" is mm3, "cells"/"beats" name a count
_PHRASES = ((re.compile(r"\s*\bper\b\s*", re.I), "/"), (re.compile(r"\bcubic\s+millimet(?:er|re)s?\b", re.I), "mm3"),
            (re.compile(r"\b(?:cells?|beats?)\b", re.I), ""))
# one token -> UCUM: alternative spellings of a prefix and base; spelling only, never a change of quantity
_TOKEN_WORDS = {
    "mcg": "ug", "mcmol": "umol", "mcl": "uL", "gm": "g",
    "micromol": "umol", "millimol": "mmol", "nanomol": "nmol", "picomol": "pmol",
    "um3": "fL", "mm3": "uL", "cumm": "uL", "cells": "", "cell": "", "k": "10*3", "thous": "10*3",
    "tsd": "10*3", "mio": "10*6", "mrd": "10*9", "thousand": "10*3", "thousands": "10*3", "million": "10*6", "millions": "10*6",
    "billion": "10*9", "billions": "10*9", "microliter": "uL", "microlitre": "uL", "microliters": "uL",
    "microlitres": "uL", "milliliter": "mL", "millilitre": "mL", "deciliter": "dL", "decilitre": "dL", "liter": "L",
    "litre": "L",
    # Cyrillic, as Russian-language reports print units
    "ммоль": "mmol", "мкмоль": "umol", "нмоль": "nmol", "пмоль": "pmol", "моль": "mol", "кг": "kg", "г": "g",
    "мг": "mg", "мкг": "ug", "нг": "ng", "пг": "pg", "л": "L", "дл": "dL", "мл": "mL", "мкл": "uL", "нл": "nL",
    "фл": "fL", "ед": "U", "мед": "mU", "ме": "[IU]", "мме": "m[IU]", "мкме": "u[IU]", "тыс": "10*3", "млн": "10*6",
    "клеток": "", "кл": "",
    # time, as reports, apps and wearables print it
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s", "ms": "ms", "msec": "ms",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min", "h": "h", "hr": "h", "hrs": "h", "hour": "h",
    "hours": "h", "std": "h", "d": "d", "day": "d", "days": "d", "wk": "wk", "week": "wk", "weeks": "wk",
    "mo": "mo", "month": "mo", "months": "mo", "a": "a", "y": "a", "yr": "a", "yrs": "a", "year": "a", "years": "a",
    "сек": "s", "с": "s", "мс": "ms", "мин": "min", "ч": "h", "час": "h", "часа": "h", "часов": "h", "дн": "d",
    "день": "d", "дней": "d", "нед": "wk", "мес": "mo", "год": "a", "лет": "a",
}
UNIT_PREFIXES = {"": 1.0, "k": 1e3, "d": 1e-1, "c": 1e-2, "m": 1e-3, "u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}
_BASES = (("[iu]", "[IU]"), ("iu", "[IU]"), ("mol", "mol"), ("kat", "kat"), ("eq", "eq"), ("g", "g"), ("l", "L"),
          ("u", "U"))
UNIT_BASES = tuple(dict.fromkeys(base for _, base in _BASES))
_POWER_RE = re.compile(r"x?10(?:\^|\*\*?|e)(\d+)")
_GLYPHS = {"µ": "u", "μ": "u", "×": "x"}
_SUPERSCRIPT = dict(zip("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))


def _token(t: str) -> str | None:
    """One token in UCUM spelling (dl -> dL, MMOL -> mmol, mIU -> m[IU], x10^9 -> 10*9), or None if it is not one."""
    low = t.lower()
    if low in _TOKEN_WORDS:
        return _TOKEN_WORDS[low]
    if m := _POWER_RE.fullmatch(low):
        return f"10*{m[1]}"
    for spelled, base in _BASES:
        if low.endswith(spelled) and low[: -len(spelled)] in UNIT_PREFIXES:
            return low[: -len(spelled)] + base
    return None


def normalize_unit(unit: str | None) -> str | None:
    """UCUM spelling of a reported unit string (no network, no value change): whitespace, case, micro signs,
    superscripts and power-of-ten forms. "K/uL", "x10E3/uL", "×10³/µL" -> "10*3/uL"; "MG/DL" -> "mg/dL"; "mcg/mL" ->
    "ug/mL"; "mEq/L" -> "meq/L"; "kg/m²" -> "kg/m2"; "Thousand per microliter" -> "10*3/uL"; "mg/dL (calc)" -> "mg/dL"; "% of total Hgb" -> "%"; "mL/min/1.73" ->
    "mL/min/{1.73_m2}". A string with no
    token it knows is returned stripped and unchanged; None or blank -> None. The one normalizer: ingest and the maps' conversions both use it."""
    if unit is None or not unit.strip():
        return None
    raw = unit.strip().rstrip(".*").strip()  # a full stop or the lab's flag asterisk printed after the unit
    u = "".join(_GLYPHS.get(ch, ch) for ch in raw)
    u = re.sub("[" + "".join(_SUPERSCRIPT) + "]+", lambda m: "^" + "".join(_SUPERSCRIPT[c] for c in m.group()), u)
    for pattern, spelled in _PHRASES:
        u = pattern.sub(spelled, u)
    u = re.sub(r"(?<!10)\^([23])(?!\d)", r"\1", re.sub(r"\s+", "", _ANNOTATION_RE.sub("", u)))  # m^2 -> m2
    if u in _CASE_ALIASES:
        return _CASE_ALIASES[u]
    if u.lower() in _UNIT_ALIASES:
        return _UNIT_ALIASES[u.lower()]
    tokens = [(t, _token(t)) for t in u.split("/")]
    if not any(known is not None for _, known in tokens):
        return raw
    return "/".join(t if known is None else known for t, known in tokens)


def known_unit(unit: str | None) -> bool:
    """`unit` is a form the table above produces: an alias target, a count (10*3/uL) or a concentration (mg/dL)."""
    return bool(unit) and (unit in _UNIT_ALIASES.values()
                           or bool(re.fullmatch(r"10\*\d+/u?L|[kmunp]?(g|mol|eq)(/[dmu]?L)?", unit)))


def _family(unit: str | None) -> str | None:
    """Dimension family of a unit; units in one family are inter-convertible by generic scaling."""
    u = normalize_unit(unit)
    if u is None:
        return None
    if u in ("%", "1"):
        return "fraction"
    if re.fullmatch(r"(10\*\d+)?/[mu]?L", u):
        return "count"
    if m := re.fullmatch(r"[kmunp]?(g|mol|eq)/[dmu]?L", u):
        return "mass" if m[1] == "g" else "molar"
    if re.fullmatch(r"[kmu]?U/[dmu]?L", u):
        return "catalytic"
    if "[IU]/" in u:
        return "iu"
    return u
