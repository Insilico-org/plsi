"""A research note's data files (WIRE §7, Files): checked as the Mother checks them, then zipped for the email."""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from plsi import files, paths
from plsi.errors import GateFailed, ValidationError
from plsi.mothership import note, scan
from plsi.mothership.relay import DRIVE_REFERENCE, mail_address
from plsi.mothership.scan import flag

MAX_BYTES = 9_000_000
MAX_ZIP = 9_500_000  # under the 10 MB mail attachment limit
MAX_ROWS = 5_000
REPORT_FILE = "report.md"  # a long note's report, sent as a data file (plsi.mothership.research)
RESERVED = frozenset({"note.json", REPORT_FILE})  # a data file never takes the name of the note or its report
VEGA_LITE = "https://vega.github.io/schema/vega-lite/"
FORMULA = ("=", "+", "-", "@")
DRIVE_LINK = re.compile(rf"/d/({note.DRIVE_FILE.pattern})|[?&]id=({note.DRIVE_FILE.pattern})|^({note.DRIVE_FILE.pattern})$")


def _number(cell: str) -> bool:
    try:
        float(cell)
        return True
    except ValueError:
        return False


def _statistics(rule: str, text: str) -> str:
    """A data file's text as `rule` reads it: statistics blanked for the id-number rule."""
    return note.STATISTIC.sub(" ", text) if rule == "id_number" else text


def _rules(text: str, instances: set[str], numeric: bool = False) -> set[str]:
    clean = note.CITATION.sub(" ", note.REPORT_MASKS["url"].sub(" ", scan.normal(text)))  # a doi.org link is a citation
    rules = [r for r in scan.PATTERNS if not (numeric and r == "id_number")]
    return set(scan.broken(clean, instances, rules, _statistics))


def _chart(doc: dict[str, Any]) -> bool:
    """A Vega-Lite chart that draws only its inline numbers: no url, href or image mark, at most MAX_ROWS rows."""
    found = scan.pairs(doc)
    marks = [v.get("type") if isinstance(v, dict) else v for k, v in found if k == "mark"]
    rows = sum(len(v) for k, v in found if k == "values" and isinstance(v, list))
    return not any(k in ("url", "href") for k, _ in found) and "image" not in marks and rows <= MAX_ROWS


def check(name: str, data: bytes, instances: set[str]) -> set[str]:
    """The rules one file breaks; empty when it may go."""
    ext = name.rsplit(".", 1)[-1]
    if len(data) > MAX_BYTES:
        return {"too_large"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"bad_file"}
    if any(c < " " and c not in "\t\n\r" for c in text):
        return {"bad_file"}
    if ext == "json":
        try:
            doc = json.loads(text)
        except ValueError:
            return {"bad_file"}
        schema = doc.get("$schema") if isinstance(doc, dict) else None
        chart = isinstance(schema, str) and schema.startswith(VEGA_LITE)
        strings = (s for _, _, s, _ in scan.walk(doc) if isinstance(s, str) and s != schema)
        found = set().union(*(_rules(s, instances) for s in strings))
        return found | ({"bad_chart"} if chart and not _chart(doc) else set())
    if ext in ("csv", "tsv"):
        cells = [c for row in csv.reader(io.StringIO(text), delimiter="," if ext == "csv" else "\t") for c in row]
        found = set().union(*(_rules(c, instances, _number(c)) for c in cells))
        return found | ({"formula"} if any(c.startswith(FORMULA) and not _number(c) for c in cells) else set())
    return _rules(text, instances)


def _drive_id(link: str) -> str:
    found = DRIVE_LINK.search(link.strip())
    if not found:
        raise ValidationError("not a Google Drive file link", code="BAD_DRIVE_LINK")
    return next(g for g in found.groups() if g)


def prepare(given: Any, instances: set[str]) -> tuple[list[dict[str, str]], dict[str, bytes]]:
    """(the note's `files` entries, the email files by name) from Explorer's [{path[, drive_link]}]."""
    if not isinstance(given, list) or not 0 < len(given) <= note.MAX_FILES:
        raise ValidationError(f"files is a list of 1-{note.MAX_FILES} {{path[, drive_link]}}", code="BAD_CONTRIBUTION")
    work = (paths.plsi_home() / "work").resolve()
    if any(isinstance(item, dict) and item.get("drive_link") for item in given):
        mail_address(DRIVE_REFERENCE, "Drive address", "NO_DRIVE_ADDRESS")  # files are shared with it
    entries, mail, found = [], {}, []
    for n, item in enumerate(given):
        path = Path(str(item.get("path", ""))).resolve() if isinstance(item, dict) else None
        if path is None or work not in path.parents or not path.is_file():
            raise ValidationError(f"files[{n}] is not a file under <PLSI_HOME>/work", code="BAD_CONTRIBUTION")
        if path.name in RESERVED:
            raise ValidationError(f"{path.name} is the name the note's own parts travel under: rename the data file",
                                  code="BAD_FILE_NAME")
        if not note.FILE_NAME.fullmatch(path.name):
            raise ValidationError(f"{path.name}: name a data file in lower case, letters, digits, _ and -, ending .csv, "
                                  ".tsv, .md or .json", code="BAD_FILE_NAME")
        data = path.read_bytes()
        found += [flag(f"files[{n}]", r) for r in sorted(check(path.name, data, instances))]
        entry = {"name": path.name, "sha256": files.sha256_hex(data)}
        if item.get("drive_link"):
            entry["drive_id"] = _drive_id(str(item["drive_link"]))
        else:
            mail[path.name] = data
        entries.append(entry)
    if found:
        raise GateFailed(found, "the research note's files are not safe to send")
    return entries, mail


def zip_bytes(members: dict[str, bytes]) -> bytes:
    """A flat, reproducible zip of the email files; too large for email raises."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o644 << 16
            zf.writestr(info, members[name])
    if out.tell() > MAX_ZIP:
        raise ValidationError("the files are too large for one email", code="TOO_LARGE_FOR_EMAIL",
                              hint="share the largest on Google Drive and give its drive_link")
    return out.getvalue()


def verify(path: Path, entries: list[dict[str, str]]) -> None:
    """Raise unless the zip holds exactly the note's email files, unchanged."""
    try:
        with zipfile.ZipFile(path) as zf:
            got = {i.filename: files.sha256_hex(zf.read(i)) for i in zf.infolist()}
    except (OSError, zipfile.BadZipFile):
        got = None
    if got != {e["name"]: e["sha256"] for e in entries}:
        raise ValidationError("the files changed since they were checked", code="HASH_MISMATCH",
                              hint="build the note again and ask the user to approve it")
