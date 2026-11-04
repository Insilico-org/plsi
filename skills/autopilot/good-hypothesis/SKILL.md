---
name: good-hypothesis
description: Use when proposing or judging a candidate explanation in research - what makes one worth having, how to write a falsifier something can actually touch, when two candidates are really one, and when to kill or supersede. Load it from the Explain or Test move when the candidates feel thin.
---

# What makes a hypothesis worth having

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Autopilot**.
The move pages say what to produce; this says how to tell a candidate that earns its place.

**A hypothesis earns its place by what it rules out.** "Something about the exposure affects sleep" excludes
nothing. "The effect is dose dependent" excludes a flat dose-response.

## The falsifier has to name something that could exist

`save` refuses a candidate with no `if_false` but cannot judge it. Three grades, and only the first two are
tests:

| Grade | The falsifier is met by | What to do |
|---|---|---|
| **cheap** | something already in the graph, or in the user's own record | test it now, at no retrieval cost |
| **reachable** | a study that exists and can be found | that is a Gather |
| **wished for** | a measurement nobody has made | **not a test.** Record it as a direction, the question that would settle it, and say in the body that nothing can touch it yet |

## Name what would settle it, or name nothing

`tested_by` points at the question whose answer decides this candidate, never back at the question that proposed
it. If the settling question does not exist yet, leave `tested_by` empty and say in the body what would settle it.

## Two candidates that predict the same thing are one

Ask of each pair: **what observation would come out differently between them?** If none, merge them and say so in
`dropped`. The observation that separates the survivors is the next question.

## The boring three come first

**Nothing** (chance, no real effect), **confounding**, **artifact** (measurement, selection or reporting), before
any mechanism. Agents favour surprising associations over unsurprising explanations, and the boring three are
usually the cheapest to kill.

## What the evidence can and cannot do

- **The user's own record is n = 1**: it can kill a prediction about this person and never makes a general claim
  supported.
- **An animal result is a finding about that species**, outside the human count.
- **Unattributed evidence counts against a candidate and not for it**: a finding with no origin may repeat one
  already counted.
- **A contradiction needs the context question first**: do the findings differ in population, dose or timing?

## Killing, sharpening, superseding

- **Kill** when the falsifier was met: `status: closed` with a plain reason. Nothing is deleted.
- **Sharpen** by writing a *new* hypothesis under the same question and closing the old one `superseded`, citing
  it.
- **Leave open** when nothing has touched it. Many untested candidates and no evidence means Gather was needed.

## Rules

- You never write a verdict; `supported` is the ceiling word.
- No cap on how many candidates a question carries: whatever survives the separating test is the right count.
- A candidate nobody could ever test is an opinion: put it in the question's body, not in the graph.
