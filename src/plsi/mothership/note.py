"""The optional parts of a research note (WIRE §3): item context, the forms its `report` masks, its `files` and the
`project` it serves."""

from __future__ import annotations

import re
from functools import partial
from typing import Any

from plsi.mothership.scan import HEX64, UUID_LOWER, flag
from plsi.vocab import EvidenceClass, SourceKind
from plsi.vocab.targets import AgingHallmark

MAX_TEXT = 300
MAX_TITLE = 120  # a project title (plsi research project)
MAX_REPORT = 40_000
DOI = r"\b10\.\d{4,9}/[A-Za-z0-9._;()/:-]+"
# the forms a `report` masks (WIRE §3), per rule; every other rule sees the report unmasked
CITATION = re.compile(r"(?i:\b(?:pmids?|pubmed)[:\s#]*\d{1,8}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)\d{1,8})*\b"
                      r"|\bNCT\d{8}\b)|" + DOI + r"|\b\d+\.\d+(?:\s*[-\u2013]\s*|\s+to\s+)\d+\.\d+\b"
                      r"|\b\d{1,2}(?:\.\d+)?%\s*CI\b|\bchr(?:2[0-2]|1\d|[1-9]|[XYM]):\d+(?:-\d+)?|\bENS[A-Z]*[GTPE]\d{11}\b"
                      r"|\b[OPQ][0-9][A-Z0-9]{3}[0-9]\b|\brs\d{3,10}\b|\bc[gh]\d{8}\b")
# a statistic, blanked for `id_number` only: a decimal mean with a decimal SD or SEM, 7.4 (0.3) or -0.3 (0.4), alone
# (nothing digit-like before or after), and a p-value, p < 0.05
STATISTIC = re.compile(r"(?<![\d.\-\u2212])[-\u2212]?\b\d{1,3}\.\d{1,2}\s?\(\s?\d{1,3}\.\d{1,2}\s?\)(?!\s?[\d(])"
                       r"|\bp\s?[<>=\u2264\u2265]\s?0?\.\d{1,4}\b")
REPORT_MASKS = {"exact_date": CITATION, "id_number": re.compile(f"{CITATION.pattern}|{STATISTIC.pattern}"),
                "url": re.compile(r"(?i:\b(?:https?://)?doi\.org/)" + DOI)}
MAX_LIST = 10
FINDINGS = ("support", "against", "risks")
FIELDS = frozenset({"question", "tags", "hallmarks", *FINDINGS, "limits", "model_output"})
NAMES = frozenset({"source", "finding", "model", "name", "sha256", "drive_id", "title", "mesh", "label", "tree"})
# an item's tags: 1-MAX_TAGS MeSH descriptors {mesh, label, tree}, resolved against NLM by `mothership note`
MAX_TAGS = 5
MESH = re.compile(r"D\d{6}(?:\d{3})?")  # a descriptor id: D016922, D000091385
TREE = re.compile(r"[A-Z]\d{2}(?:\.\d{3})*")  # a tree number: G07.345.124.130; its letter is the MeSH branch
TAG_PATHS = frozenset({"items[].tags[].mesh", "items[].tags[].tree[]"})
SOURCE_PATHS = frozenset(f"items[].{k}[].source.id" for k in FINDINGS)
MAX_FILES = 20
FILE_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\.(?:csv|tsv|md|json)")
DRIVE_FILE = re.compile(r"[A-Za-z0-9_-]{20,80}")
FILE_PATHS = frozenset({"files[].sha256", "files[].drive_id"})
PROJECT_PATHS = frozenset({"project.id"})  # a uuid, checked by `project`
# an item's sources: exactly {kind, id}, a public identifier in its strict form
SOURCE_IDS = {SourceKind.PMID: re.compile(r"[1-9]\d{0,7}"), SourceKind.DOI: re.compile(r"10\.\d{4,9}/\S{1,200}"),
              SourceKind.NCT: re.compile(r"NCT\d{8}"), SourceKind.MODEL: re.compile(r"(?=.*[A-Za-z])[A-Za-z0-9._:/-]{1,80}")}


def project(doc: dict[str, Any]) -> list[dict[str, str]]:
    """`bad_project` for a `project` that is not exactly {id, title}: a lowercase uuid and a short title."""
    if "project" not in doc:
        return []
    given = doc["project"]
    ok = isinstance(given, dict) and set(given) == {"id", "title"} and isinstance(given["id"], str) \
        and bool(UUID_LOWER.fullmatch(given["id"])) and isinstance(given["title"], str) and 0 < len(given["title"].strip()) <= MAX_TITLE
    return [] if ok else [flag("project", "bad_project")]


def _file(e: Any, seen: list[Any]) -> bool:
    return isinstance(e, dict) and {"name", "sha256"} <= set(e) <= {"name", "sha256", "drive_id"} \
        and isinstance(e["name"], str) and bool(FILE_NAME.fullmatch(e["name"])) and e["name"] not in seen \
        and isinstance(e["sha256"], str) and bool(HEX64.fullmatch(e["sha256"])) \
        and ("drive_id" not in e or isinstance(e["drive_id"], str) and bool(DRIVE_FILE.fullmatch(e["drive_id"])))


def files(doc: dict[str, Any]) -> list[dict[str, str]]:
    """`bad_files` for a `files` list that is not 1-MAX_FILES entries of {name, sha256[, drive_id]} with unique names."""
    given = doc.get("files")
    if given is None:
        return []
    if not isinstance(given, list) or not 0 < len(given) <= MAX_FILES:
        return [flag("files", "bad_files")]
    names = [e.get("name") if isinstance(e, dict) else None for e in given]
    return [flag(f"files[{n}]", "bad_files") for n, e in enumerate(given) if not _file(e, names[:n])]


def by_email(doc: dict[str, Any]) -> list[dict[str, str]]:
    """The files that travel in the email's zip: every entry without a drive_id."""
    return [e for e in doc.get("files") or [] if "drive_id" not in e]


def mask(rule: str, report: str) -> str:
    """The report as `rule` sees it: its masked forms blanked, keeping the line breaks."""
    pattern = REPORT_MASKS.get(rule)
    return pattern.sub(lambda m: " " + "\n" * m[0].count("\n"), report) if pattern else report


LIMITS = {"report": MAX_REPORT}
MASKS = {"report": mask}  # a report's violations name their line (plsi.mothership.scan)


def _text(v: Any) -> bool:
    return isinstance(v, str) and 0 < len(v.strip()) <= MAX_TEXT


def _source(s: Any) -> bool:
    pattern = SOURCE_IDS.get(s["kind"]) if isinstance(s, dict) and isinstance(s.get("kind"), str) else None
    return bool(pattern and set(s) == {"kind", "id"} and isinstance(s["id"], str) and pattern.fullmatch(s["id"]))


def _cites(source: Any) -> tuple[str, str] | None:
    ok = isinstance(source, dict) and isinstance(source.get("kind"), str) and isinstance(source.get("id"), str)
    return (source["kind"], source["id"]) if ok else None


def _finding(cited: set[tuple[str, str]], e: Any) -> bool:
    """{source, finding}: a short finding from one of the item's own sources."""
    return isinstance(e, dict) and set(e) == {"source", "finding"} and _text(e["finding"]) and _cites(e["source"]) in cited


def _model_output(e: Any) -> bool:
    return isinstance(e, dict) and set(e) == {"model", "finding"} and _text(e["finding"]) \
        and isinstance(e["model"], str) and bool(SOURCE_IDS[SourceKind.MODEL].fullmatch(e["model"]))


def _tag(e: Any) -> bool:
    return isinstance(e, dict) and set(e) == {"mesh", "label", "tree"} and isinstance(e["mesh"], str) \
        and bool(MESH.fullmatch(e["mesh"])) and _text(e["label"]) and isinstance(e["tree"], list) \
        and 0 < len(e["tree"]) <= MAX_LIST and all(isinstance(t, str) and TREE.fullmatch(t) for t in e["tree"])


def _tags(item: dict[str, Any], n: int) -> list[dict[str, str]]:
    """`bad_context` unless `tags` is 1-MAX_TAGS distinct MeSH descriptors and `hallmarks` distinct hallmarks."""
    out = []
    if "tags" in item:
        tags = item["tags"]
        ids = [e.get("mesh") for e in tags if isinstance(e, dict)] if isinstance(tags, list) else []
        if not isinstance(tags, list) or not 0 < len(tags) <= MAX_TAGS or len(set(ids)) != len(tags):
            out.append(flag(f"items[{n}].tags", "bad_context"))
        else:
            out += [flag(f"items[{n}].tags[{m}]", "bad_context") for m, e in enumerate(tags) if not _tag(e)]
    if "hallmarks" in item:
        given = item["hallmarks"]
        ok = isinstance(given, list) and 0 < len(given) == len(set(map(str, given))) \
            and all(h in tuple(AgingHallmark) for h in given)
        out += [] if ok else [flag(f"items[{n}].hallmarks", "bad_context")]
    return out


def _entries(item: dict[str, Any], key: str, n: int, ok: Any) -> list[dict[str, str]]:
    entries = item[key]
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_LIST:
        return [flag(f"items[{n}].{key}", "bad_context")]
    return [flag(f"items[{n}].{key}[{m}]", "bad_context") for m, e in enumerate(entries) if not ok(e)]


def check(items: list[dict[str, Any]], report: Any = None) -> list[dict[str, str]]:
    """`bad_source` for each source outside its form, `bad_context` for each item context field (and a `report`)."""
    sources = [item.get("sources", []) for item in items]
    out = [flag(f"items[{n}].sources[{m}]", "bad_source") for n, given in enumerate(sources)
           for m, s in enumerate(given if isinstance(given, list) else [None]) if not _source(s)]
    out += [] if report is None or isinstance(report, str) and report.strip() else [flag("report", "bad_context")]
    for n, item in enumerate(items):
        cited = {_cites(s) for s in sources[n]} - {None} if isinstance(sources[n], list) else set()
        if "question" in item and not _text(item["question"]):
            out.append(flag(f"items[{n}].question", "bad_context"))
        if "evidence_class" in item and item["evidence_class"] not in tuple(EvidenceClass):
            out.append(flag(f"items[{n}].evidence_class", "bad_context"))
        out += _tags(item, n)
        lists = {**dict.fromkeys(FINDINGS, partial(_finding, cited)), "limits": _text, "model_output": _model_output}
        out += [v for key, ok in lists.items() if key in item for v in _entries(item, key, n, ok)]
    return out
