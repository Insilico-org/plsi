"""`plsi bio step`: the gate that closes an analysis step. The step file's short methods, key numbers, criterion and
verdict are checked against the frozen protocol, written to `results/steps/<step>.md` and logged in
`results/steps.jsonl`; the page's text comes back as the chat block."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from plsi import clock
from plsi.bio import protocol
from plsi.bio.flags import BLOCKING
from plsi.bio.tuning import MAX_CRITERION, MAX_METHODS, MAX_RESULTS
from plsi.errors import GateFailed, ValidationError, violation
from plsi.vocab.bio import AnalysisVerdict, BioRule, StepRule

_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _frozen_criterion(root: Path, step: str) -> str | None:
    path = root / "protocol" / "protocol.json"
    criteria = json.loads(path.read_text(encoding="utf-8")).get("criteria") if path.is_file() else None
    return criteria.get(step) if isinstance(criteria, dict) else None


def _inside(root: Path, rel: str) -> bool:
    path = (root / rel).resolve()
    return path.is_file() and path.is_relative_to(root.resolve())


def _result_ok(r: Any) -> tuple[bool, bool]:
    """(a {name, value} result, its interval [low, high] holds the value)."""
    if not isinstance(r, dict) or not r.get("name") or "value" not in r:
        return False, True
    ci, value = r.get("ci"), r["value"]
    if ci is None:
        return True, True
    ok = (isinstance(ci, list) and len(ci) == 2 and all(isinstance(c, (int, float)) for c in ci) and ci[0] <= ci[1]
          and (not isinstance(value, (int, float)) or ci[0] <= value <= ci[1]))
    return True, ok


def _check(root: Path, doc: dict[str, Any], frozen: bool) -> list[dict[str, str]]:
    bad: list[dict[str, str]] = []
    step, results = str(doc.get("step") or ""), doc.get("results")
    if not _SLUG.fullmatch(step):
        bad.append(violation("step", StepRule.STEP_ID, "a lowercase slug such as `03-de-discovery`"))
    if not doc.get("title"):
        bad.append(violation("title", StepRule.REQUIRED, "name the step in a few words"))
    if not 0 < len(str(doc.get("methods") or "").strip()) <= MAX_METHODS:
        bad.append(violation("methods", StepRule.SHORT_METHODS, f"1-{MAX_METHODS} characters: what ran, on what"))
    if not isinstance(results, list) or not 0 < len(results) <= MAX_RESULTS:
        bad.append(violation("results", StepRule.KEY_NUMBERS, f"1-{MAX_RESULTS} results, each {{name, value}}"))
        results = []
    for i, r in enumerate(results):
        shaped, interval = _result_ok(r)
        if not shaped:
            bad.append(violation(f"results[{i}]", StepRule.KEY_NUMBERS, "{name, value[, ci, n, unit]}"))
        elif not interval:
            bad.append(violation(f"results[{i}]", StepRule.INTERVAL, "ci is [low, high] and holds the value"))
    bad += [violation(f, StepRule.FILE_IN_PROJECT, "not a file inside the analysis folder")
            for f in [*(doc.get("files") or []), *(doc.get("figures") or [])] if not _inside(root, f)]
    bad += [violation(f, StepRule.FILE_IN_PROJECT, "a figure is a .png (the --figure output)")
            for f in doc.get("figures") or [] if not str(f).lower().endswith(".png")]
    bad += [violation(f, StepRule.FILE_IN_PROJECT, "a .png goes in `figures`, so the page shows it")
            for f in doc.get("files") or [] if str(f).lower().endswith(".png")]
    if len(str(doc.get("criterion") or "")) > MAX_CRITERION:
        bad.append(violation("criterion", StepRule.SHORT_CRITERION, f"at most {MAX_CRITERION} characters: the rule "
                             "and its numbers; the full protocol is in protocol.md"))
    if doc.get("verdict") not in tuple(AnalysisVerdict):
        return bad + [violation("verdict", StepRule.VERDICT, f"one of {', '.join(AnalysisVerdict)}")]
    criterion, pinned = str(doc.get("criterion") or "").strip(), _frozen_criterion(root, step)
    if pinned is not None and criterion != pinned.strip() and not doc.get("post_hoc"):
        bad.append(violation("criterion", StepRule.CRITERION_FROZEN, "differs from protocol.json for this step",
                             "an amendment and a new freeze, or mark the step post_hoc"))
    if doc["verdict"] == AnalysisVerdict.SUPPORTED:
        blocking = sorted(BLOCKING & {BioRule(f) for f in doc.get("flags") or [] if f in tuple(BioRule)})
        reasons = [(not criterion, "no criterion was frozen for it"), (not frozen, "the protocol is not frozen"),
                   (bool(doc.get("post_hoc")), "a post-hoc step cannot support"),
                   (bool(blocking), f"flagged {', '.join(blocking)}")]
        bad += [violation("verdict", StepRule.SUPPORTED_EARNED, why) for hit, why in reasons if hit]
    return bad


def _page(doc: dict[str, Any], manifest: str | None) -> str:
    head = f"Step `{doc['step']}` · {clock.now().date().isoformat()} · " + (
        f"protocol `{manifest[:12]}`" if manifest else "before the freeze") + (" · **post hoc**" if doc.get("post_hoc") else "")
    lines = [f"# {doc['title']}", "", head, ""]
    lines += [f"**Question.** {doc['question']}", ""] if doc.get("question") else []
    lines += [f"**Methods.** {doc['methods'].strip()}", ""]
    lines += [f"**Data.** {', '.join(map(str, doc['data']))}", ""] if doc.get("data") else []
    lines += ["| Result | Value | 95% CI | n |", "|---|---|---|---|"]
    for r in doc["results"]:
        ci = f"{r['ci'][0]:.3g} to {r['ci'][1]:.3g}" if r.get("ci") else ""
        value = f"{r['value']:.4g}" if isinstance(r["value"], float) else str(r["value"])
        lines.append(f"| {r['name']} | {value}{' ' + r['unit'] if r.get('unit') else ''} | {ci} | {r.get('n', '')} |")
    lines += [line for f in doc.get("figures") or []
              for line in ("", f"![{Path(f).stem}](../../{f})")]  # the page sits in results/steps/
    verdict = doc["verdict"].replace("_", " ")
    lines += ["", f"**Criterion.** {doc.get('criterion') or 'none frozen'}", "",
              f"**Verdict: {verdict}.**" + (f" {doc['why']}" if doc.get("why") else "")]
    for label, key in (("Flags", "flags"), ("Files", "files"), ("Next", "next")):
        if value := doc.get(key):
            text = ", ".join(f"`{v}`" if key == "files" else str(v) for v in value) if isinstance(value, list) else value
            lines += ["", f"**{label}.** {text}"]
    return "\n".join(lines) + "\n"


def step(dir: str, file: str) -> dict[str, Any]:
    """Check and record one analysis step; returns the page path and its text as `chat`."""
    root = protocol.project_root(dir)
    try:
        doc = json.loads(sys.stdin.read() if file == "-" else Path(file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"the step file is not readable JSON: {exc}", code="BAD_STEP") from None
    if not isinstance(doc, dict):
        raise ValidationError("the step file is one JSON object", code="BAD_STEP")
    frozen = (root / "protocol" / protocol.MANIFEST).is_file()
    manifest = protocol.verify(dir)["manifest_sha256"] if frozen else None  # drift refuses the step
    if bad := _check(root, doc, frozen):
        raise GateFailed(bad, "the step cannot be recorded")
    page = _page(doc, manifest)
    out = root / "results" / "steps" / f"{doc['step']}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    entry = {"step": doc["step"], "at": clock.now().isoformat(), "verdict": doc["verdict"], "manifest": manifest,
             "post_hoc": bool(doc.get("post_hoc")), "flags": doc.get("flags") or [], "page": out.relative_to(root).as_posix()}
    with (root / "results" / "steps.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    return {**entry, "chat": page, "figures": [(root / f).resolve().as_posix() for f in doc.get("figures") or []]}
