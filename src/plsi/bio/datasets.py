"""`plsi bio datasets`: the eligibility table (one row per public dataset considered), checked before any dataset
is opened. Refused: an included row without its counts, labels, origin or platform, an accession on two rows, a
replication set from a discovery set's origin, and no discovery set."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from plsi.bio.tables import number, rows
from plsi.errors import GateFailed, violation
from plsi.vocab.bio import BioRule, DatasetDecision, DatasetRole, StepRule

COLUMNS = ("accession", "role", "decision", "origin", "n_case", "n_control", "labels", "platform", "reason")


def _norm(origin: str) -> str:
    return " ".join(origin.lower().replace(",", " ").split())


def datasets(file: str) -> dict[str, Any]:
    table = rows(file, COLUMNS)
    bad: list[dict[str, str]] = []
    included: dict[str, list[dict[str, Any]]] = defaultdict(list)
    held, excluded, seen = [], [], set()
    for i, row in enumerate(table, start=2):
        where = f"line {i} ({row['accession'] or 'no accession'})"
        if row["accession"] in seen:
            bad.append(violation(where, BioRule.DUPLICATE_DATASET, "listed twice; one row per dataset"))
        seen.add(row["accession"])
        try:
            role, decision = DatasetRole(row["role"]), DatasetDecision(row["decision"])
        except ValueError:
            bad.append(violation(where, StepRule.VOCABULARY, f"role one of {', '.join(r.value for r in DatasetRole)}; "
                                 f"decision one of {', '.join(d.value for d in DatasetDecision)}"))
            continue
        if not row["reason"]:
            bad.append(violation(where, BioRule.ELIGIBILITY_INCOMPLETE, "every decision gives its reason"))
        if decision is DatasetDecision.EXCLUDE:
            excluded.append({"accession": row["accession"], "reason": row["reason"]})
            continue
        if decision is DatasetDecision.HOLD:
            held.append({"accession": row["accession"], "role": role.value, "reason": row["reason"]})
            continue
        missing = [c for c in ("accession", "origin", "labels", "platform") if not row[c]]
        counts = [number(row, c, where, optional=True) for c in ("n_case", "n_control")]
        needs = missing + (["case and control counts"] if any(c is None or c < 1 for c in counts) else [])
        if needs:
            bad.append(violation(where, BioRule.ELIGIBILITY_INCOMPLETE, f"an included set needs {', '.join(needs)}",
                                 "missing means missing: hold it until the metadata say"))
            continue
        included[role.value].append({"accession": row["accession"], "origin": row["origin"],
                                     "n_case": int(counts[0]), "n_control": int(counts[1]),
                                     "labels": row["labels"], "platform": row["platform"]})
    discovery = {_norm(d["origin"]): d["accession"] for d in included[DatasetRole.DISCOVERY.value]}
    if not discovery and not bad:
        bad.append(violation("role", BioRule.ELIGIBILITY_INCOMPLETE, "no discovery set is included"))
    for rep in included[DatasetRole.REPLICATION.value]:
        if (key := _norm(rep["origin"])) in discovery:
            bad.append(violation(rep["accession"], BioRule.SHARED_ORIGIN,
                                 f"shares origin '{rep['origin']}' with discovery {discovery[key]}: not independent",
                                 "make it exploratory, or find a set from another origin"))
    if bad:
        raise GateFailed(bad, "the eligibility table is not ready")
    return {"included": dict(included), "held": held, "excluded": excluded}
