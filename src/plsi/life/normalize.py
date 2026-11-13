"""Code and unit normalization (`normalize observations`): LOINC via NLM Clinical Tables, RxNorm via plsi.rxnav,
units via a local UCUM alias table."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from plsi import net, references, rxnav
from plsi.codes import PATTERNS
from plsi.life.importers import observation_items
from plsi.life.models import ObservationInput
from plsi.models import Code, parse
from plsi.files import atomic_write_json, load_json
from plsi.paths import MAPS_DIR
from plsi.vocab import CodeSystem, ObservationKind

MAX_AMBIGUOUS_CANDIDATES = 5
LOINC_MAX_LIST = 200  # LOINC search hits ranked per label

# ---------------------------------------------------------------- units

# Whole spellings, lower-cased and space-free -> UCUM. IU/L stays U/L, as labs print enzyme activity.
_UNIT_ALIASES = {
    "k/ul": "10*3/uL", "thou/ul": "10*3/uL", "m/ul": "10*6/uL", "mill/ul": "10*6/uL",
    "u/l": "U/L", "iu/l": "U/L", "fl": "fL", "%": "%", "percent": "%", "pct": "%",
    "mmhg": "mm[Hg]", "kg/m2": "kg/m2", "kg/m^2": "kg/m2", "bpm": "/min", "beats/min": "/min",
    "uiu/ml": "u[IU]/mL", "miu/l": "m[IU]/L", "miu/ml": "m[IU]/mL",
    "mg%": "mg/dL", "g%": "g/dL",  # per 100 mL, as older and some national reports print it
}
# whole spellings whose case carries the meaning: German G/l (giga, 10^9 per litre) and T/l (tera), never grams
_CASE_ALIASES = {"G/l": "10*9/L", "G/L": "10*9/L", "T/l": "10*12/L", "T/L": "10*12/L",
                 "Gpt/l": "10*9/L", "Gpt/L": "10*9/L", "Tpt/l": "10*12/L", "Tpt/L": "10*12/L"}
# a label printed with the unit that names the method, not the quantity: "% (NGSP)" is %
_ANNOTATION_RE = re.compile(r"\((?:NGSP|DCCT)\)", re.I)
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
_GLYPHS = {"\u00b5": "u", "\u03bc": "u", "\u00d7": "x"}
_SUPERSCRIPT = dict(zip("\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079", "0123456789"))


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
    "ug/mL"; "mEq/L" -> "meq/L"; "kg/m²" -> "kg/m2"; "Thousand per microliter" -> "10*3/uL". A string with no
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


_PROPERTY_FAMILIES = {
    "MCnc": {"mass"}, "SCnc": {"molar"}, "MSCnc": {"mass", "molar"}, "NCnc": {"count"}, "CCnc": {"catalytic"},
    "ACnc": {"iu"}, "NFr": {"fraction"}, "MFr": {"fraction"}, "VFr": {"fraction"}, "SFr": {"fraction"},
}

# ---------------------------------------------------------------- LOINC

_SPECIMEN_RE = re.compile(r"\bin ([A-Z].*?)(?: by |\s--|$)")  # LOINC system names are capitalized
# no specimen printed: a routine draw (serum, plasma or venous blood) before a dried spot, urine or a capillary stick
_ROUTINE_SPECIMENS = frozenset({"Serum or Plasma", "Serum", "Plasma", "Blood", "Venous blood", "Serum, Plasma or Blood", None})
_DROP_RE = re.compile(r"^deprecated\b|\s--|challenge|\b\d+\s*hours?\b", re.I)  # deprecated, timed, challenge


def shipped_coordinates(map_id: str | None = None) -> list[dict[str, Any]]:
    """The raw coordinates of the shipped maps (of one map when `map_id` is given), read as YAML: plsi.life never
    imports plsi.map."""
    found = sorted(MAPS_DIR.glob("*.yaml")) if map_id is None else [MAPS_DIR / f"{map_id}.yaml"]
    return [c for path in found for c in (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("coordinates") or []]


def _map_codes() -> tuple[set[str], set[str]]:
    """(accepted, rejected) LOINC codes across shipped maps. A code accepted anywhere is never treated as rejected."""
    accepted: set[str] = set()
    rejected: set[str] = set()
    for coord in shipped_coordinates():
        accepts = coord.get("accepts") or {}
        for key, into in (("codes", accepted), ("reject_codes", rejected)):
            into |= {str(c["code"]) for c in accepts.get(key) or [] if c.get("system") == CodeSystem.LOINC}
    return accepted, rejected - accepted


# words a printed test name adds that do not name another analyte
_DESCRIPTORS = frozenset({"total", "serum", "plasma", "blood", "whole", "venous", "capillary", "fasting", "fasted",
                          "random", "level", "levels", "test", "calc", "calculated", "direct", "measured", "s", "p", "b",
                          "hs", "high", "sensitivity", "sensitive", "ultrasensitive", "3rd", "gen", "generation", "of",
                          "the", "in", "c", "count", "conc", "concentration", "ngsp", "ifcc", "dcct"})


def _words(text: str) -> set[str]:
    folded = text.lower().replace("ae", "e").replace("oe", "e")  # haemoglobin, oestradiol
    return set(re.findall(r"[a-z0-9]+", folded))


# the specimen a name or a LOINC system names, by class: a urine result is never a blood result
_SPECIMEN_WORDS = {
    "urine": {"urine", "urin", "harn", "u", "моча", "мочи", "мочевой", "моче"},
    "csf": {"csf", "liquor", "cerebral", "spinal", "cerebrospinal", "ликвор"},
    "saliva": {"saliva", "speichel", "слюна", "слюны"},
    "stool": {"stool", "feces", "faeces", "stuhl", "кал", "кала"},
    "dbs": {"dbs", "dried"},
    "isf": {"interstitial", "isf", "cgm", "sensor"},
    "blood": {"serum", "plasma", "blood", "venous", "capillary", "vollblut", "кровь", "крови", "сыворотка", "плазма"},
}
_FASTING_WORDS = frozenset({"fasting", "fasted", "fast", "nuchtern", "nuechtern", "натощак"})


def specimen_class(text: str | None) -> str | None:
    """The specimen class a printed name, a printed specimen or a LOINC system names: urine, csf, saliva, stool,
    dbs or blood; None when it names none. A dried spot outranks blood ("Blood in DBS" is dbs)."""
    words = set(re.findall(r"\w+", (text or "").lower()))
    found = [k for k, ws in _SPECIMEN_WORDS.items() if words & ws]
    return found[0] if found else None


def same_analyte(printed: str, component: str, short: str, display: str) -> bool:
    """A LOINC candidate names the analyte the report printed: its component's words (before any ^ timing or /
    denominator) are all in the printed name, or its short name's analyte is; and every other printed word is a
    descriptor or appears in the candidate's name. "Total cholesterol" is Cholesterol, never Cholesterol in LDL."""
    words, compact = _words(printed), re.sub(r"[^a-z0-9]", "", printed.lower())
    analyte = _words(re.split(r"[\^/]", component, maxsplit=1)[0]) - {"in"}
    head = next(iter(re.findall(r"[a-z0-9]+", short.lower())), "")
    named = bool(analyte) and analyte <= words or bool(head) and (head in words or compact.startswith(head))
    rest = words - _DESCRIPTORS - analyte - {head} - set().union(*_SPECIMEN_WORDS.values())
    timing = component.split("^", 1)[1].lower() if "^" in component else ""
    # a timed code (fasting, after a dose) only for a name that prints the timing
    timed = (not timing or "fst" in timing and bool(set(re.findall(r"\w+", printed.lower())) & _FASTING_WORDS)
             or "fst" not in timing and bool(re.search(r"(?:post|after|\d+\s*h)", printed.lower())))
    return named and timed and rest <= _words(display) | _words(short)


def loinc_search_url() -> str:
    """The NLM Clinical Tables LOINC search endpoint (also used by `plsi maps validate --live`)."""
    return references.api_base("nlm_clinical_tables_loinc") + "/api/loinc_items/v3/search"


def loinc_candidates(text: str, unit: str | None = None, specimen: str | None = None) -> list[dict[str, Any]]:
    """Ranked LOINC candidates for a lab label (network).

    Drops deprecated, timed and challenge codes, any shipped-map reject_code and any code of another specimen class
    than the one printed (`specimen`, or named in `text`: urine, csf, saliva, stool, dbs, blood). Rank: shipped-map accepted codes
    first, then unit/property compatibility (convertible counts as compatible), then specimen match, then API order.
    Returns [{code, display, specimen, property, units, map_accepted, compatible}].
    """
    reply = net.get_json(loinc_search_url(), {"terms": text, "type": "question", "maxList": LOINC_MAX_LIST,
                                              "df": "LOINC_NUM,LONG_COMMON_NAME", "ef": "PROPERTY,units,COMPONENT,SHORTNAME"})
    codes, extra, display = reply[1] or [], reply[2] or {}, reply[3] or []
    accepted, rejected = _map_codes()
    obs_family = _family(unit)
    printed_class = specimen_class(specimen) or specimen_class(text)
    ranked = []
    for i, code in enumerate(codes):
        name = display[i][1] if i < len(display) else ""
        if code in rejected or not PATTERNS[CodeSystem.LOINC].fullmatch(code) or (code not in accepted and _DROP_RE.search(name)):
            continue
        prop = (extra.get("PROPERTY") or [None] * len(codes))[i]
        units = [u["unit"] for u in (extra.get("units") or [None] * len(codes))[i] or [] if u.get("unit")]
        spec = m[1] if (m := _SPECIMEN_RE.search(name)) else None
        if specimen_class(spec) not in ((printed_class,) if printed_class != "blood" and printed_class else ("blood", None)):
            continue  # another specimen: urine glucose never gets a blood code; unprinted means a routine blood draw
        families = {_family(u) for u in units} | _PROPERTY_FAMILIES.get(prop or "", set())
        compatible = obs_family is None or obs_family in families  # no reported unit: nothing to contradict
        spec_match = bool(spec and specimen.lower() in spec.lower()) if specimen else spec in _ROUTINE_SPECIMENS
        component = (extra.get("COMPONENT") or [None] * len(codes))[i] or ""
        short = (extra.get("SHORTNAME") or [None] * len(codes))[i] or ""
        analyte = same_analyte(text, component, short, name)
        ranked.append(((code not in accepted, not compatible, not analyte, not spec_match, i), {
            "code": code, "display": name, "specimen": spec, "property": prop, "units": units,
            "map_accepted": code in accepted, "compatible": compatible,
            "same_analyte": analyte,
        }))
    return [c for _, c in sorted(ranked, key=lambda r: r[0])]


# ---------------------------------------------------------------- RxNorm

def _rxnorm_groups(text: str) -> list[list[Code]]:
    """Ingredients per approximateTerm candidate (deduped by rxcui, best first)."""
    return [[Code(system=CodeSystem.RXNORM, code=p["rxcui"], display=p.get("name")) for p in rxnav.ingredients(rxcui).get("IN", [])]
            for rxcui in rxnav.candidates(text)]


def _flatten(groups: list[list[Code]]) -> list[Code]:
    out: dict[str, Code] = {}
    for c in (c for g in groups for c in g):
        out.setdefault(c.code, c)
    return list(out.values())


def normalize_observations(in_path: str, out_path: str) -> dict[str, Any]:
    """`plsi normalize observations --in F --out F` (network).

    Uncoded measurements get LOINC (auto-pick only when the top candidate is map-accepted, compatible AND names the
    printed analyte, `same_analyte`);
    uncoded medications get the RxNorm ingredient when the best match resolves to exactly one. Others pass through.
    Returns {out, counts: {total, coded, ambiguous, unchanged}, ambiguous: [{index, original_text, candidates}]}.
    """
    observations = [parse(ObservationInput, item, f"observation {i}") for i, item in enumerate(observation_items(load_json(in_path)))]
    out, ambiguous, coded = [], [], 0
    for i, obs in enumerate(observations):
        code, candidates = None, None
        if obs.code is None and obs.kind == ObservationKind.MEASUREMENT:
            ranked = loinc_candidates(obs.original_text, obs.unit, obs.specimen)
            if ranked and ranked[0]["map_accepted"] and ranked[0]["compatible"] and ranked[0]["same_analyte"]:
                code = Code(system=CodeSystem.LOINC, code=ranked[0]["code"], display=ranked[0]["display"])
            else:
                candidates = ranked[:MAX_AMBIGUOUS_CANDIDATES]
        elif obs.code is None and obs.kind == ObservationKind.MEDICATION:
            groups = _rxnorm_groups(obs.original_text)
            if groups and len(groups[0]) == 1:
                code = groups[0][0]
            else:
                candidates = [c.dump() for c in _flatten(groups)[:MAX_AMBIGUOUS_CANDIDATES]]
        if code is not None:
            obs, coded = obs.model_copy(update={"code": code}), coded + 1
        elif candidates is not None:
            ambiguous.append({"index": i, "original_text": obs.original_text, "candidates": candidates})
        out.append(parse(ObservationInput, obs.dump()).dump())
    target = Path(out_path).resolve()
    atomic_write_json(target, out)
    return {
        "out": str(target),
        "counts": {"total": len(out), "coded": coded, "ambiguous": len(ambiguous), "unchanged": len(out) - coded - len(ambiguous)},
        "ambiguous": ambiguous,
    }
