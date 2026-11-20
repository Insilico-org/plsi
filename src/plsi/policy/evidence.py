"""Live evidence search and the verification ledger (public re-export).

The per-source live search lives in `sources`, the verification ledger in `ledger`, and the shared
source-record primitives in `records`. This module keeps the public API stable.
"""

from __future__ import annotations

from plsi import net
from plsi.policy.ledger import (CAP_AUTHORS, CAP_TITLE, CHECKS, LEDGER_MAX_AGE_DAYS, NAMED_AUTHORS, Found,
                                is_verified, latest_verification, ledger_path, verify)
from plsi.policy.records import (CITED_AT, ID_PATTERNS, RETRACTED, Result, cite_url, label_query, label_title)
from plsi.policy.sources import MAX_RESULTS, SOURCES, search

__all__ = [
    "CAP_AUTHORS", "CAP_TITLE", "CHECKS", "CITED_AT", "Found", "ID_PATTERNS", "LEDGER_MAX_AGE_DAYS",
    "MAX_RESULTS", "NAMED_AUTHORS", "RETRACTED", "Result", "SOURCES", "cite_url", "is_verified",
    "label_query", "label_title", "latest_verification", "ledger_path", "net", "search", "verify",
]
