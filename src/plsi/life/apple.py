"""`plsi apple export`: an Apple Health export ZIP -> the daily rows of wearables/apple-health step 4.

export.xml is streamed straight out of the ZIP (nothing is extracted, so no member path is ever written) and only
the record types a map uses are kept. One row per date, metric and source kind ("watch", "phone", "other"); device
and account names never leave this function. Monthly means, the 15-day minimum and the one-app-per-metric choice
stay with wearables/import step 3. No network calls.
"""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from plsi.errors import NotFound, ValidationError
from plsi.files import atomic_write_text, sha256_file

SUMMED = {  # summed per calendar day: metric, unit
    "HKQuantityTypeIdentifierStepCount": ("steps", "/d"),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("exercise_minutes", "min"),
}
AVERAGED = {  # mean per calendar day
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_heart_rate", "/min"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_sdnn", "ms"),
}
READINGS = {  # one row per reading, unit as recorded
    "HKQuantityTypeIdentifierVO2Max": "vo2_max",
    "HKQuantityTypeIdentifierBodyMass": "weight",
    "HKQuantityTypeIdentifierBloodPressureSystolic": "bp_systolic",
    "HKQuantityTypeIdentifierBloodPressureDiastolic": "bp_diastolic",
}
SLEEP = "HKCategoryTypeIdentifierSleepAnalysis"
ASLEEP = {f"HKCategoryValueSleepAnalysis{v}" for v in ("Asleep", "AsleepCore", "AsleepDeep", "AsleepREM", "AsleepUnspecified")}
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}$")
COLUMNS: tuple[str, ...] = ("date", "metric", "value", "unit", "source")


def _time(raw: str | None) -> datetime | None:
    """Apple's '2024-01-15 22:30:00 +0400'; the day is the local one as written, never shifted."""
    try:
        return datetime.strptime(raw or "", "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


def _kind(rec: dict[str, str]) -> str:
    text = f"{rec.get('sourceName', '')} {rec.get('device', '')}".lower()
    return "watch" if "watch" in text else "phone" if "iphone" in text or "phone" in text else "other"


def _member(zf: zipfile.ZipFile) -> str:
    names = [n for n in zf.namelist() if n.replace("\\", "/").rsplit("/", 1)[-1] == "export.xml"]
    if len(names) != 1:
        raise ValidationError("not an Apple Health export: the ZIP needs exactly one export.xml", code="APPLE_EXPORT_FORMAT",
                              hint="share the export.zip from Health -> profile -> Export All Health Data")
    return names[0]


def _merged_minutes(spans: list[tuple[datetime, datetime]]) -> float:
    total, end = 0.0, None
    for a, b in sorted(spans):
        if end is not None and a < end:
            a = end
        if b > a:
            total += (b - a).total_seconds()
            end = b if end is None else max(end, b)
    return total / 60


def daily_rows(zip_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """(rows, counts of skipped record types). Every app is its own source, so two apps of one kind are never added
    together; sleep segments are merged per app and dated by wake-up day."""
    sums: dict[tuple[str, str, str, str], float] = defaultdict(float)
    means: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    sleep: dict[tuple[str, str], list[tuple[datetime, datetime]]] = defaultdict(list)
    readings: dict[tuple[str, str, str, str, str], None] = {}  # blood pressure is listed twice (in its Correlation too)
    skipped: dict[str, int] = defaultdict(int)
    kinds: dict[str, str] = {}  # app name -> kind; names never leave this function
    try:
        with zipfile.ZipFile(zip_path) as zf, zf.open(_member(zf)) as xml:
            root = None
            for event, el in ET.iterparse(xml, events=("start", "end")):
                if root is None:
                    root = el
                    if el.tag != "HealthData":
                        raise ValidationError("export.xml is not an Apple Health export", code="APPLE_EXPORT_FORMAT")
                if event == "start" or el.tag != "Record":
                    continue
                rec = dict(el.attrib)
                root.clear()  # keeps memory flat on multi-GB exports
                rtype, raw, src = rec.get("type", ""), rec.get("startDate", ""), rec.get("sourceName", "")
                if rtype == SLEEP:
                    start, end = _time(raw), _time(rec.get("endDate"))
                    if rec.get("value") not in ASLEEP:
                        skipped["sleep:" + rec.get("value", "").removeprefix("HKCategoryValueSleepAnalysis")] += 1
                    elif start and end and end > start:
                        kinds.setdefault(src, _kind(rec))
                        sleep[(end.date().isoformat(), src)].append((start, end))
                    continue
                try:
                    value = float(rec.get("value", ""))
                except ValueError:
                    value = None
                day = raw[:10]  # the local day as written: no timestamp parse per record (exports run to millions)
                if not _DAY.match(day) or value is None or not (rtype in SUMMED or rtype in AVERAGED or rtype in READINGS):
                    skipped[rtype.removeprefix("HKQuantityTypeIdentifier") or "unknown"] += 1
                    continue
                kinds.setdefault(src, _kind(rec))
                if rtype in SUMMED:
                    sums[(day, *SUMMED[rtype], src)] += value
                elif rtype in AVERAGED:
                    means[(day, *AVERAGED[rtype], src)].append(value)
                else:
                    readings[(raw, READINGS[rtype], rec.get("value", ""), rec.get("unit", ""), src)] = None
    except ET.ParseError as exc:
        raise ValidationError(f"export.xml is not valid XML: {exc}", code="APPLE_EXPORT_FORMAT") from None
    except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError, OSError) as exc:
        raise ValidationError(f"the ZIP cannot be read to the end: {exc}", code="APPLE_EXPORT_UNREADABLE",
                              hint="download or export it again; an encrypted ZIP is not supported") from None
    label = _labels(kinds)
    rows = [{"date": t[:10], "metric": m, "value": float(v), "unit": u, "source": label[s]} for t, m, v, u, s in readings]
    rows += [{"date": d, "metric": m, "value": v, "unit": u, "source": label[s]} for (d, m, u, s), v in sums.items()]
    rows += [{"date": d, "metric": m, "value": sum(v) / len(v), "unit": u, "source": label[s]} for (d, m, u, s), v in means.items()]
    rows += [{"date": d, "metric": "sleep_duration", "value": _merged_minutes(sp), "unit": "min", "source": label[s]}
             for (d, s), sp in sleep.items()]
    rows.sort(key=lambda r: (r["date"], r["metric"], r["source"]))
    return rows, dict(skipped)


def _labels(kinds: dict[str, str]) -> dict[str, str]:
    """App name -> 'watch', 'phone' or 'other', numbered ('watch-2') when one kind has several apps."""
    count: dict[str, int] = defaultdict(int)
    out = {}
    for src in sorted(kinds):
        count[kinds[src]] += 1
        out[src] = kinds[src] if count[kinds[src]] == 1 else f"{kinds[src]}-{count[kinds[src]]}"
    return out


def export(file: str, out: str) -> dict[str, Any]:
    """Write the daily rows to `out` (CSV: date,metric,value,unit,source). Returns {out, sha256 (of the ZIP, for
    origin.file_sha256), rows, metrics, first, last, skipped_types}: per metric the row count by source kind, and the record types not read (names and counts only)."""
    path = Path(file)
    if not path.is_file():
        raise NotFound(f"input file not found: {path.name}", code="FILE_NOT_FOUND")
    rows, skipped = daily_rows(path)
    sha = sha256_file(path)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({**r, "value": f"{r['value']:.6g}"} for r in rows)
    atomic_write_text(Path(out), buf.getvalue())
    metrics: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        metrics[r["metric"]][r["source"]] += 1
    return {"out": out, "sha256": sha, "rows": len(rows), "metrics": {m: dict(k) for m, k in metrics.items()},
            "first": rows[0]["date"] if rows else None, "last": rows[-1]["date"] if rows else None, "skipped_types": skipped}
