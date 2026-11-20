"""`plsi bio pool`: random-effects pooling of per-study effects on one scale, with the DerSimonian-Laird tau²; the
HKSJ interval (t, k-1 df, variance factor max(1, q)) is never narrower than DL's."""

from __future__ import annotations

import math
from typing import Any

from plsi.bio import figures
from plsi.bio.tables import number, rows
from plsi.bio.tuning import MIN_STUDIES
from plsi.distributions import CONFIDENCE, Z95, chi2_sf, norm_sf, t_quantile, t_two_sided
from plsi.errors import ValidationError
from plsi.vocab.bio import PoolModel


def pooled(effects: list[float], ses: list[float], model: PoolModel = PoolModel.HKSJ) -> dict[str, Any]:
    k = len(effects)
    if k < MIN_STUDIES:
        raise ValidationError(f"pooling needs at least {MIN_STUDIES} studies, got {k}", code="TOO_FEW_STUDIES")
    if any(se <= 0 for se in ses):
        raise ValidationError("every standard error is positive", code="BAD_TABLE")
    w = [1 / se**2 for se in ses]
    fixed = sum(wi * y for wi, y in zip(w, effects)) / sum(w)
    q = sum(wi * (y - fixed) ** 2 for wi, y in zip(w, effects))
    c = sum(w) - sum(wi**2 for wi in w) / sum(w)
    tau2 = max(0.0, (q - (k - 1)) / c) if c > 0 else 0.0
    wr = [1 / (se**2 + tau2) for se in ses]
    mu = sum(wi * y for wi, y in zip(wr, effects)) / sum(wr)
    if model is PoolModel.HKSJ:
        qh = sum(wi * (y - mu) ** 2 for wi, y in zip(wr, effects)) / (k - 1)
        se_mu = math.sqrt(max(1.0, qh) / sum(wr))
        crit, p = t_quantile(0.5 + CONFIDENCE / 2, k - 1), t_two_sided(mu / se_mu, k - 1)
    else:
        se_mu = math.sqrt(1 / sum(wr))
        crit, p = Z95, 2 * norm_sf(abs(mu) / se_mu)
    i2 = max(0.0, (q - (k - 1)) / q) if q > 0 else 0.0
    return {"model": model.value, "k": k, "effect": mu, "se": se_mu, "ci": [mu - crit * se_mu, mu + crit * se_mu],
            "p": min(1.0, p), "tau2": tau2, "i2": i2, "q": q, "q_p": chi2_sf(q, k - 1),
            "weights": [wi / sum(wr) for wi in wr]}


def pool(file: str, model: str = PoolModel.HKSJ.value, figure: str | None = None) -> dict[str, Any]:
    """Columns study, effect, se; returns the pooled estimate with its CI, tau², I² and each study's weight."""
    table = rows(file, ("study", "effect", "se"))
    effects = [number(r, "effect", f"line {i}") for i, r in enumerate(table, start=2)]
    ses = [number(r, "se", f"line {i}") for i, r in enumerate(table, start=2)]
    out = pooled(effects, ses, PoolModel(model))  # type: ignore[arg-type]
    out["studies"] = [{"study": r["study"], "effect": e, "se": s, "weight": w}
                      for r, e, s, w in zip(table, effects, ses, out.pop("weights"))]
    rows_ = [(r["study"], e, e - Z95 * s, e + Z95 * s) for r, e, s in zip(table, effects, ses)]  # type: ignore[operator]
    out["figures"] = figures.forest(rows_, (f"pooled ({out['model'].upper()})", out["effect"], *out["ci"]), figure,
                                    f"Pooled effect, {out['k']} studies (I² {out['i2']:.0%})", "effect (95% CI)",
                                    0.0) if figure else []
    return out
