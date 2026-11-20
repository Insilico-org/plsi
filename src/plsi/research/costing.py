"""What a move costs, read off the run log: the last observed cost of a move and the dearest move seen
(`estimate`, for whether the next move is affordable), and the median move (`typical`, for how far the remainder
reaches). The samples are the metered deltas of the costed log lines; the seed stands in until one is observed."""

from __future__ import annotations

from typing import Any

from plsi.research import runs
from plsi.research.tuning import SEED_COST


def _deltas(log: list[dict[str, Any]], move: str | None = None) -> list[float]:
    return [line["cost"]["delta"] for line in runs.costed(log)
            if (move is None or line.get("move") == move) and (line.get("cost") or {}).get("delta") is not None]


def estimate(log: list[dict[str, Any]], move: str) -> dict[str, Any]:
    """The last observed cost of this move, then the dearest move seen, then the seed."""
    own = _deltas(log, move)
    if own:
        return {"cost": max(own[-1], 0.0), "basis": f"last observed {move}"}
    seen = _deltas(log)
    if seen:
        return {"cost": max(max(seen), 0.0), "basis": "the dearest move observed so far"}
    return {"cost": SEED_COST, "basis": "seed estimate; no move has been observed yet"}


def typical(log: list[dict[str, Any]]) -> float:
    """The median cost of a move, for planning how far the remainder reaches; steadier than the last sample."""
    seen = sorted(_deltas(log))
    return seen[len(seen) // 2] if seen else SEED_COST
