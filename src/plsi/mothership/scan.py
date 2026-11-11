"""The rules every string and number of a Mothership message passes, as on the Mother's side (WIRE §3, §4): strict
parsing, nesting depth, NFKC with format characters removed, lengths, the identifying patterns outside their exempt
paths, forbidden keys and bounded numbers. Paths show only wire field names, indexes, `#key[<n>]` and `#unknown[<n>]`."""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable, Iterable, Iterator
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
UUID_LOWER = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")  # as the Mother's project ids
UUID_ANY = re.compile(UUID_LOWER.pattern, re.I)
# a long base64 run mixing cases and digits (sequences and hex hashes do not)
BASE64_RUN = r"(?<![A-Za-z0-9+/])(?=[A-Za-z0-9+/]*[a-z])(?=[A-Za-z0-9+/]*[A-Z])(?=[A-Za-z0-9+/]*[0-9])[A-Za-z0-9+/]{120,}"
_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
_MONTH = rf"(?:{_MONTHS})[a-z]*\.?"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_TLDS = "com|org|net|io|ai|co|me|info|biz|ru|cn|uk|de|xyz|app|dev|link|ly|gl"
PATTERNS = {
    "exact_date": re.compile(rf"\b\d{{4}}-\d{{2}}-\d{{2}}|\b\d{{4}}[./-]\d{{1,2}}[./-]\d{{1,2}}\b"
                             rf"|(?<![\d.])\d{{1,2}}([./-])\d{{1,2}}\1(?:\d{{4}}|\d{{2}})(?!\d|\.\d)"
                             rf"|{_DAY}\s+{_MONTH}\s+\d{{2,4}}|\b{_MONTH}\s+{_DAY},?\s+\d{{2,4}}"
                             rf"|\d{{1,2}}[- ]{_MONTH}[- ]\d{{2,4}}", re.I),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "url": re.compile(rf"\bhttps?://|\bwww\.|(?<![\w-])[\w-]+\.(?:{_TLDS})\b", re.I),
    "id_number": re.compile(r"\d[\d\s().-]{6,}\d"),
    "internal_id": re.compile(r"\b(?:s_[0-9a-f]{12}|evt_[0-9a-f]{8,32})\b"),
    "embedded_data": re.compile(r"(?i:\bdata:[a-z]+/[\w.+-]+;base64)|" + BASE64_RUN),  # a data: URI or a base64 run
}
# a cheap test every match of the rule contains, so the backtracking bare-domain pattern runs only where it can match
NEEDS = {"url": re.compile(rf"https?://|www\.|\.(?:{_TLDS})\b", re.I)}
YEARS = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")  # removed before the id-number rule: year ranges are allowed
FORBIDDEN_KEYS = frozenset({"subject_id", "instance", "birth_year", "event_id", "event_ids", "path", "original_path",
                            "install_id"})
KEYED = frozenset({"states[].coordinates", "scores.by_coordinate"})  # objects keyed by coordinate ids
Exempt = Callable[[str, str, str], bool]  # (rule, path template, shown path) -> exempt
Mask = Callable[[str, str], str]  # (rule, text) -> the text as that rule reads it


def flag(path: str, rule: str) -> dict[str, str]:
    return {"path": path, "rule": rule}


def name(key: Any, n: int, names: frozenset[str], at: str = "") -> str:
    """The shown path of the key at position n of the object at `at`: its name when a wire field, else `#unknown[n]`."""
    shown = key if isinstance(key, str) and key in names else f"#unknown[{n}]"
    return f"{at}.{shown}" if at else shown


def normal(text: str) -> str:
    """NFKC with Unicode format characters (category Cf, e.g. zero-width space) removed: what the rules read."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf")


def _read(rule: str, text: str) -> str:
    """The text as an identifying-pattern rule reads it: the id-number rule with years removed."""
    return YEARS.sub(" ", text) if rule == "id_number" else text


def hit(rule: str, text: str) -> bool:
    """`text` breaks the identifying-pattern rule."""
    if rule in NEEDS and not NEEDS[rule].search(text):
        return False
    return bool(PATTERNS[rule].search(_read(rule, text)))


def _names(instances: set[str]) -> re.Pattern[str]:
    """Any of the (lower-case) instance names as a whole word."""
    return re.compile("|".join(rf"\b{re.escape(n)}\b" for n in instances))


def named(text: str, instances: set[str]) -> bool:
    """`text` names one of the instances as a whole word, in any case."""
    return bool(instances) and bool(_names(instances).search(text.lower()))


def broken(text: str, instances: set[str], rules: Iterable[str] = PATTERNS, mask: Mask | None = None) -> list[str]:
    """The identifying-pattern `rules` (each reading `text` as `mask` shows it) and `instance_name` that `text` breaks."""
    found = [rule for rule in rules if hit(rule, mask(rule, text) if mask else text)]
    return found + (["instance_name"] if named(text, instances) else [])


def listed(value: Any) -> list[Any]:  # reading a document whose shape is checked elsewhere
    return value if isinstance(value, list) else []


def keyed(value: Any) -> dict[Any, Any]:  # as listed, for an object
    return value if isinstance(value, dict) else {}


# a data: picture (markdown or HTML), a data: URI with its payload, or a bare base64 run
PICTURE = re.compile(r"(?i:!\[[^\]\n]*\]\(\s*data:[^)]*\)|<img\b[^>]*\bdata:[^>]*>|\bdata:[a-z]+/[\w.+-]+;base64,?"
                     r"[A-Za-z0-9+/=]*)|" + BASE64_RUN + "={0,2}")
REMOVED = "[picture removed]"


def strip_pictures(obj: Any) -> tuple[Any, int]:
    """`obj` with hidden pictures replaced by REMOVED, and their count; a hit string is cleaned in its normal form."""
    if isinstance(obj, dict):
        parts = [(k, *strip_pictures(v)) for k, v in obj.items()]
        return {k: v for k, v, _ in parts}, sum(n for *_, n in parts)
    if isinstance(obj, list):
        parts = [strip_pictures(v) for v in obj]
        return [v for v, _ in parts], sum(n for _, n in parts)
    if not isinstance(obj, str) or not hit("embedded_data", normal(obj)):
        return obj, 0
    return PICTURE.subn(REMOVED, normal(obj))


class _Duplicate(ValueError):
    pass


def _unique(items: list[tuple[str, Any]]) -> dict[str, Any]:
    if len({k for k, _ in items}) != len(items):
        raise _Duplicate
    return dict(items)


def _constant(name: str) -> Any:
    raise ValueError("non-finite number")


def load(file: str | Path) -> Any:
    """A message file parsed strictly: NaN/Infinity -> not_json, a repeated key -> duplicate_key (path `$`)."""
    text = files.read_input_text(file)
    try:
        return json.loads(text, parse_constant=_constant, object_pairs_hook=_unique)
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


def walk(obj: Any, names: frozenset[str] = frozenset(), shown: str = "",
         plain: str = "") -> Iterator[tuple[str, str, Any, bool]]:
    """(shown path, path template, value, is_key) for every dict key, string and number, paths showing only `names`.
    Templates write `[]` for any index and `*` for any coordinate key."""
    if isinstance(obj, dict):
        for n, (k, v) in enumerate(obj.items()):
            sub, tmpl = (f"#key[{n}]", "*") if plain in KEYED else (name(k, n, names),) * 2
            sub, tmpl = (f"{shown}.{sub}", f"{plain}.{tmpl}") if shown else (sub, tmpl)
            if isinstance(k, str):
                yield sub, tmpl, k, True
            yield from walk(v, names, sub, tmpl)
    elif isinstance(obj, list):
        for n, v in enumerate(obj):
            yield from walk(v, names, f"{shown}[{n}]", f"{plain}[]")
    elif isinstance(obj, (str, int, float)) and not isinstance(obj, bool):
        yield shown, plain, obj, False


def pairs(obj: Any) -> list[tuple[str, Any]]:
    if isinstance(obj, dict):
        return [p for k, v in obj.items() for p in ((k, v), *pairs(v))]
    return [p for v in obj for p in pairs(v)] if isinstance(obj, list) else []


def lines(pattern: re.Pattern[str], text: str) -> list[int]:
    """The 1-based lines where a match of `pattern` starts, each once."""
    return list(dict.fromkeys(text.count("\n", 0, m.start()) + 1 for m in pattern.finditer(text)))


def _lined(path: str, text: str, mask: Mask, instances: set[str]) -> list[dict[str, str]]:
    """The identifying-pattern and instance-name rules over a masked field: one violation per line and rule, its path
    `<path>[<line>]`."""
    out = []
    for rule, pattern in PATTERNS.items():
        seen = mask(rule, text)
        if rule not in NEEDS or NEEDS[rule].search(seen):
            out += [flag(f"{path}[{n}]", rule) for n in lines(pattern, _read(rule, seen))]
    if instances:
        out += [flag(f"{path}[{n}]", "instance_name") for n in lines(_names(instances), text.lower())]
    return out


def violations(doc: Any, exempt: Exempt, names: frozenset[str], instances: set[str],
               limits: dict[str, int] | None = None, masks: dict[str, Mask] | None = None) -> list[dict[str, str]]:
    """The string, key and number rules over the whole document, paths showing only `names`; `instances` are the
    instance names never sent. A field in `masks` (path template -> mask) is read as each rule's mask shows it, and its
    violations name the line (`_lined`); `limits` override MAX_STRING per path template."""
    out = []
    for path, plain, value, is_key in walk(doc, names):
        path = path or "$"
        if not isinstance(value, str):
            if not abs(value) <= MAX_NUMBER:  # NaN, infinities and big numbers; a huge int is never made a float
                out.append(flag(path, "bad_number"))
            continue
        text = normal(value)
        if is_key and text in FORBIDDEN_KEYS:
            out.append(flag(path, "forbidden_field"))
        if len(value) > (MAX_KEY if is_key else (limits or {}).get(plain, MAX_STRING)):
            out.append(flag(path, "too_long"))
            continue
        if masks and plain in masks and not is_key:
            out += [v for v in _lined(path, text, masks[plain], instances) if not exempt(v["rule"], plain, path)]
            continue
        rules = [rule for rule in PATTERNS if is_key or not exempt(rule, plain, path)]
        out += [flag(path, rule) for rule in broken(text, instances, rules)]
    return out
