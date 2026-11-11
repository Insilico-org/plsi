---
name: gather
description: Use as PLSI Research Orchestrator when `plsi research next` says the move is `gather` - find a seed paper, run the five query families, read what came back and write each result down as a finding with its verbatim quote.
---

# Gather

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Orchestrator**. Writes `finding` nodes and
`last_search` on the question; the shape is in `shared/research-graph`.

**Use both retrieval routes** (`lab/deep-search`, Three routes): your own web search and the toolbelt, which gives
identifiers code can verify and the publication types `design` comes from:

```bash
plsi evidence search --source europepmc --query "<query>" --limit 20   # the only source that returns abstracts
plsi evidence verify --kind pmid --id <id>
```

A quote verifies against whatever `text` you pass, so a finding from your own web search verifies as well as one
from the toolbelt.

**Pass retrieved text, never a summary of it.** A paraphrase passed as `text` verifies against itself and the
check is defeated silently. If a tool will not give you the source's own words, get them another way, or record
the finding with no `text` and say in the body that the quote could not be checked.

The services rate-limit (HTTP 429 and 503 come back as `NETWORK_ERROR`): space the calls out. A round cut short
by rate limiting is **not** an empty field; say so in `open` and record no absence.

When a search comes back thin, junk or empty, read `lab/deep-search`.

## 1. Seed first

Find **one good paper** first, ideally a recent review or meta-analysis on this question, and build queries from
its controlled vocabulary and wording. A review often shows the question is already settled.

## 2. Blocks, not sentences

One concept block per element of the question; synonyms OR'd inside a block; blocks AND'd together. A failed
search is then diagnosable: drop one block and see which was responsible.

Check every controlled-vocabulary term before using it; many model-proposed MeSH terms do not exist. A term that
does not resolve becomes a free-text synonym inside its block, never silently dropped.

## 3. Five query families, in this order

| # | Family | Purpose |
|---|---|---|
| 1 | **review** | map the field; find out whether this is already settled |
| 2 | **direct** | the question's own concept blocks |
| 3 | **against** | hunt the opposite result: "no association", "null", "failed to replicate" |
| 4 | **population** | restricted to the population that matters |
| 5 | **seed references** | one hop out from the seed paper's reference list, not recursive |

The against-family runs before the population restriction, because an unrestricted null damages a hypothesis
more than a restricted positive confirms it. Family 5 recovers the recall model-written queries lose.

## 4. Read the count before you read the papers

| Hits | What it means | What to do |
|---|---|---|
| **0** | genuinely novel, or the terms are wrong | re-query once with different vocabulary. Still zero: record the absence and stop |
| **1–20** | readable | read them |
| **20–200** | too many | filter by study design, strongest first, read the top |
| **200+** | the question is too broad | back to Ask and narrow. Do **not** read |

**Hits are not findings.** Plenty retrieved and nothing usable is `nothing-usable`, a statement about retrieval.
Only a genuine zero, twice, earns `unstudied`.

**At a zero, record the absence, never a finding.** `save` refuses a finding from a search that returned nothing
(refusal 5); the permitted output is `last_search` with two rounds, zero hits, and a `gap_why` naming the
vocabularies tried.

**"None found" has to be earned.** Write that no contradicting evidence exists only after a query designed to find
some, and name it. Otherwise the honest statement is *not searched*.

## 5. What becomes a finding

What was observed, in whom, and where it came from. Two papers reporting the same result in the same cohort are
**one finding with two sources**.

Every finding carries:

- a **verbatim quote** from the **results** sentence, not the conclusion. Copy it; never retype it.
- **`design`** and **`species`** from their closed lists in `shared/research-graph`, plus **`population`** in your
  own words and **`observed`** where the source gives a date. Put the shape in the field and the specifics in
  `population` and the body; if no value fits, use the most cautious one that does and say why in the body. `species` is what the result is **about**; a mouse result is `animal`, never `human`.
- **`origin`**: the narrowest shared source of the result (registration id, else named cohort, else consortium,
  else research group). Two papers reporting two endpoints of one trial share an origin and are one line of
  evidence. Reuse the exact string from `origins_in_use` when the source is already there: a second wording
  invents an independent line that does not exist. If you cannot tell, leave it empty.
- `studies` when the source is an aggregate: the number it pools, as a descriptor.

**A finding never computes.** Numbers go down as they appear, with no conversions or ratios.

**Ask of any marker-based finding:** if this number improved and nothing else changed, would the person be better
off? If no or unknown, the finding is `surrogate-only` and the question inherits that gap.

**Not a finding:** a review's summary of other work (go to the primary source, or record it as *one* finding
attributed to the review); a mechanism proposed in a discussion section (a hypothesis for Explain); an animal
result stated as a human one; anything the source does not say, including something true it never claimed.

## 6. Stopping

Count novelty each round: retrieved sources not already seen. When a round returns almost nothing new, stop and
record `last_search: {rounds, hits, new}`. A quiet round comes back as a `signal`; if you think the search rather
than the field was the problem, say so in `open` and keep the direction open. About five rounds of refinement is
usually what pays.

## Rules

- Verify every published identifier (`plsi evidence verify --kind pmid|doi|nct|label|evipedia|model|rule`) before
  it goes into `sources`. The user's own record has no kind: a `personal-record` source carries the event or state
  reference as written, and its quote stays unverified. Say so.
- A personal record is structured fields. Put the relevant dates in the body and name them in the hypothesis's
  `if_false`, where Test can use them.
- A private source (a Mothership release, a licensed database, a document the user supplied) is an ordinary finding
  with its release identifier and no `text`, so its quote stays unverified, and it obeys every refusal.
- Abstracts and metadata only: quote verification is partial, and unverified quotes are common. Say so rather
  than claiming more.
- Code never closes a direction: only `close_direction` does.
