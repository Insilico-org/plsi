---
name: test
description: Use as PLSI Research Autopilot when `plsi research next` says the move is `test` - link the evidence to the candidates, ask the context question before believing any contradiction, and when a question is ready, write the answer it rolls up to.
---

# Test

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Autopilot**. Writes links, boundaries, statuses
and answers; the shape is in `shared/research-graph`.

Two jobs arrive here and `next` says which: **settling candidates** under an open question, or **answering** a
question that is `ready_to_answer` (§6). A direction you test drops off the frontier; one left half-worked comes
back tomorrow. `autopilot/good-hypothesis` has the craft for killing, sharpening or leaving a candidate open.

## 1. Personal data first

**Can the user's own record settle this?** A timeline, a prior result, a prescription date. It is cheap and the
only evidence about this person. It is n = 1: it **can never make a general claim supported** and it **can refute
a prediction about this user** outright. Use it first as a cheap kill, last as support.

## 2. Cheap settlements before new searching

Kill any candidate you can with evidence already in the graph. Only the survivors justify retrieval.

## 3. The discriminating observation

For each surviving pair: what observation would come out differently between them? If none, merge them.

A test is worth running only when **it can come out both ways**, **the two outcomes mean different things**, and
**it is cheap enough to be worth the answer**. Otherwise close the direction rather than plan the test.

## 4. The context question, before you believe any contradiction

> **Do the two findings differ in population, dose or timing?**

If they do, it is a **boundary condition**, not a clash, and both findings stand. Most apparent contradictions in
the literature dissolve this way; only one that survives is disputed. Record the answer on the hypothesis:

```json
{"name": "<hypothesis>", "boundaries": [{
  "between": ["<finding A>", "<finding B>"],
  "differ_in": "population age band",
  "note": "40-70 against 65-85; not the same population, so not a clash",
  "spawned": "<the new question this opened>"}]}
```

**Every finding named in `between` stops counting against the hypothesis.** Name only the two the boundary
separates. The boundary is usually a good new question: spawn it.

## 5. Link the evidence

`update` each finding with `supports` or `contradicts`, naming the hypotheses. These are the only links you type.

**Silence on the outcome is not support.** A source that did not measure or report the outcome *bounds* the
question; it does not support a claim about it. A body that would say "the source does not report X" means
the finding supports no claim about X. Leave it linked to the question and say in the body what it
bounds. A boundary dissolves a contradiction, never the support.

Then close what died: `status: closed` with a `closed_reason` in plain words. Nothing is deleted.

Code recounts the independent origins and names the verdict in the save's reply. If it is not what you expected,
the reason is in the counts.

## 6. Answering a question that is ready

`ready_to_answer` comes in two shapes: a parent whose decomposing children are all resolved, and a leaf with
evidence and candidates that have met it (a settled leaf needs no invented children). Answering costs a move.

```json
{"name": "<the question>", "status": "answered",
 "answer": "...", "cites": ["<hypothesis>", "<a resolved child question>", "<a finding>"]}
```

1. **Every claim in the answer cites a node**; `save` refuses an answer that cites nothing (refusal 4).
2. **The answer is as strong as the weakest claim it cites**, computed by code. A **claim** (a hypothesis or a
   resolved child question) is a step, and the weakest caps the answer. A **finding** is counted by distinct
   origins and sets the verdict only when the answer rests on nothing else, so cite findings freely. A cited
   question searched and found empty is reported separately as *nothing found for*.
3. **What stayed open is part of the answer**: carry it into `open`.

## 7. Save

`update` for links, boundaries, statuses and the answer; `nodes` for any question a boundary or a failed test
opened. `expanded`: what was settled; `dropped`: what was closed and why; `open`: what you could not settle and
what it would take.

## Rules

- **You never write a verdict** (refusal 7), and never a verdict word as a status.
- An animal result does not move a human verdict.
- Two analyses of one data release are one line of evidence; the `origin` is the release.
- Something actionable goes into the report and nowhere else. Adopting anything is the plan path through
  Nostradamus and Challenger, with the user.
- The frontier is a ranking, not an order: work another direction when you judge it better and name it in the
  save.
