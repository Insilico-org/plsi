---
name: explain
description: Use as PLSI Research Autopilot when `plsi research next` says the move is `explain` - put the competing accounts of the evidence on the table, the boring ones first, each with what we would see if it were false.
---

# Explain

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Autopilot**. Writes `hypothesis` nodes; the
shape is in `shared/research-graph`.

`next` has handed you the question, every finding that bears on it, and each one's `note`. Nothing here needs a
search.

Explain is due only where findings exist. Where they say nothing useful, explaining the absence is legitimate (a
tooling limit, a question nobody asked, a result only in tables this loop cannot read), and each is a falsifiable
candidate. If the honest answer is that the search was wrong, do a gather instead and save that.

When the candidates feel thin, or you cannot tell whether a falsifier is any good, read `autopilot/good-hypothesis`.

## 1. The boring three first, as a checklist

Before any mechanism, consider:

1. **Nothing**: chance, or no real effect.
2. **Confounding**: something else accounts for it.
3. **Artifact**: measurement, selection or reporting produced it.

Then the mechanistic candidates. Write the boring ones that are live as nodes and name the ones you dismissed in
`dropped`, with why.

## 2. Every candidate that survives the separating test, each with `if_false`

There is no fixed number. **Two candidates that no observation could separate are one** (`autopilot/test` §3):
run that test over every pair, merge what it catches, and keep what survives. A question that needs many more is
split in Ask, not crowded here. `next` hands back `dropped` in `already_tried`, so a set-aside candidate stays set
aside.

**Every candidate records what we would see if it were wrong** (refusal 2). An `if_false` must name something
observable: *"the symptom began before the prescription date in the user's own log"*, not *"the hypothesis would
not hold"*.

Fill `tested_by` only with a question that **already exists** (refusal 6 rejects a link to a missing node).
Otherwise leave it empty and say in the body what would settle it; Test fills the link when it creates that
question. Never point `tested_by` back at the question that proposed the hypothesis.

## 3. Sharpening, not nesting

Hypotheses do not nest. A candidate sharpened after new evidence is a **new** hypothesis under the same question,
with the old one closed `superseded` and cited. Structure lives in the question tree.

## 4. Read your way to hypotheses

A topic holds tens of findings, far too few for graph-structure hypothesis generation; candidates come from
reading the findings. The graph stops you asking the same question twice and counts what you find.

## 5. Save

`nodes` of `kind: hypothesis`, each with its `question`, `if_false`, `tested_by` where you know it, and a body of
one or two lines saying what it claims. In `dropped`, the candidates you set aside, with why.

## Rules

- You never write a verdict, and never a verdict word as a status (refusal 7).
- Do not propose a candidate nothing could test. Put it in `open` as a direction that needs a measurement nobody
  has.
