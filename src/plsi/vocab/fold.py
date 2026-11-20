"""Fold a label to its comparison form: lower-case letters and digits only."""

from __future__ import annotations

import re
from typing import Any


def fold(text: Any) -> str:
    """Lower-case letters and digits only, so `ABC-123`, `abc 123` and `abc123` compare equal."""
    return re.sub(r"[^a-z0-9]+", "", str(text or "").lower())
