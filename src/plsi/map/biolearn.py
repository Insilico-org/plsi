"""biolearn adapter: every biolearn aging clock through one generic path.

A clock is a gallery model of a supported type whose output is measured in years ("Age (Years)",
"Aging Rate (Years/Year)"). `run` imputes missing CpGs once per imputation reference (each model's biolearn
default) and then evaluates every requested clock on the imputed sample, so a projection loads each
reference once instead of once per clock.

biolearn imports torch at module import, although only its deep models use it; when torch is not installed,
an inert stand-in is registered so the linear clocks load without the multi-hundred-MB dependency.
"""

from __future__ import annotations

import contextlib
import importlib.util
import math
import re
import sys
import types
import warnings
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from plsi.errors import DependencyMissing
from plsi.vocab import Sex

HINT = 'pip install -e ".[clocks]"'
SUPPORTED_TYPES = frozenset({"LinearMethylationModel", "GrimageModel"})
_YEARS = re.compile(r"\(years(?:/year)?\)", re.I)
_REFERENCES = {"sesame_450k": ("sesame_450k_median.csv", "median"), "dunedin": ("DunedinPACE_Gold_Means.csv", "mean")}
_SEX = {Sex.F: 0, Sex.M: 1}


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """biolearn prints and warns; stdout carries the CLI envelope."""
    with warnings.catch_warnings(), contextlib.redirect_stdout(sys.stderr):
        warnings.simplefilter("ignore")
        yield


def _torch_standin() -> None:
    if "torch" in sys.modules or importlib.util.find_spec("torch") is not None:
        return
    torch = types.ModuleType("torch")
    torch.Tensor = type("Tensor", (), {})  # type: ignore[attr-defined]
    nn = types.ModuleType("torch.nn")
    nn.Module = type("Module", (), {})  # type: ignore[attr-defined]
    nn.functional = types.ModuleType("torch.nn.functional")  # type: ignore[attr-defined]
    torch.nn = nn  # type: ignore[attr-defined]
    sys.modules.update({"torch": torch, "torch.nn": nn, "torch.nn.functional": nn.functional})  # type: ignore[attr-defined]


@lru_cache(maxsize=1)
def _gallery() -> Any:
    try:
        _torch_standin()
        with _quiet():
            from biolearn.model_gallery import ModelGallery

            return ModelGallery()
    except (ImportError, OSError) as exc:  # OSError: a broken numpy binary
        raise DependencyMissing(f"biolearn is not importable: {exc}", hint=HINT) from None


def available() -> bool:
    try:
        _gallery()
        return True
    except DependencyMissing:
        return False


@lru_cache(maxsize=1)
def clocks() -> list[dict[str, Any]]:
    """[{name, year, tissue, output, unit, source, usage_note}] for every biolearn aging clock, sorted by name."""
    out = []
    for name, d in _gallery().model_definitions.items():
        output = str(d.get("output") or "")
        if d["model"]["type"] in SUPPORTED_TYPES and _YEARS.search(output):
            out.append({"name": name, "year": d.get("year"), "tissue": d.get("tissue"), "output": output,
                        "unit": "a/a" if "/year" in output.lower() else "a", "source": d.get("source"),
                        "usage_note": (d.get("usage") or {}).get("commercial")})
    return sorted(out, key=lambda c: c["name"].lower())


@lru_cache(maxsize=4)
def _reference(method: str) -> Any:
    import pandas as pd
    from biolearn.util import get_data_file

    file, column = _REFERENCES[method]
    return pd.read_csv(get_data_file(file), index_col=0)[column]


def _value(result: Any, sample: str) -> float:
    import pandas as pd

    if isinstance(result, pd.DataFrame):
        result = result["Predicted"] if "Predicted" in result.columns else result.iloc[:, 0]
    value = float(result.loc[sample])
    if not math.isfinite(value):
        raise ValueError("non-finite value")
    return value


def run(names: list[str], betas: Any, *, age: float | None, sex: Sex) -> dict[str, float | str]:
    """Evaluate clocks on a one-sample beta matrix (pandas DataFrame, CpG index x 1 column).
    -> {name: value, or an error message string for a clock that could not be computed}."""
    import pandas as pd
    from biolearn.data_library import GeoData
    from biolearn.imputation import hybrid_impute

    gallery = _gallery()
    sample = betas.columns[0]
    meta = pd.DataFrame({"age": [age], "sex": [_SEX.get(sex, float("nan"))]}, index=[sample])
    groups: dict[str, list[str]] = {}
    out: dict[str, float | str] = {}
    for name in names:
        if name not in gallery.model_definitions:
            out[name] = f"unknown biolearn model {name!r}"
        else:
            groups.setdefault(gallery.model_definitions[name]["model"].get("default_imputation", "sesame_450k"), []).append(name)
    with _quiet():
        for method, group in groups.items():
            models = {n: gallery.get(n, imputation_method="none") for n in group}
            if method in _REFERENCES:
                required = sorted(set().union(*(m.methylation_sites() for m in models.values())))
                dnam = hybrid_impute(betas, _reference(method), required)
            else:
                dnam = betas
            geo = GeoData(meta, dnam)
            for n, model in models.items():
                try:
                    out[n] = _value(model.predict(geo), sample)
                except Exception as exc:  # noqa: BLE001 - one clock failing must not hide the others
                    out[n] = f"biolearn {n} failed: {exc}"
    return out
