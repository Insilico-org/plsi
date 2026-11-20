"""The hint a Mothership gate refusal carries: what each rule it names reads as, and the usual way past it. Built from
the violations' rules and paths only, never from the text refused (a violation never echoes what it found)."""

from __future__ import annotations

import re

from plsi.mothership.note import FINDINGS, MAX_LIST, MAX_REPORT, MAX_TAGS, MAX_TEXT
from plsi.mothership.scan import MAX_STRING, PATTERNS
from plsi.vocab import EvidenceClass
from plsi.vocab.targets import AgingHallmark

# what the identifying-pattern rules of plsi.mothership.scan.PATTERNS match, in plain words
HINTS = {
    "id_number": "8 or more characters of digits joined by spaces, dots, dashes or brackets read as an ID or phone "
                 "number, so an interval, a decimal range or a mean (SD) does too. In a claim, method or other short "
                 "field give the estimate alone (HR 0.71) and put the interval in `report`, where intervals, decimal "
                 "ranges, mean (SD) and p-values pass; in `report` and data files write a citation as PMID 12345678 "
                 "and remove any other long number",
    "exact_date": "a date, or what reads as one: a word that starts like a month (jan...dec, so also markers, "
                  "separate, decades, declined) with a number on each side or two numbers after it ('4 markers 12', "
                  "'declined 2, 12'), or a three-part version such as 2.7.10 (read as day.month.year). Send no exact "
                  "date; reword so the numbers do not sit around such a word, and give a version as major.minor "
                  "(STAR 2.7)",
    "url": "a link, www., or a word ending in a domain suffix (.io, .ai, .com, .org, .me, .app, .dev ...), which module "
           "names such as plotly.io match too. Cite a source by its kind and id, never a link (in `report` a doi.org "
           "link passes), and name a package without its module (plotly, pandas)",
    "email": "an email address: remove it",
    "internal_id": "a PLSI event or subject id (evt_..., s_...): remove it",
    "embedded_data": "a data: URI or a long base64 run: remove it (in the note's text a hidden picture is removed for "
                     "you; in a data file it is refused)",
    "instance_name": "the name of one of the user's PLSI instances, in any case, as a whole word (a hyphen breaks a "
                     "word: self-reported names an instance called self): reword",
    "formula": "a CSV or TSV cell that starts with =, +, - or @ and is not a number reads as a spreadsheet formula, "
               "and the Mother refuses it too: write a strand as plus/minus or 1/-1, a missing value as an empty cell "
               "or NA, a genotype as ko/ko or wt/ko",
    "too_long": f"over its length limit ({MAX_STRING:,} characters a text, {MAX_REPORT:,} the report): shorten it",
    "bad_context": f"an item's context outside its form: each text 1-{MAX_TEXT} characters, each list 1-{MAX_LIST} "
                   "entries, a support, against or risks entry citing one of the item's own sources",
}

# what `bad_context` asks of the field a violation names (the last field of its path); HINTS["bad_context"] otherwise
CONTEXT = {
    "question": f"question is a text of 1-{MAX_TEXT} characters",
    "evidence_class": "evidence_class is one of " + ", ".join(EvidenceClass),
    "hallmarks": "hallmarks are distinct, each one of " + ", ".join(AgingHallmark),
    "tags": f"tags are 1-{MAX_TAGS} distinct MeSH descriptors, as plsi mothership note fills them from their ids",
    **dict.fromkeys(FINDINGS, f"support, against and risks hold 1-{MAX_LIST} entries {{source, finding}}, each "
                              f"citing one of the item's own sources, the finding 1-{MAX_TEXT} characters"),
    "limits": f"limits hold 1-{MAX_LIST} texts of 1-{MAX_TEXT} characters",
    "model_output": f"model_output holds 1-{MAX_LIST} entries {{model, finding}}, the model a name with a letter, the "
                    f"finding 1-{MAX_TEXT} characters",
    "report": "report is a text that is not empty",
}
# Every identifying-pattern rule of scan (and the instance-name rule) must have a hint here: a rename in scan then
# fails loudly at import instead of silently dropping a hint users rely on.
assert {*PATTERNS, "instance_name"} <= set(HINTS), f"identifying rules without a hint: {set(PATTERNS) - set(HINTS)}"

FIELD = re.compile(r"[a-z_]+")


def _field(path: str) -> str:
    names = FIELD.findall(path)
    return names[-1] if names else ""


def _says(rule: str, paths: list[str]) -> str:
    if rule != "bad_context":
        return HINTS[rule]
    return "; ".join(dict.fromkeys(CONTEXT.get(_field(p), HINTS[rule]) for p in paths))


def hint(violations: list[dict[str, str]]) -> str | None:
    """One line per rule named in `violations` that has a hint, in the order first named; None when none has.
    `bad_context` says what each field it names must hold, the allowed values for evidence_class and hallmarks."""
    rules: dict[str, list[str]] = {}
    for v in violations:
        rules.setdefault(v["rule"], []).append(v["path"])
    return "; ".join(f"{rule}: {_says(rule, paths)}" for rule, paths in rules.items() if rule in HINTS) or None
