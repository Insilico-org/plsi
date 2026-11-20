"""`plsi bio disproportionality` (ROR, PRR and Yates chi-square per drug-event pair from deduplicated 2x2 counts) and
`plsi bio null-check` (whether a permuted run flags about alpha, as a null should)."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from plsi.bio import figures, stats
from plsi.bio.flags import raise_flag
from plsi.bio.tables import number, rows
from plsi.bio.tuning import ALPHA, FIGURE_ROWS, MAX_ROWS_SHOWN, MIN_CELL, NULL_CALIBRATION
from plsi.distributions import Z95, binom_sf, chi2_sf
from plsi.errors import ValidationError
from plsi.vocab.bio import BioRule


def _pair(a: float, b: float, c: float, d: float) -> dict[str, Any]:
    ror = ci = None
    if min(a, b, c, d) > 0:
        ror = a * d / (b * c)
        half = Z95 * math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        ci = [ror * math.exp(-half), ror * math.exp(half)]
    n, den = a + b + c + d, (a + b) * (c + d) * (a + c) * (b + d)
    chi = n * max(0.0, abs(a * d - b * c) - n / 2) ** 2 / den if den else 0.0
    return {"ror": ror, "ror_ci": ci, "prr": (a / (a + b)) / (c / (c + d)) if c > 0 and a + b > 0 else None,
            "chi2": chi, "p": chi2_sf(chi, 1) if den else 1.0}


COLUMNS = ("drug", "event", "a", "ror", "ror_low", "ror_high", "prr", "chi2", "p", "padj", "sparse", "signal")


def _write(out: str, pairs: list[dict[str, Any]]) -> None:
    with Path(out).open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        w.writerows([r["drug"], r["event"], r["a"], r["ror"], *(r["ror_ci"] or [None, None]), r["prr"], r["chi2"], r["p"],
                     r["padj"], r["sparse"], r["signal"]] for r in pairs)


def _label(row: dict[str, Any]) -> str:
    return f"{row['drug']} · {row['event']}"


def _control(pairs: list[dict[str, Any]], control: str, flags: list[str]) -> dict[str, Any]:
    """The frozen positive control `drug:event`: its row, and `control_missed` when it is not a signal."""
    drug, sep, event = control.partition(":")
    row = next((r for r in pairs if r["drug"] == drug.strip() and r["event"] == event.strip()), None) if sep else None
    if row is None:
        raise ValidationError(f"no pair {control!r} in the table", code="NO_CONTROL", hint="--control '<drug>:<event>'")
    if not row["signal"]:
        raise_flag(flags, BioRule.CONTROL_MISSED, f"the positive control {control} is not a signal: the pipeline is wrong")
    return row


def disproportionality(file: str, alpha: float = ALPHA, out: str | None = None, control: str | None = None,
                       figure: str | None = None) -> dict[str, Any]:
    """`out` writes every pair (the output shows the top rows only); `control` names the frozen positive control."""
    pairs = []
    for i, r in enumerate(rows(file, ("drug", "event", "a", "b", "c", "d")), start=2):
        cells = [number(r, k, f"line {i}") for k in "abcd"]
        if any(x is None or x < 0 or x != int(x) for x in cells):
            raise ValidationError(f"line {i}: a, b, c and d are counts", code="BAD_TABLE")
        pairs.append({"drug": r["drug"], "event": r["event"], "a": int(cells[0]), **_pair(*cells),  # type: ignore[arg-type]
                    "sparse": cells[0] < MIN_CELL})  # type: ignore[operator]
    for row, q in zip(pairs, stats.bh([r["p"] for r in pairs])):
        row["padj"] = q
        row["signal"] = not row["sparse"] and q < alpha and row["ror_ci"] is not None and row["ror_ci"][0] > 1
    flags: list[str] = []
    if sparse := sum(1 for r in pairs if r["sparse"]):
        raise_flag(flags, BioRule.SPARSE_TABLE, f"{sparse} pairs have under {MIN_CELL} reports in the drug-event cell; "
                   "none of them is a signal")
    pairs.sort(key=lambda r: (not r["signal"], r["p"]))
    ctrl = _control(pairs, control, flags) if control else None
    if out:
        _write(out, pairs)
    shown = [r for r in pairs if r["ror_ci"] and not r["sparse"]][:FIGURE_ROWS]
    if ctrl and ctrl not in shown and ctrl["ror_ci"]:
        shown = shown[:FIGURE_ROWS - 1] + [ctrl]
    shown.sort(key=lambda r: -r["ror"])
    drawn = figures.forest([(_label(r), r["ror"], *r["ror_ci"]) for r in shown], None, figure,
                           f"Reporting odds ratios, top {len(shown)} of {len(pairs)} pairs"
                           + (" (positive control marked)" if ctrl else ""), "ROR (95% CI, log scale)", 1.0, log=True,
                           marked=_label(ctrl) if ctrl else None) if figure else []
    return {"control": ctrl, "table": out, "figures": drawn, "pairs": len(pairs),
            "signals": sum(1 for r in pairs if r["signal"]),
            "sparse": sparse, "alpha": alpha, "top": pairs[:MAX_ROWS_SHOWN], "flags": flags}


def null_check(file: str, alpha: float = ALPHA, column: str = "p", figure: str | None = None) -> dict[str, Any]:
    ps = [number(r, column, f"line {i}") for i, r in enumerate(rows(file, (column,)), start=2)]
    if not ps:
        raise ValidationError("the null run has no p-values", code="BAD_TABLE")
    flagged = sum(1 for p in ps if p < alpha)  # type: ignore[operator]
    share, tail = flagged / len(ps), binom_sf(flagged, len(ps), alpha)
    flags: list[str] = []
    if share > NULL_CALIBRATION * alpha or tail < alpha:
        raise_flag(flags, BioRule.NULL_MISSPECIFIED, f"the permuted null flags {share:.1%} at alpha {alpha} (expected "
                   "about alpha): it keeps the structure it should remove; fix the permutation")
    drawn = figures.p_hist(ps, alpha, figure, f"Permuted null: {share:.1%} flagged at alpha {alpha}"  # type: ignore[arg-type]
                           + ("" if not flags else " (misspecified)")) if figure else []
    return {"figures": drawn, "tested": len(ps), "flagged": flagged, "share": share, "expected": alpha, "binomial_p": tail,
            "calibrated": not flags, "flags": flags}
