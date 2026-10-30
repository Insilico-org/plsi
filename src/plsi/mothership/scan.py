"""The rules every string and number of a Mothership message passes, the same on PLSI's side as on the Mother's
(WIRE §3, §4): strict parsing (no NaN or Infinity, no duplicate keys), nesting depth, NFKC normalisation with format
characters removed, lengths, the identifying patterns (exact dates, contacts, URLs, id numbers, internal ids) outside
their exempt paths, forbidden keys, and finite bounded numbers. A violation is {path, rule}: paths show only wire
field names and indexes; a coordinate key is `#key[<n>]` and any other key `#unknown[<n>]` (n = its position)."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import GateFailed

MAX_DEPTH = 32
MAX_STRING = 4000
MAX_KEY = 64
MAX_NUMBER = 1e9
ID = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}")
HEX64 = re.compile(r"[0-9a-f]{64}")
MONTH = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
_MONTH = rf"(?:{_MONTHS})[a-z]*\.?"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_TLDS = "com|org|net|io|ai|co|me|info|biz|ru|cn|uk|de|xyz|app|dev|link|ly|gl"
PATTERNS = {
    "exact_date": re.compile(rf"\b\d{{4}}-\d{{2}}-\d{{2}}|\b\d{{4}}[./-]\d{{1,2}}[./-]\d{{1,2}}\b"
                             rf"|(?<![\d.])\d{{1,2}}([./-])\d{{1,2}}\1(?:\d{{4}}|\d{{2}})(?![\d.])"
                             rf"|{_DAY}\s+{_MONTH}\s+\d{{2,4}}|\b{_MONTH}\s+{_DAY},?\s+\d{{2,4}}"
                             rf"|\d{{1,2}}[- ]{_MONTH}[- ]\d{{2,4}}", re.I),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "url": re.compile(rf"\bhttps?://|\bwww\.|(?<![\w-])[\w-]+\.(?:{_TLDS})\b", re.I),
    "id_number": re.compile(r"\d[\d\s().-]{6,}\d"),
    "internal_id": re.compile(r"\b(?:s_[0-9a-f]{12}|evt_[0-9a-f]{8,32})\b"),
}
# a cheap test every match of the rule contains, so the backtracking bare-domain pattern runs only where it can match
NEEDS = {"url": re.compile(rf"https?://|www\.|\.(?:{_TLDS})\b", re.I)}
YEARS = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")  # removed before the id-number rule: year ranges are allowed
FORBIDDEN_KEYS = frozenset({"subject_id", "instance", "birth_year", "event_id", "event_ids", "path", "original_path",
                            "install_id"})
KEYED = frozenset({"states[].coordinates", "scores.by_coordinate"})  # objects keyed by coordinate ids
Exempt = Callable[[str, str, str], bool]  # (rule, path template, shown path) -> exempt


def flag(path: str, rule: str) -> dict[str, str]:
    return {"path": path, "rule": rule}


def name(key: Any, n: int, names: frozenset[str], at: str = "") -> str:
    """The shown path of the key at position n of the object at `at`: its name when a wire field, else `#unknown[n]`."""
    shown = key if isinstance(key, str) and key in names else f"#unknown[{n}]"
    return f"{at}.{shown}" if at else shown


def normal(text: str) -> str:
    """NFKC with Unicode format characters (category Cf, e.g. zero-width space) removed: what the rules read."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf")


def hit(rule: str, text: str) -> bool:
    """`text` breaks the identifying-pattern rule (the id-number rule reads it with years removed)."""
    if rule in NEEDS and not NEEDS[rule].search(text):
        return False
    return bool(PATTERNS[rule].search(YEARS.sub(" ", text) if rule == "id_number" else text))


class _Duplicate(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len({k for k, _ in pairs}) != len(pairs):
        raise _Duplicate
    return dict(pairs)


def _constant(name: str) -> Any:
    raise ValueError("non-finite number")


def load(file: str | Path) -> Any:
    """A message file parsed strictly: NaN/Infinity -> not_json, a repeated key -> duplicate_key (path `$`)."""
    text = files.read_input_text(file)
    try:
        return json.loads(text, parse_constant=_constant, object_pairs_hook=_pairs)
    except _Duplicate:
        rule = "duplicate_key"
    except RecursionError:
        rule = "too_deep"
    except ValueError:
        rule = "not_json"
    raise GateFailed([flag("$", rule)], "the file is not safe to send")


def too_deep(obj: Any) -> bool:
    """More than MAX_DEPTH nested objects and lists (the top-level object is depth 1); checked before any walk."""
    stack = [(obj, 1)]
    while stack:
        o, d = stack.pop()
        if isinstance(o, (dict, list)):
            if d > MAX_DEPTH:
                return True
            stack += [(v, d + 1) for v in (o.values() if isinstance(o, dict) else o)]
    return False


def _walk(obj: Any, names: frozenset[str], shown: str = "", plain: str = "") -> Iterator[tuple[str, str, Any, bool]]:
    """(shown path, path template, value, is_key) for every dict key, string and number. Templates write `[]` for any
    index and `*` for any coordinate key."""
    if isinstance(obj, dict):
        for n, (k, v) in enumerate(obj.items()):
            sub, tmpl = (f"#key[{n}]", "*") if plain in KEYED else (name(k, n, names),) * 2
            sub, tmpl = (f"{shown}.{sub}", f"{plain}.{tmpl}") if shown else (sub, tmpl)
            if isinstance(k, str):
                yield sub, tmpl, k, True
            yield from _walk(v, names, sub, tmpl)
    elif isinstance(obj, list):
        for n, v in enumerate(obj):
            yield from _walk(v, names, f"{shown}[{n}]", f"{plain}[]")
    elif isinstance(obj, (str, int, float)) and not isinstance(obj, bool):
        yield shown, plain, obj, False


def violations(doc: Any, exempt: Exempt, names: frozenset[str], instances: set[str]) -> list[dict[str, str]]:
    """The string, key and number rules over the whole document, paths showing only `names`; `instances` are the
    instance names never sent."""
    out = []
    for path, plain, value, is_key in _walk(doc, names):
        path = path or "$"
        if not isinstance(value, str):
            if not abs(value) <= MAX_NUMBER:  # NaN, infinities and big numbers; a huge int is never made a float
                out.append(flag(path, "bad_number"))
            continue
        text = normal(value)
        if is_key and text in FORBIDDEN_KEYS:
            out.append(flag(path, "forbidden_field"))
        if len(value) > (MAX_KEY if is_key else MAX_STRING):
            out.append(flag(path, "too_long"))
            continue
        out += [flag(path, rule) for rule in PATTERNS if (is_key or not exempt(rule, plain, path)) and hit(rule, text)]
        if any(re.search(rf"\b{re.escape(n)}\b", text.lower()) for n in instances):
            out.append(flag(path, "instance_name"))
    return out
