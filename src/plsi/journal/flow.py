"""Flow cytometry from an entry's FCS files: every gate counted from the events within its parent, and the plots the
page draws (event dots coloured by density per x/y pair, a histogram per interval gate). Scatter channels are
linear, fluorescence is shown and gated on arcsinh(value / cofactor); results are cached in the entry folder."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from plsi.errors import PlsiError, ValidationError
from plsi.files import atomic_write_json, hash_json, load_json
from plsi.journal import fcs as fcsfile
from plsi.journal.results import Gate, Results
from plsi.journal.tuning import COUNT_TOLERANCE, FLOW_DOTS, FLOW_GRID, FLOW_HIST_BINS, FLOW_SAMPLES

VERSION = 3  # bump when the cached numbers or plots change
LINEAR = re.compile(r"^(fsc|ssc|time)", re.IGNORECASE)
SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def _axis(f: fcsfile.Fcs, i: int, cofactor: float) -> dict[str, Any]:
    np = fcsfile.numpy()
    name, linear, top = f.names[i], bool(LINEAR.match(f.names[i])), f.ranges[i]
    if linear:
        lo, hi = 0.0, top
        step = 10 ** int(np.floor(np.log10(max(top, 1) / 4)))
        step *= next(m for m in (1, 2, 5, 10) if top / (step * m) <= 6)
        ticks = [[v, f"{v / 1000:g}K" if v >= 1000 else f"{v:g}"] for v in np.arange(0, top + 1, step)]
    else:
        lo, hi = float(np.arcsinh(-3.0)), float(np.arcsinh(top / cofactor))
        ticks = [[0.0, "0"]] + [[t, ("−" if sign < 0 else "") + "10" + str(e).translate(SUPERSCRIPT)]
                                for e in range(2, 8) for sign in (1, -1)
                                if lo <= (t := float(np.arcsinh(sign * 10 ** e / cofactor))) <= hi]
    label = f.labels[i]
    return {"channel": name, "label": name if label == name else f"{label} · {name}", "linear": linear,
            "lo": lo, "hi": hi, "ticks": sorted(ticks)}


def _show(values: Any, axis: dict[str, Any], cofactor: float) -> Any:
    return values if axis["linear"] else fcsfile.numpy().arcsinh(values / cofactor)


def _at(value: float, axis: dict[str, Any], cofactor: float) -> float:
    """One channel value on the plot's display scale."""
    return float(_show(fcsfile.numpy().float64(value), axis, cofactor))


def _mask(g: Gate, f: fcsfile.Fcs, cofactor: float) -> Any:
    np = fcsfile.numpy()
    xi = f.index(g.x)
    x = f.events[:, xi]
    if g.interval:
        return (x >= g.interval[0]) & (x <= g.interval[1])
    yi = f.index(g.y)
    y = f.events[:, yi]
    if g.rect:
        return (x >= g.rect[0]) & (x <= g.rect[1]) & (y >= g.rect[2]) & (y <= g.rect[3])
    ax, ay = _axis(f, xi, cofactor), _axis(f, yi, cofactor)
    px, py = _show(x, ax, cofactor), _show(y, ay, cofactor)
    verts = [(_at(a, ax, cofactor), _at(b, ay, cofactor)) for a, b in g.polygon]
    inside = np.zeros(len(px), dtype=bool)
    for (xa, ya), (xb, yb) in zip(verts, verts[-1:] + verts[:-1], strict=True):  # ray casting, all events per edge
        with np.errstate(divide="ignore", invalid="ignore"):
            inside ^= ((ya > py) != (yb > py)) & (px < (xb - xa) * (py - ya) / (yb - ya) + xa)
    return inside


def _shape(g: Gate, ax: dict[str, Any], ay: dict[str, Any] | None, cofactor: float) -> dict[str, Any]:
    if g.interval:
        return {"lo": _at(g.interval[0], ax, cofactor), "hi": _at(g.interval[1], ax, cofactor)}
    corners = [(g.rect[0], g.rect[2]), (g.rect[1], g.rect[2]), (g.rect[1], g.rect[3]), (g.rect[0], g.rect[3])] if g.rect else g.polygon
    return {"points": [[_at(a, ax, cofactor), _at(b, ay, cofactor)] for a, b in corners]}


def _smooth(grid: Any) -> Any:
    """A small Gaussian blur (sigma about 1.2 bins) along both axes."""
    np = fcsfile.numpy()
    k = np.exp(-0.5 * (np.arange(-3, 4) / 1.2) ** 2)
    k /= k.sum()
    for axis in (0, 1):
        grid = np.apply_along_axis(np.convolve, axis, grid, k, mode="same")
    return grid


def _b64(values: Any, dtype: str) -> str:
    return base64.b64encode(values.astype(dtype).tobytes()).decode("ascii")


def _dots(px: Any, py: Any, ax: dict[str, Any], ay: dict[str, Any]) -> dict[str, Any]:
    """Up to FLOW_DOTS events (a fixed random draw when there are more), each coloured by the smoothed density where
    it lies: x and y as uint16 across the axis, the level 1-255, densest last so it is drawn on top."""
    np = fcsfile.numpy()
    keep = (px >= ax["lo"]) & (px <= ax["hi"]) & (py >= ay["lo"]) & (py <= ay["hi"])
    fx, fy = (px[keep] - ax["lo"]) / (ax["hi"] - ax["lo"]), (py[keep] - ay["lo"]) / (ay["hi"] - ay["lo"])
    ix, iy = np.minimum(fx * FLOW_GRID, FLOW_GRID - 1).astype(int), np.minimum(fy * FLOW_GRID, FLOW_GRID - 1).astype(int)
    grid = np.zeros((FLOW_GRID, FLOW_GRID))
    np.add.at(grid, (iy, ix), 1)
    dens = _smooth(grid)[iy, ix]
    level = 1 + np.log1p(dens) / np.log1p(dens.max()) * 254 if len(dens) and dens.max() > 0 else np.ones(len(dens))
    pick = np.arange(len(fx))
    if len(pick) > FLOW_DOTS:
        pick = np.sort(np.random.default_rng(0).choice(len(fx), FLOW_DOTS, replace=False))
    pick = pick[np.argsort(level[pick], kind="stable")]
    return {"n": int(len(pick)), "x": _b64(np.round(fx[pick] * 65535), "<u2"), "y": _b64(np.round(fy[pick] * 65535), "<u2"),
            "level": _b64(level[pick], "uint8")}


def _ordered(gates: list[Gate], checks: list[str], sample: str) -> list[Gate]:
    names, out, left = set(), [], list(gates)
    while left:
        if not (ready := [g for g in left if g.parent is None or g.parent in names]):
            checks += [f"{sample} · {g.name}: parent gate {g.parent!r} not found; not counted" for g in left]
            break
        out += ready
        names |= {g.name for g in ready}
        left = [g for g in left if g not in ready]
    return out


def _count(f: fcsfile.Fcs, sample: str, r: Results, checks: list[str]) -> tuple[dict, list, dict]:
    """Event masks, a row per gate (events, % of parent and of total) and the gates grouped by the plot they sit on."""
    np = fcsfile.numpy()
    total = len(f.events)
    mine = [g for g in r.gates if g.sample in (None, sample)]
    checks += [f"{sample} · {g.name}: no shape; not counted from the events" for g in mine if not (g.polygon or g.rect or g.interval)]
    exported = {c.gate: c.events for c in r.exported_counts if c.sample == sample}
    masks, rows, groups = {None: np.ones(total, dtype=bool)}, [], {}
    for g in _ordered([g for g in mine if g.polygon or g.rect or g.interval], checks, sample):
        masks[g.name] = masks[g.parent] & _mask(g, f, r.cofactor)
        n, base = int(masks[g.name].sum()), int(masks[g.parent].sum())
        rows.append({"gate": g.name, "parent": g.parent, "events": n, "of_parent": n / base * 100 if base else None,
                     "of_total": n / total * 100 if total else None})
        if g.name in exported and abs(exported[g.name] - n) > COUNT_TOLERANCE * max(n, 1):
            checks.append(f"{sample} · {g.name}: exported {exported[g.name]:,} events, the file gives {n:,}")
        groups.setdefault((g.parent, f.index(g.x), f.index(g.y) if g.y and not g.interval else None), []).append(g)
    if not groups and len(scatter := [i for i, n in enumerate(f.names) if LINEAR.match(n) and not n.lower().startswith("time")]) >= 2:
        groups[(None, scatter[0], scatter[1])] = []  # no gates: the scatter plot of all events
    return masks, rows, groups


def _plots(f: fcsfile.Fcs, masks: dict, rows: list, groups: dict, cofactor: float) -> list[dict[str, Any]]:
    np = fcsfile.numpy()
    pct = {row["gate"]: row["of_parent"] for row in rows}
    plots = []
    for (parent, xi, yi), gs in groups.items():
        pop = f.events[masks[parent]]
        ax = _axis(f, xi, cofactor)
        ay = None if yi is None else _axis(f, yi, cofactor)
        px = _show(pop[:, xi], ax, cofactor)
        plot = {"parent": parent or "all events", "events": len(pop), "x": ax,
                "gates": [{"name": g.name, "pct": pct.get(g.name), **_shape(g, ax, ay, cofactor)} for g in gs]}
        if ay is None:
            plot["histogram"] = np.histogram(px, bins=FLOW_HIST_BINS, range=(ax["lo"], ax["hi"]))[0].tolist()
        else:
            plot.update({"y": ay, "dots": _dots(px, _show(pop[:, yi], ay, cofactor), ax, ay)})
        plots.append(plot)
    return plots


def _sample(path: Path, sample: str, r: Results, checks: list[str]) -> dict[str, Any]:
    f = fcsfile.read(path, r.compensate)
    if r.compensate and not f.compensated:
        checks.append(f"{sample}: the file has no spillover matrix; shown uncompensated")
    masks, rows, groups = _count(f, sample, r, checks)
    return {"sample": sample, "file": path.name, "events": len(f.events), "compensated": f.compensated,
            "channels": [{"name": n, "label": lab} for n, lab in zip(f.names, f.labels, strict=True)],
            "gates": rows, "plots": _plots(f, masks, rows, groups, r.cofactor)}


def derive(folder: Path, r: Results, strict: bool = False) -> dict[str, Any]:
    """Every sample's gate counts and plots ({} without FCS files). strict: a wrong channel or an unreadable file
    raises (save); otherwise it becomes a check (the page)."""
    if not r.fcs:
        return {}
    files = folder / "files"
    sizes = [(f.sample, f.file, (files / f.file).stat().st_size if (files / f.file).is_file() else None) for f in r.fcs]
    key = hash_json({"v": VERSION, "files": sizes, "gates": [g.dump() for g in r.gates], "cofactor": r.cofactor,
                     "exported": [c.dump() for c in r.exported_counts], "compensate": r.compensate})
    cache_path = folder / "flow-cache.json"
    if cache_path.is_file() and (cache := load_json(cache_path)).get("key") == key:
        return cache["flow"]
    checks: list[str] = []
    samples = []
    for f in r.fcs[:FLOW_SAMPLES]:
        if not (files / f.file).is_file():
            checks.append(f"{f.sample}: {f.file} is not attached yet")
            continue
        try:
            samples.append(_sample(files / f.file, f.sample, r, checks))
        except PlsiError as e:
            if strict and isinstance(e, ValidationError):
                raise
            checks.append(f"{f.sample}: {e.message}")
    if len(r.fcs) > FLOW_SAMPLES:
        checks.append(f"only the first {FLOW_SAMPLES} samples are drawn")
    names = list(dict.fromkeys(row["gate"] for s in samples for row in s["gates"]))
    summary = {"gates": names, "rows": [[s["sample"], *[next((x["of_parent"] for x in s["gates"] if x["gate"] == n), None)
                                                         for n in names]] for s in samples]}
    out = {"samples": samples, "summary": summary, "checks": checks}
    if samples:
        atomic_write_json(cache_path, {"key": key, "flow": out}, private=True)
    return out
