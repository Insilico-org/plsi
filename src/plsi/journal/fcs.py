"""Read a flow cytometry FCS file (2.0, 3.0, 3.1; list mode) into its channels and an events x channels array, with
the file's own spillover matrix applied when it has one. numpy is needed (the flow extra; the bot's environment has it)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plsi.errors import DependencyMissing, ValidationError

SPILL_KEYS = ("$SPILLOVER", "SPILL", "$SPILL", "SPILLOVER")


@dataclass
class Fcs:
    names: list[str]  # $PnN, what the gates name
    labels: list[str]  # $PnS (marker, e.g. "CD45"), or the name when there is none
    ranges: list[float]  # $PnR
    events: Any  # numpy array, events x channels
    compensated: list[str]  # channels the spillover matrix was applied to

    def index(self, channel: str) -> int:
        """A channel by its name or its marker label, case and punctuation ignored."""
        want = re.sub(r"[^a-z0-9]", "", channel.lower())
        for i, (n, lab) in enumerate(zip(self.names, self.labels, strict=True)):
            if want in (re.sub(r"[^a-z0-9]", "", n.lower()), re.sub(r"[^a-z0-9]", "", lab.lower())):
                return i
        raise ValidationError(f"channel {channel!r} is not in the file ({', '.join(self.names)})", code="FCS_CHANNEL")


def numpy() -> Any:
    try:
        import numpy as np
    except ImportError as e:
        raise DependencyMissing("flow data needs numpy", code="FLOW_UNAVAILABLE", hint="uv pip install numpy") from e
    return np


def _invalid(path: Path, why: str) -> ValidationError:
    return ValidationError(f"{path.name}: {why}", code="FCS_INVALID", hint="export the FCS file again from the cytometer or FlowJo")


def _text(raw: bytes) -> dict[str, str]:
    """The TEXT segment: delimiter first, pairs after; a doubled delimiter is a literal one."""
    text = raw.decode("utf-8", errors="replace")
    if not text:
        return {}
    d = re.escape(text[0])
    parts = [p.replace(text[0] * 2, text[0]) for p in re.split(f"(?<!{d}){d}(?!{d})", text[1:])]
    if parts and parts[-1] == "":
        parts.pop()
    return {parts[i].strip().upper(): parts[i + 1].strip() for i in range(0, len(parts) - 1, 2)}


def _segments(path: Path, data: bytes) -> tuple[dict[str, str], int, int]:
    """The TEXT keywords and the data segment's first and last byte, from the header (or TEXT past 99,999,999)."""
    if data[:3] != b"FCS":
        raise _invalid(path, "not an FCS file")
    try:
        t0, t1, d0, d1 = (int(data[a:a + 8].strip() or 0) for a in (10, 18, 26, 34))
        meta = _text(data[t0:t1 + 1])
        if not d0 or not d1:
            d0, d1 = int(meta.get("$BEGINDATA", 0)), int(meta.get("$ENDDATA", 0))
    except ValueError:
        raise _invalid(path, "the header's segment offsets are not numbers") from None
    if not ("$PAR" in meta and "$TOT" in meta):
        raise _invalid(path, "no $PAR or $TOT keyword")
    if meta.get("$MODE", "L") != "L":
        raise _invalid(path, "only list-mode files are read")
    if not 0 < d0 <= d1 < len(data):
        raise _invalid(path, "the data segment lies outside the file")
    return meta, d0, d1


def _dtype(path: Path, meta: dict[str, str], par: int) -> str:
    kind, endian = meta.get("$DATATYPE", "F").upper(), "<" if meta.get("$BYTEORD", "1,2,3,4").startswith("1") else ">"
    bits = {int(meta.get(f"$P{i}B", "32")) for i in range(1, par + 1)}
    if kind in ("F", "D"):
        return f"{endian}f{4 if kind == 'F' else 8}"
    if kind == "I" and len(bits) == 1 and bits <= {16, 32}:
        return f"{endian}u{bits.pop() // 8}"
    raise _invalid(path, f"data type {kind} with {sorted(bits)} bits is not read")


def _spill(meta: dict[str, str], names: list[str]) -> tuple[list[str], list[list[float]]] | None:
    raw = next((meta[k] for k in SPILL_KEYS if meta.get(k)), None)
    if not raw:
        return None
    t = [x.strip() for x in raw.split(",")]
    n = int(t[0])
    chans, vals = t[1:1 + n], [float(x) for x in t[1 + n:1 + n + n * n]]
    if len(vals) != n * n or not all(c in names for c in chans):
        raise ValidationError("the file's spillover matrix does not match its channels", code="FCS_SPILLOVER")
    return chans, [vals[i * n:(i + 1) * n] for i in range(n)]


def read(path: Path, compensate: bool = True) -> Fcs:
    np = numpy()
    data = path.read_bytes()
    meta, d0, d1 = _segments(path, data)
    par, tot = int(meta["$PAR"]), int(meta["$TOT"])
    dtype = _dtype(path, meta, par)
    if (d1 - d0 + 1) < tot * par * np.dtype(dtype).itemsize:
        raise _invalid(path, "the data segment is shorter than $TOT x $PAR")
    events = np.frombuffer(data, dtype=dtype, count=tot * par, offset=d0).reshape(tot, par).astype("f8")
    names = [meta.get(f"$P{i}N", f"P{i}") for i in range(1, par + 1)]
    labels = [meta.get(f"$P{i}S") or names[i - 1] for i in range(1, par + 1)]
    ranges = [float(meta.get(f"$P{i}R", "262144")) for i in range(1, par + 1)]
    if dtype[1] == "u":  # log-amplified integer channels: value = f2 * 10^(f1 * x / range)
        for i in range(par):
            f1, f2 = (float(x) for x in (meta.get(f"$P{i + 1}E", "0,0").split(",") + ["0"])[:2])
            if f1 > 0:
                events[:, i] = (f2 or 1.0) * 10 ** (f1 * events[:, i] / ranges[i])
    done: list[str] = []
    if compensate and (spill := _spill(meta, names)):
        chans, matrix = spill
        idx = [names.index(c) for c in chans]
        events[:, idx] = events[:, idx] @ np.linalg.inv(np.array(matrix))
        done = chans
    return Fcs(names, labels, ranges, events, done)
