"""Which of the user's own keys bear on target work, what each adds, and what is left of today's oracle cap.

Nothing here is called during a gather and nothing here spends anything. Every question in `targets/evaluate`
is answerable from the free sources; a platform read is optional, goes out through `plsi oracle ...` (where
the daily cap is enforced) and is recorded as a `platform_reads` entry, which is model_derived and never a
citation.
"""

from __future__ import annotations

from typing import Any

from plsi import keys
from plsi.policy import oracles
from plsi.vocab.targets import ExternalSource

# A platform's key is the user's own bearer token (`oracles.token_env`, read from env / .env).
FOR_TARGETS: tuple[dict[str, Any], ...] = (
    {"key": oracles.token_env(ExternalSource.PANDAOMICS), "service": ExternalSource.PANDAOMICS.value,
     "adds": "the platform's own record and rankings for a target, on request",
     "command": "plsi oracle pandaomics tools, then plsi oracle pandaomics call --tool <t> --file args.json. "
                "`plsi targets dossier` never calls it",
     "enters_as": "one `platform_reads` entry: model_derived, never a citation, and refused unless the "
                  "egress ledger shows the platform was asked",
     "read_first": "targets/pandaomics"},
    {"key": oracles.token_env(ExternalSource.PANDACLAW), "service": ExternalSource.PANDACLAW.value,
     "adds": "an agent that reads the literature and pipeline pages for a target and writes it up",
     "command": "plsi oracle pandaclaw-skills, then plsi oracle pandaclaw --file ask.json --out "
                "<PLSI_HOME>/work/<thread>/pandaclaw_<topic>_<n>.md",
     "enters_as": "one `platform_reads` entry: model_derived, and every identifier in its prose still has "
                  "to verify before it may be cited",
     "read_first": "targets/pandaomics"},
    {"key": "NCBI_API_KEY", "service": None,
     "adds": "PubMed verification at 10 requests a second instead of 3, which target-refusal-4 uses for "
             "every identifier in an assessment",
     "command": "used automatically by plsi evidence verify; nothing to call",
     "enters_as": "not a source: it only raises the rate on one already used"},
    {"key": "OPENFDA_API_KEY", "service": None,
     "adds": "openFDA label lookups at a higher daily rate; a label set id is a citation `assess` accepts",
     "command": "used automatically by plsi evidence verify --kind label; nothing to call",
     "enters_as": "not a source: it only raises the rate on one already used"},
)


def available() -> dict[str, Any]:
    """Which of these keys are set, what each would add, and today's oracle allowance. The same shape is
    returned whether or not anything is set."""
    present = keys.status()
    spent = oracles.budget()
    cap = spent["cap_per_oracle_per_day"]
    unlocked, absent = [], []
    for entry in FOR_TARGETS:
        row = {k: v for k, v in entry.items() if k != "service"}
        if not present.get(entry["key"]):
            absent.append({"key": entry["key"], "would_add": entry["adds"]})
            continue
        if service := entry["service"]:
            used = spent["spent_today"].get(service, 0)
            row["today"] = {"spent": used, "remaining": max(0, cap - used), "cap": cap}
        unlocked.append(row)
    return {
        "unlocked": unlocked,
        "not_set": absent,
        "budget": {"cap_per_oracle_per_day": cap, "spent_today": spent["spent_today"],
                   "raise_it": spent["raise_it"]},
        "rule": "every question in targets/evaluate is answerable without any of these. A platform read is "
                "model_derived, never stronger than a curated record, and goes out through plsi oracle, "
                "where the daily cap is enforced.",
        "note": None if unlocked else "no platform key is set; nothing in targets needs one.",
    }
