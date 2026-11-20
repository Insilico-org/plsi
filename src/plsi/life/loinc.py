"""LOINC candidate resolution (`loinc_candidates`): ranked LOINC codes for a printed lab label via NLM Clinical Tables,
filtered by shipped-map accept/reject lists, specimen class and unit/property compatibility."""

from __future__ import annotations

import re
from typing import Any

import yaml

from plsi import net, references
from plsi.codes import PATTERNS
from plsi.life.units import _family
from plsi.paths import MAPS_DIR
from plsi.vocab import CodeSystem

LOINC_MAX_LIST = 200  # LOINC search hits ranked per label

_PROPERTY_FAMILIES = {
    "MCnc": {"mass"}, "SCnc": {"molar"}, "MSCnc": {"mass", "molar"}, "NCnc": {"count"}, "CCnc": {"catalytic"},
    "ACnc": {"iu"}, "NFr": {"fraction"}, "MFr": {"fraction"}, "VFr": {"fraction"}, "SFr": {"fraction"},
}

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
