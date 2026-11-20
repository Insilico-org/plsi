"""One ranked-enum mixin: members carry an ordinal `rank` and share a `top` of the strongest."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum, nonmember
from typing import Self


class RankedEnum(StrEnum):
    """A StrEnum whose members are ordered by strength. Set `_strongest_first = nonmember(True)` when members are
    listed strongest-first (rank counts down from the first member); leave it False when they are listed
    weakest-first (rank is the member index). `_empty` is the value `top` returns for no values (None by default)."""

    _strongest_first = nonmember(False)
    _empty = nonmember(None)

    @property
    def rank(self) -> int:
        members = list(type(self))
        index = members.index(self)
        return len(members) - 1 - index if self._strongest_first else index

    @classmethod
    def top(cls, values: Iterable[Self]) -> Self | None:
        """The strongest of values (`_empty` when there are none)."""
        default = cls(cls._empty) if cls._empty is not None else None
        return max(values, key=lambda m: m.rank, default=default)
