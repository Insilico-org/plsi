"""The files `plsi bio` reads: CSV/TSV tables with a header row, gene lists (one per line) and GMT gene sets."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from plsi.errors import NotFound, ValidationError


def _path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_file():
        raise NotFound(f"no file {p}", hint="pass the path of a file on this computer")
    return p


def rows(path: str | Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    """Every row of a CSV (or TSV, by extension or tab in the header) as {column: text}; refuses missing columns."""
    p = _path(path)
    text = p.read_text(encoding="utf-8").lstrip("﻿")
    first = text.split("\n", 1)[0]
    delimiter = "\t" if p.suffix.lower() in {".tsv", ".tab"} or "\t" in first else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    header = [h.strip() for h in reader.fieldnames or []]
    if missing := [c for c in required if c not in header]:
        raise ValidationError(f"{p.name} has no column {', '.join(missing)} (has: {', '.join(header)})",
                              code="BAD_TABLE", hint=f"columns needed: {', '.join(required)}")
    out = []
    for n, row in enumerate(reader, start=2):
        if None in row:
            raise ValidationError(f"{p.name} line {n} has more cells than the header (an unquoted comma?)",
                                  code="BAD_TABLE", hint="quote any cell that holds the delimiter")
        out.append({k.strip(): (v or "").strip() for k, v in row.items()})
    return out


def number(row: dict[str, str], column: str, where: str, *, optional: bool = False) -> float | None:
    raw = row.get(column, "")
    if raw == "" or raw.upper() in {"NA", "NAN", "NULL"}:
        if optional:
            return None
        raise ValidationError(f"{where}: `{column}` is empty", code="BAD_TABLE")
    try:
        value = float(raw)
    except ValueError:
        raise ValidationError(f"{where}: `{column}` is {raw!r}, not a number", code="BAD_TABLE") from None
    if not math.isfinite(value):
        raise ValidationError(f"{where}: `{column}` is not finite", code="BAD_TABLE")
    return value


def genes(path: str | Path) -> list[str]:
    """A gene list, one symbol per line; blank lines and lines starting with # are skipped; order kept, no repeats."""
    seen: dict[str, None] = {}
    for line in _path(path).read_text(encoding="utf-8").splitlines():
        if (g := line.strip().split("\t")[0].split(",")[0].strip()) and not g.startswith("#"):
            seen.setdefault(g.upper(), None)
    return list(seen)


def gmt(path: str | Path) -> dict[str, list[str]]:
    """A GMT file: name, description, then the set's genes, tab-separated, one set per line."""
    out: dict[str, list[str]] = {}
    for n, line in enumerate(_path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) < 3:
            raise ValidationError(f"{Path(path).name} line {n}: a set needs a name, a description and genes",
                                  code="BAD_TABLE")
        out[cells[0].strip()] = sorted({g.strip().upper() for g in cells[2:] if g.strip()})
    return out
