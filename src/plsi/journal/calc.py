"""`plsi journal calc`: bench arithmetic on named quantities ("10 mM", "250uL", "5e5"), each result with its steps;
units are checked against their family, and a missing or impossible input is one clear error. Writes nothing."""

from __future__ import annotations

import math
import re
from typing import Any

from plsi.errors import ValidationError
from plsi.files import load_json
from plsi.vocab.journal import CalcKind, PlateFormat

MOLAR = {"M": 1.0, "mM": 1e-3, "uM": 1e-6, "µM": 1e-6, "nM": 1e-9, "pM": 1e-12}
MASS_CONC = {"g/L": 1.0, "mg/mL": 1.0, "ug/uL": 1.0, "µg/µL": 1.0, "ug/mL": 1e-3, "µg/mL": 1e-3, "ng/uL": 1e-3,
             "ng/µL": 1e-3, "ng/mL": 1e-6, "%": 10.0}  # % = g per 100 mL
FOLD = {"X": 1.0, "x": 1.0}
VOLUME = {"L": 1.0, "mL": 1e-3, "uL": 1e-6, "µL": 1e-6, "nL": 1e-9}
MASS = {"kg": 1e3, "g": 1.0, "mg": 1e-3, "ug": 1e-6, "µg": 1e-6, "ng": 1e-9, "pg": 1e-12}
CONCENTRATIONS = (MOLAR, MASS_CONC, FOLD)
# growth area (cm²) and working volume (mL) per well
WELLS = {PlateFormat.W6: (9.5, 2.0), PlateFormat.W12: (3.8, 1.0), PlateFormat.W24: (1.9, 0.5),
         PlateFormat.W48: (0.95, 0.25), PlateFormat.W96: (0.32, 0.1), PlateFormat.W384: (0.056, 0.04)}
MICRO = re.compile(r"(?<![A-Za-z])u(?=[A-Za-z])")  # uL, ng/uL, uM as printed: µL, ng/µL, µM
_QTY = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([^\d\s].*)?$")


def quantity(text: Any, what: str) -> tuple[float, str]:
    """'10 mM' -> (10.0, 'mM'); a bare number has unit ''."""
    m = _QTY.match(str(text))
    if not m:
        raise ValidationError(f"{what}: {text!r} is not a number with a unit", code="CALC_INPUT")
    return float(m.group(1)), (m.group(2) or "").strip()


def _in(params: dict[str, Any], key: str, family: dict[str, float] | None = None, default: Any = None) -> float:
    """params[key] in the family's base unit (a bare number is taken as already in it)."""
    raw = params.get(key, default)
    if raw is None:
        raise ValidationError(f"{key} is needed", code="CALC_INPUT")
    value, unit = quantity(raw, key)
    if family is None or not unit:
        return value
    if unit not in family:
        raise ValidationError(f"{key}: unit {unit!r} is not one of {', '.join(family)}", code="CALC_UNIT")
    return value * family[unit]


def _numbers(params: dict[str, Any], key: str) -> list[float]:
    """A list written as "46, 51; 39" (commas or semicolons)."""
    try:
        return [float(x) for x in str(params.get(key, "")).replace(";", ",").split(",") if x.strip()]
    except ValueError:
        raise ValidationError(f"{key}: numbers separated by commas", code="CALC_INPUT") from None


def _conc(params: dict[str, Any], key: str) -> tuple[float, dict[str, float]]:
    value, unit = quantity(params[key], key)
    for family in CONCENTRATIONS:
        if unit in family:
            return value * family[unit], family
    raise ValidationError(f"{key}: unit {unit!r} is not a concentration (M, mg/mL, %, X ...)", code="CALC_UNIT")


def _show(value: float, family: dict[str, float]) -> str:
    """A base-unit value in the family unit that gives a number between 1 and 1000 (a volume down to 0.1 µL stays in
    µL, as pipettes are set)."""
    if family is VOLUME and 1e-7 <= abs(value) < 1e-6:
        return f"{value / 1e-6:.4g} µL"
    units = sorted({scale: unit for unit, scale in reversed(family.items()) if unit.isascii() and unit != "%"}.items(), reverse=True)
    scale, unit = next(((sc, u) for sc, u in units if abs(value) >= sc), units[-1])
    return f"{value / scale:.4g} {MICRO.sub('µ', unit)}"


def molarity(p: dict[str, Any]) -> dict[str, Any]:
    known = [k for k in ("mass", "volume", "mw", "conc") if p.get(k) is not None]
    if len(known) != 3:
        raise ValidationError("give exactly three of mass, volume, mw (g/mol), conc", code="CALC_INPUT")
    if "mass" not in known:
        g = _in(p, "conc", MOLAR) * _in(p, "volume", VOLUME) * _in(p, "mw")
        return {"mass": _show(g, MASS), "steps": [f"mass = conc × volume × MW = {_show(g, MASS)}"]}
    if "conc" not in known:
        m = _in(p, "mass", MASS) / _in(p, "mw") / _in(p, "volume", VOLUME)
        return {"conc": _show(m, MOLAR), "steps": [f"conc = mass ÷ MW ÷ volume = {_show(m, MOLAR)}"]}
    if "volume" not in known:
        v = _in(p, "mass", MASS) / _in(p, "mw") / _in(p, "conc", MOLAR)
        return {"volume": _show(v, VOLUME), "steps": [f"volume = mass ÷ MW ÷ conc = {_show(v, VOLUME)}"]}
    mw = _in(p, "mass", MASS) / _in(p, "conc", MOLAR) / _in(p, "volume", VOLUME)
    return {"mw": f"{mw:.5g} g/mol", "steps": [f"MW = mass ÷ conc ÷ volume = {mw:.5g} g/mol"]}


def dilution(p: dict[str, Any]) -> dict[str, Any]:
    c1, fam1 = _conc(p, "c1")
    c2, fam2 = _conc(p, "c2")
    if fam1 is not fam2:
        raise ValidationError("c1 and c2 must be the same kind of concentration", code="CALC_UNIT")
    if c2 > c1:
        raise ValidationError("c2 is above the stock c1: a dilution cannot concentrate", code="CALC_IMPOSSIBLE")
    v2 = _in(p, "v2", VOLUME)
    v1 = c2 * v2 / c1
    return {"v1": _show(v1, VOLUME), "diluent": _show(v2 - v1, VOLUME), "fold": f"{c1 / c2:.4g}",
            "steps": [f"V1 = C2 × V2 ÷ C1 = {_show(v1, VOLUME)} of stock",
                      f"add {_show(v2 - v1, VOLUME)} diluent to {_show(v2, VOLUME)} total ({c1 / c2:.4g}-fold)"]}


def serial(p: dict[str, Any]) -> dict[str, Any]:
    c0, fam = _conc(p, "start")
    f, n, v = _in(p, "factor"), int(_in(p, "steps", default=8)), _in(p, "volume", VOLUME)
    if f <= 1 or not 1 <= n <= 24:
        raise ValidationError("factor above 1 and 1-24 steps", code="CALC_INPUT")
    t = v / f
    rows = [{"tube": i + 1, "conc": _show(c0 / f ** (i + 1), fam)} for i in range(n)]
    return {"transfer": _show(t, VOLUME), "diluent_per_tube": _show(v - t, VOLUME), "tubes": rows,
            "steps": [f"put {_show(v - t, VOLUME)} diluent in each of {n} tubes",
                      f"move {_show(t, VOLUME)} from the stock into tube 1, mix, then {_show(t, VOLUME)} on each time",
                      f"discard {_show(t, VOLUME)} from the last tube so every tube holds {_show(v - t, VOLUME)}"]}


def seeding(p: dict[str, Any]) -> dict[str, Any]:
    stock = _in(p, "cells_per_ml")
    fmt = PlateFormat(str(p.get("plate", "96")))
    area, working = WELLS[fmt]
    per_well = _in(p, "per_cm2") * area if p.get("per_cm2") else _in(p, "per_well")
    vol = _in(p, "volume_per_well", VOLUME, default=f"{working} mL") * 1e3  # mL
    wells, extra = int(_in(p, "wells")), _in(p, "overage_pct", default=10) / 100
    cells = per_well * wells * (1 + extra)
    total_ml = vol * wells * (1 + extra)
    susp_ml = cells / stock
    if susp_ml > total_ml:
        raise ValidationError(f"the suspension ({stock:.3g}/mL) is too dilute for {per_well:.3g} cells in "
                              f"{vol * 1e3:.3g} µL: spin down and resuspend", code="CALC_IMPOSSIBLE")
    return {"cells_per_well": f"{per_well:.4g}", "suspension": _show(susp_ml / 1e3, VOLUME),
            "medium": _show((total_ml - susp_ml) / 1e3, VOLUME), "total": _show(total_ml / 1e3, VOLUME),
            "steps": [f"{per_well:.4g} cells × {wells} wells × {1 + extra:.2f} overage = {cells:.4g} cells",
                      f"{cells:.4g} ÷ {stock:.4g}/mL = {_show(susp_ml / 1e3, VOLUME)} of suspension",
                      f"top up with {_show((total_ml - susp_ml) / 1e3, VOLUME)} medium; "
                      f"{_show(vol / 1e3, VOLUME)} per well ({fmt.value}-well, {area} cm²)"]}


def hemocytometer(p: dict[str, Any]) -> dict[str, Any]:
    live, dead = _numbers(p, "live"), _numbers(p, "dead")
    df = _in(p, "dilution", default=2)
    if not live:
        raise ValidationError("live: the counts of each large square, comma-separated", code="CALC_INPUT")
    mean_live, mean_dead = sum(live) / len(live), (sum(dead) / len(dead) if dead else 0.0)
    per_ml = mean_live * df * 1e4
    viability = mean_live / (mean_live + mean_dead) * 100 if mean_live + mean_dead else 0.0
    out = {"cells_per_ml": f"{per_ml:.4g}", "viability_pct": f"{viability:.1f}",
           "steps": [f"mean {mean_live:.4g} live per square × dilution {df:g} × 10⁴ = {per_ml:.4g} cells/mL",
                     f"viability {mean_live:.4g} ÷ ({mean_live:.4g} + {mean_dead:.4g}) = {viability:.1f}%"]}
    if p.get("volume"):
        out["total_cells"] = f"{per_ml * _in(p, 'volume', VOLUME) * 1e3:.4g}"
    return out


def mastermix(p: dict[str, Any]) -> dict[str, Any]:
    """components: [{name, stock, final}] (concentrations) or [{name, per_reaction}] (a volume); water fills up."""
    n, extra = int(_in(p, "reactions")), _in(p, "overage_pct", default=10) / 100
    rxn, template = _in(p, "reaction_volume", VOLUME), _in(p, "template_volume", VOLUME, default="0 uL")
    k = n * (1 + extra)
    rows, used = [], template
    for c in p.get("components") or []:
        if c.get("per_reaction"):
            per = _in(c, "per_reaction", VOLUME)
        else:
            (final, ff), (stock, sf) = _conc(c, "final"), _conc(c, "stock")
            if ff is not sf:
                raise ValidationError(f"{c['name']}: stock and final are different kinds of concentration", code="CALC_UNIT")
            per = final / stock * rxn
        used += per
        rows.append({"component": c["name"], "per_reaction": _show(per, VOLUME), "mix": _show(per * k, VOLUME)})
    if used > rxn + 1e-12:
        raise ValidationError("the components and template add up to more than the reaction volume", code="CALC_IMPOSSIBLE")
    rows.insert(0, {"component": "water", "per_reaction": _show(rxn - used, VOLUME), "mix": _show((rxn - used) * k, VOLUME)})
    return {"reactions_made": f"{k:.3g}", "rows": rows, "aliquot": _show(rxn - template, VOLUME),
            "steps": [f"{n} reactions + {extra * 100:.0f}% = {k:.3g} reactions of mix",
                      f"aliquot {_show(rxn - template, VOLUME)} mix per tube, then {_show(template, VOLUME)} template"]}


def dna_moles(p: dict[str, Any]) -> dict[str, Any]:
    ng, bp = _in(p, "mass", MASS) * 1e9, _in(p, "length")
    double = str(p.get("strands", "ds")) == "ds"
    mw = bp * 617.96 + 36.04 if double else bp * 308.97 + 18.02
    pmol = ng / mw * 1e3
    return {"pmol": f"{pmol:.4g}", "mw": f"{mw:.5g} g/mol",
            "steps": [f"MW = {'617.96 × bp + 36.04' if double else '308.97 × nt + 18.02'} = {mw:.5g} g/mol",
                      f"{ng:.4g} ng ÷ MW × 1000 = {pmol:.4g} pmol"]}


def ligation(p: dict[str, Any]) -> dict[str, Any]:
    vec, vbp, ibp, ratio = _in(p, "vector_mass", MASS) * 1e9, _in(p, "vector_length"), _in(p, "insert_length"), _in(p, "ratio", default=3)
    ins = ratio * vec * ibp / vbp
    out = {"insert_ng": f"{ins:.4g}",
           "steps": [f"insert = {ratio:g} × {vec:.4g} ng × {ibp:g} bp ÷ {vbp:g} bp = {ins:.4g} ng"]}
    if p.get("insert_conc"):
        ul = ins / (_in(p, "insert_conc", MASS_CONC) * 1e3)
        out["insert_volume"] = f"{ul:.3g} µL"
        out["steps"].append(f"{ins:.4g} ng ÷ {_in(p, 'insert_conc', MASS_CONC) * 1e3:.4g} ng/µL = {ul:.3g} µL")
    return out


def protein_load(p: dict[str, Any]) -> dict[str, Any]:
    """samples: [{name, conc}] (µg/µL or mg/mL); load µg per lane in lane_volume with a Laemmli of buffer_x."""
    target, lane = _in(p, "load", MASS) * 1e6, _in(p, "lane_volume", VOLUME) * 1e6  # µg, µL
    bx = _in(p, "buffer_x", default=4)
    buffer = lane / bx
    rows = []
    for s in p.get("samples") or []:
        conc = _in(s, "conc", MASS_CONC)  # µg/µL
        vol = target / conc
        if vol > lane - buffer:
            raise ValidationError(f"{s['name']}: {target:g} µg needs {vol:.3g} µL, more than {lane - buffer:.3g} µL fits",
                                  code="CALC_IMPOSSIBLE")
        rows.append({"sample": s["name"], "sample_ul": f"{vol:.3g}", "buffer_ul": f"{buffer:.3g}", "water_ul": f"{lane - buffer - vol:.3g}"})
    return {"rows": rows, "steps": [f"{target:g} µg per lane ÷ concentration; {buffer:.3g} µL of {bx:g}X buffer; water to {lane:g} µL"]}


def dose(p: dict[str, Any]) -> dict[str, Any]:
    mg_kg, stock = _in(p, "dose"), _in(p, "stock", MASS_CONC)  # stock in mg/mL
    if not (weights := _numbers(p, "weights_g")):
        raise ValidationError("weights_g: the animals' weights in g, comma-separated", code="CALC_INPUT")
    rows = [{"weight_g": f"{w:g}", "mg": f"{mg_kg * w / 1e3:.4g}", "volume_ul": f"{mg_kg * w / 1e3 / stock * 1e3:.4g}",
             "ml_per_kg": f"{mg_kg / stock:.3g}"} for w in weights]
    return {"rows": rows, "steps": [f"mg = {mg_kg:g} mg/kg × weight; volume = mg ÷ {stock:g} mg/mL",
                                    f"every animal gets {mg_kg / stock:.3g} mL/kg"]}


def agarose(p: dict[str, Any]) -> dict[str, Any]:
    pct, ml = _in(p, "percent"), _in(p, "volume", VOLUME) * 1e3
    return {"agarose_g": f"{pct * ml / 100:.3g}", "steps": [f"{pct:g}% × {ml:g} mL ÷ 100 = {pct * ml / 100:.3g} g agarose"]}


def doubling(p: dict[str, Any]) -> dict[str, Any]:
    n0, n1, hours = _in(p, "start"), _in(p, "end"), _in(p, "hours")
    if n1 <= n0 or n0 <= 0:
        raise ValidationError("end count must be above a positive start count", code="CALC_IMPOSSIBLE")
    gens = math.log2(n1 / n0)
    return {"doubling_hours": f"{hours / gens:.3g}", "doublings": f"{gens:.3g}",
            "steps": [f"doublings = log2({n1:.4g} ÷ {n0:.4g}) = {gens:.3g}", f"{hours:g} h ÷ {gens:.3g} = {hours / gens:.3g} h"]}


CALCULATORS = {CalcKind.MOLARITY: molarity, CalcKind.DILUTION: dilution, CalcKind.SERIAL: serial,
               CalcKind.SEEDING: seeding, CalcKind.HEMOCYTOMETER: hemocytometer, CalcKind.MASTERMIX: mastermix,
               CalcKind.LIGATION: ligation, CalcKind.DNA_MOLES: dna_moles, CalcKind.PROTEIN_LOAD: protein_load,
               CalcKind.DOSE: dose, CalcKind.AGAROSE: agarose, CalcKind.DOUBLING: doubling}


def calc(kind: str, set_values: list[str] | None = None, file: str | None = None) -> dict[str, Any]:
    """`journal calc --kind K [--set key=value ...] [--file params.json]`: one calculation, nothing written."""
    params: dict[str, Any] = dict(load_json(file)) if file else {}
    for item in set_values or []:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValidationError(f"--set {item!r}: use key=value", code="CALC_INPUT")
        params[key.strip()] = value.strip()
    try:
        out = CALCULATORS[CalcKind(kind)](params)
    except KeyError as e:
        raise ValidationError(f"{e.args[0]} is needed", code="CALC_INPUT") from None
    except ZeroDivisionError:
        raise ValidationError("an input is zero where it divides", code="CALC_IMPOSSIBLE") from None
    return {"kind": kind, "inputs": params, **out}
