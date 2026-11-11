---
name: deep-search
description: Use when searching for evidence in research and the obvious query is not enough - choosing between your own web search, the literature APIs and the relation counts, adapting a query per source, and telling a silent field from a failing instrument. Load it from the Gather move when a search comes back thin, junk or empty, and from Ask when a direction needs to be aimed before it is searched.
---

# Finding what is actually there

`lab/gather` says how to search and what a finding must carry; this says which route to take and what a search
returning nothing means.

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

## Queries

The seed paper, the concept blocks, the five query families, the hit count, "none found" and stopping are
`lab/gather` steps 1-4 and 6. Adapt each query per source: PubMed ANDs every token, so a natural-language question
returns zero; Europe PMC returns the newest first and needs `EXT_ID:<pmid>` to fetch one record.

## Three different silences

- **Nothing retrieved, twice, in different vocabularies**: a genuine absence, `unstudied`.
- **Plenty retrieved, nothing usable**: retrieval failed, not the field, `nothing-usable`. Say what came back.
- **The result exists where this loop cannot read it** (a results table, a figure, a full text): a tooling limit.
  Name it as its own gap.

Before writing any of the three, try the other route.
