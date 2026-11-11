---
name: ask
description: Use as PLSI Research Orchestrator when `plsi research next` says the move is `ask` - turn the top frontier direction into one question a search could settle, or split it into three to five children across different angles.
---

# Ask

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Orchestrator**. Writes `question` nodes; the shape
is in `shared/research-graph`.

A frontier item is a direction; a question is something a search can settle. Most of what the rest of the cycle
costs is decided here.

## 1. Four tests, before any search

A question that fails any of these is reworked, not searched.

1. **Could the evidence exist?** Something a study design could have measured.
2. **Can it come out both ways?** If one answer is already known, it is not a question.
3. **Is it bounded?** Who or what (population, system, sample), what was varied (exposure, marker,
   intervention), measured how (outcome). Without all three a finding cannot say where it came from.
4. **Does it change anything?** If either answer leaves the question in chief where it was, drop it.

For test 2, when the direction has a subject (a drug, a gene, a condition), ask the field first:

```bash
plsi research discover --about "<the subject>"
```

`well_studied` lists what the field has answered: do not write those children. `candidates` are relations
standing on a handful of papers, each with PMIDs to aim Gather at. It is optional, and it proposes only: a
relation unrelated to the question in chief is a different topic. `lab/deep-search` says what the counts
mean.

## 2. Split it, or sharpen it

**Split** when the direction is too big to settle in one cycle: three to five children, **from at least three
different angles**.

| Angle | Asks |
|---|---|
| mechanism | is there a route by which this could happen at all? |
| magnitude | how large is it, and in whom? |
| boundary | where does it stop holding — dose, age, sex, comorbidity, duration? |
| alternative | what else would produce the same observation? |
| harm | what does it cost, and to whom? |

Three siblings from one angle are three rewordings. The angles are counted and shown.

Each child records `link: decomposes` and the parent waits for them all, then rolls up into an answer. A child
of a parent that is already answered records `link: continues`. **Write `link` at creation**: it cannot be
worked out later.

**Sharpen** instead when the direction is already narrow: one question, with the search terms you will use. A
question that needs a fourth level of depth was not narrowed properly at the first. `next` gives the depth and the advisory limits (three deep, three to five wide). Go past them only for a
candidate at the depth limit whose settling question cannot be written anywhere else, and say why in the body.
Otherwise, at the limit, answer something instead of splitting again.

## 3. The gap sets the shape of the question

- **unsearched**: nobody has looked yet. The cheapest search.
- **unstudied**: we looked and found nothing. *Does it exist under any other name?*
- **unexplained**: evidence is in and nothing accounts for it. *What would account for this?* (often a sign to
  let Explain run instead)
- **unreplicated**: one independent line. *Does it replicate in a different design or population?*
- **surrogate-only**: known only through a marker. *Does the marker track the outcome that matters?*
- **disputed**: sources disagree and the context question did not dissolve it. *What differs between the two
  settings?*

## 4. Save

`nodes` of `kind: question`, each with `stakes`, `angle`, the parent and `link` where there is one, and a body of
one or two plain lines saying why this question. Claiming nothing has been studied needs `last_search` with two
rounds in different vocabularies (refusal 3).

In `expanded`, what you split and along which angles; in `open`, which children you did **not** create and why.

The frontier ranks directions by moves to a verdict, so a new question starts at the bottom. Write one when the
research needs it, not because the one in front of you is hard.

## Rules

- **Stakes is ordinal**: `high`, `some` or `low` - how much resolving it would change the answer in chief. Never
  a number.
- A question that cannot come out both ways is dropped, not ranked.
- Rewording an existing question is a **new** question; close the old one `superseded` and cite it. Titles
  never change: links are made of them.
- Keep at least one open direction that is not a continuation of the current best.
