"""`plsi bio freeze` and `plsi bio verify`: an analysis's frozen protocol. Every file under `protocol/` and
`scripts/` is hashed into `protocol/MANIFEST.sha256` (the `sha256sum -c` format) and each freeze is logged in
`protocol/freezes.jsonl`; freezing a stage again needs a changed `protocol/amendments.md`."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from plsi import clock
from plsi.bio.tuning import MAX_CRITERION
from plsi.errors import GateFailed, NotFound, ValidationError, violation
from plsi.vocab.bio import BioRule, FreezeStage

MANIFEST, LOG, AMENDMENTS, DISCOVERY_OUT = "MANIFEST.sha256", "freezes.jsonl", "amendments.md", "discovery_frozen.json"
FROZEN_DIRS = ("protocol", "scripts")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_root(dir: str) -> Path:
    """The analysis folder; refused unless it holds protocol/."""
    root = Path(dir)
    if not (root / "protocol").is_dir():
        raise NotFound(f"{root} has no protocol/ folder", hint="the analysis folder holds protocol/ and scripts/")
    return root


def _files(root: Path) -> list[Path]:
    return [p for sub in FROZEN_DIRS for p in sorted((root / sub).rglob("*"))
            if p.is_file() and p.name not in {MANIFEST, LOG} and "__pycache__" not in p.parts
            and not p.name.startswith(".")]


def _log(root: Path) -> list[dict[str, Any]]:
    path = root / "protocol" / LOG
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    return [json.loads(line) for line in lines if line.strip()]


def _manifest(root: Path) -> tuple[dict[str, str], str]:
    """{relative path: sha256} and the manifest's own hash; MANIFEST_CORRUPT for a line not `<hash>  <path>`."""
    text = (root / "protocol" / MANIFEST).read_text(encoding="utf-8")
    listed = {}
    for n, line in enumerate(text.splitlines(), start=1):
        digest, sep, rel = line.partition("  ")
        if not sep or len(digest) != 64 or not rel:
            raise ValidationError(f"protocol/{MANIFEST} line {n} is not `<sha256>  <path>`", code="MANIFEST_CORRUPT",
                                  hint="never edit the manifest; freeze again after an amendment")
        listed[rel] = digest
    return listed, hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check_criteria(root: Path) -> None:
    """Every criterion in protocol.json fits a step page (MAX_CRITERION), so a step never has to reword it."""
    path = root / "protocol" / "protocol.json"
    criteria = json.loads(path.read_text(encoding="utf-8")).get("criteria") if path.is_file() else None
    long = sorted(k for k, v in criteria.items() if len(str(v)) > MAX_CRITERION) if isinstance(criteria, dict) else []
    if long:
        raise ValidationError(f"criteria over {MAX_CRITERION} characters: {', '.join(long)}", code="CRITERION_TOO_LONG",
                              hint="the rule and its numbers in one or two sentences; the conditions go in protocol.md")


def freeze(dir: str, stage: str = FreezeStage.PROTOCOL.value) -> dict[str, Any]:
    """Write the manifest for `stage`; its hash is posted before any held-out data are read."""
    root, stage = project_root(dir), FreezeStage(stage)
    _check_criteria(root)
    done = _log(root)
    amend = root / "protocol" / AMENDMENTS
    amend_sha = _sha(amend) if amend.is_file() else None
    if stage is FreezeStage.DISCOVERY:
        if not any(f["stage"] == FreezeStage.PROTOCOL for f in done):
            raise ValidationError("freeze the protocol before discovery", code="NOT_FROZEN",
                                  hint=f"plsi bio freeze --dir {dir}")
        if not (root / "protocol" / DISCOVERY_OUT).is_file():
            raise ValidationError(f"write protocol/{DISCOVERY_OUT} (the derived lists, thresholds and rules) first",
                                  code="NO_DISCOVERY_OUTPUT")
    same = [f for f in done if f["stage"] == stage]
    if same and same[-1]["amendments_sha256"] == amend_sha:
        raise ValidationError(f"stage {stage} is frozen; record the change in protocol/{AMENDMENTS} (date, what, why) "
                              "before freezing again", code="AMENDMENT_NEEDED")
    text = "".join(f"{_sha(p)}  {p.relative_to(root).as_posix()}\n" for p in _files(root))
    (root / "protocol" / MANIFEST).write_text(text, encoding="utf-8")
    entry = {"stage": stage.value, "at": clock.now().isoformat(), "files": text.count("\n"),
             "manifest_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "amendments_sha256": amend_sha}
    with (root / "protocol" / LOG).open("a", encoding="utf-8") as out:
        out.write(json.dumps(entry) + "\n")
    return entry


def verify(dir: str) -> dict[str, Any]:
    """GATE_FAILED with every frozen file changed, missing or added since the last freeze."""
    root = project_root(dir)
    if not (root / "protocol" / MANIFEST).is_file():
        raise ValidationError("nothing frozen yet", code="NOT_FROZEN", hint=f"plsi bio freeze --dir {dir}")
    listed, manifest_sha = _manifest(root)
    found = [violation(rel, BioRule.MANIFEST_DRIFT, "frozen file is missing" if not (root / rel).is_file()
                       else "frozen file changed")
             for rel, digest in listed.items() if not (root / rel).is_file() or _sha(root / rel) != digest]
    found += [violation(rel, BioRule.MANIFEST_DRIFT, "file added after the freeze",
                        f"record it in protocol/{AMENDMENTS}, then freeze again")
              for p in _files(root) if (rel := p.relative_to(root).as_posix()) not in listed]
    if found:
        raise GateFailed(found, "the frozen protocol changed")
    return {"files": len(listed), "stage": (_log(root) or [{}])[-1].get("stage"), "manifest_sha256": manifest_sha}
