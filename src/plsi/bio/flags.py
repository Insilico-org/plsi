"""A check's flags: each is returned in the check's `flags` and warned once; `BLOCKING` flags stop a step from
being recorded as supported (`plsi bio step`)."""

from __future__ import annotations

from plsi import errors
from plsi.vocab.bio import BioRule

BLOCKING = frozenset({BioRule.NULL_AS_GOOD, BioRule.NULL_MISSPECIFIED, BioRule.SHARED_ORIGIN, BioRule.THIN_OVERLAP,
                      BioRule.LIMIT_EXCEEDED, BioRule.ORDER_UNSTABLE, BioRule.MANIFEST_DRIFT, BioRule.SET_SIZE_BIAS,
                      BioRule.CONTROL_MISSED, BioRule.KO_NOT_PERTURBED})


def raise_flag(flags: list[str], rule: BioRule, message: str) -> None:
    if rule.value not in flags:
        flags.append(rule.value)
        errors.warn(rule.value, message)
