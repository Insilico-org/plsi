---
name: deep-search
description: Use when searching for evidence in research and the obvious query is not enough - choosing between your own web search, the literature APIs and the relation counts, five query shapes, telling a silent field from a failing instrument, and knowing when to stop. Load it from the Gather move when a search comes back thin, junk or empty, and from Ask when a direction needs to be aimed before it is searched.
---

# Finding what is actually there

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Autopilot**.
The Gather page says what a finding must carry; this says how to find one. Depth is more *shapes* of query, and
knowing what a shape returning nothing means.

## Three routes

- **Your own web search** reaches the whole page: results tables, registry entries, preprints, guidelines, the
  paper a relevance ranker will not return. Use it for the seed, for numbers not in any abstract, and to check
  whether an empty API result is the field or the query.
- **The toolbelt** gives verifiable identifiers and publication types. Only `europepmc` returns abstracts;
  `pubmed` for publication types and hit counts, `ctgov` trials, `openfda` labels, `evipedia` evidence reviews.
- **`plsi research discover --about "<subject>"`** reads PubTator relation annotations and returns, for each
  entity linked to the subject, how many papers stand behind the link. It tells a settled question
  (`well_studied`) from an open one (`candidates`, each with its PMIDs as seeds) before you spend a cycle.
  The counts are a model's reading, not curation, so the quote still comes from the paper. It indexes PubMed and
  the open-access subset only. `resolved: false` means PubTator uses another name for the subject: pass its id
  with `--entity` (`@CHEMICAL_<Name>`, `@GENE_<SYMBOL>`, `@DISEASE_<Name>`) or use web search.

Neither the APIs nor web search alone is a search.

## Start from one good paper

Find a recent review or meta-analysis first and build from **its** controlled vocabulary and phrasing. Check every
controlled-vocabulary term before using it; an unresolved term becomes a free-text synonym inside its block, never a silent drop.

## Five shapes, in this order

| # | Shape | What it is for |
|---|---|---|
| 1 | **review** | map the field; find out if this is already settled |
| 2 | **direct** | the question's own concept blocks |
| 3 | **against** | hunt the opposite on purpose: "no association", "null", "failed to replicate" |
| 4 | **population** | restricted to the people who matter |
| 5 | **references** | one hop out from the seed's reference list, not recursive |

The against-shape runs before the population restriction: an unrestricted null damages a claim more than a
restricted positive supports it.

One concept block per element, synonyms OR'd inside, blocks AND'd together, so a failed search is diagnosable by
dropping one block. Adapt it per source: PubMed ANDs every token, so a natural-language question returns zero;
Europe PMC returns the newest first and needs `EXT_ID:<pmid>` to fetch one record.

## Read the count before the papers

| Hits | What it means | What to do |
|---|---|---|
| **0** | novel, or the terms are wrong | re-query once with different vocabulary. Still zero: a recorded absence |
| **1–20** | readable | read them |
| **20–200** | too many | filter by design, strongest first, read the top |
| **200+** | the question is too broad | back to Ask. Do **not** read |

## Three different silences

- **Nothing retrieved, twice, in different vocabularies**: a genuine absence, `unstudied`.
- **Plenty retrieved, nothing usable**: retrieval failed, not the field, `nothing-usable`. Say what came back.
- **The result exists where this loop cannot read it** (a results table, a figure, a full text): a tooling limit.
  Name it as its own gap.

Before writing any of the three, try the other route.

## "None found" has to be earned

Write *no contradicting evidence exists* only after a query designed to find some, and record which; otherwise the claim is *not searched*. `save`
enforces two rounds before `gap: unstudied`; the rest is yours.

## Stopping

Count novelty each round. When a round returns almost nothing new, stop. Code reports a quiet round as a signal and
does not act on it. About five rounds of refinement is usually what pays.

## Rules

- Quote the **results** sentence, not the conclusion. Copy it; never retype it.
- Record `origin` and reuse the exact string in `origins_in_use`.
- A review's summary of other work is **one** finding attributed to the review. A mechanism from a discussion
  section is a hypothesis.
