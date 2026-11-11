---
name: hallmarks
description: Use as PLSI Target Hunter when the researcher wants a target, pathway or candidate framed against the hallmarks of aging - which hallmarks it touches, on what evidence, and which aging clocks or biomarkers could show an effect.
---

# PLSI hallmark framing

The framing is easily overstated, so the shape of the evidence matters more than the amount.

## When to use

- "Which hallmarks does <target> act on?", "frame this candidate for a grant", a candidate from `targets/discover`
  or a mechanism from `targets/evaluate`.

## Steps

1. **Start from the curated record.**

   ```bash
   plsi targets dossier --gene <SYMBOL>          # `aging` is Open Genes' curation, with identifiers
   plsi targets brief   --gene <SYMBOL>          # the same evidence, split human and animal
   ```

   The aging block gives a confidence level, the aging mechanisms the curators assigned, why the gene was curated,
   and the studies: lifespan experiments (animal) and longevity associations (human genetics), kept apart.
   `curated: false` means Open Genes does not cover the gene; the literature search starts there.

2. **Read the computed frame.**

   ```bash
   plsi targets hallmarks --gene <SYMBOL>       # from the dossier on disk; contacts nothing
   ```

   One row per hallmark of the twelve in López-Otín et al. 2023 (PMID 36599349; say so, since the earlier list has
   nine), each marked `touched` or not and naming the Open Genes mechanisms it rests on.

   - **`silence`** on an untouched row says which absence it is: no mechanism vocabulary for that hallmark in the
     source, nothing filed by the curators, or a gene the source does not cover.
   - **`unmapped_mechanisms`** are curated mechanisms the mapping does not place; name them and map them in prose.
   - **`touched_count`** is breadth of curation, not a score; never rank by it.
   - The mapping is PLSI's reading of Open Genes' words. Where you disagree with a row, say so and why.
   - Compare `counts` with `shown` (the lists are sampled; say `n of N`) and check `perturbed` on every animal row
     (an experiment that changed another gene is not evidence about this one).

   Then widen with the literature:

   ```bash
   plsi evidence search --source pubmed    --query "<target> <hallmark>" --limit 20
   plsi evidence search --source europepmc --query "EXT_ID:<pmid>" --limit 1   # the abstract for one paper
   plsi evidence verify --kind <pmid|doi> --id <id>
   plsi refs list --kind dataset
   ```

   `pubmed` ranks by relevance without abstracts; `europepmc` gives abstracts ranked by date. The `dataset`
   references are bookmarks, not queryable sources: open them with your own web search and say which you checked
   by hand and which you could not.

3. **Grade each link by its weakest cited step**, naming the model system:

   | Evidence under the link | Class |
   |---|---|
   | human genetic association or a human trial | may reach `evidence_backed` |
   | animal lifespan or phenotype work | Low; `species: animal` wherever it is written |
   | cell or in-vitro work | Low |
   | pathway membership or a curated mechanism label alone | `hypothesis_only` |

   A curated mechanism label carries no study; a link resting only on one is `hypothesis_only` until you find the
   paper. A label that restates what the protein is says nothing about aging.

4. **Readouts.** For each mapped hallmark, the human biomarkers or aging clocks that could show an effect, where they
   come from and what change would refute the link. A link with no readout is a label.

   ```bash
   plsi clocks list
   ```

   Say whether improving the readout alone is known to mean the person is better off; an untied surrogate is a
   limit.

5. **Return one `result`** with `<PLSI_HOME>/work/<thread>/hallmarks_<gene>_<YYYYMMDD>.md` (the `thread` from the
   request, or `<gene>-hallmarks`, saying which you used): a table of hallmark, link, direction, evidence class,
   model system, identifiers, readout and falsifier, then one paragraph on which links are strongest and which are
   labels. Name the `target_<gene>.json` from `plsi targets show` in `files` when one was written.

## Rules

- **No hallmark link is stronger than its weakest cited step.** Animal and cell data stay Low.
- **A curated mechanism label is not a hallmark**, and the mapping between them is stated.
- **An absence in Open Genes is an absence in Open Genes.** Name the silent source.
- **A human readout on an animal-evidence row says so**: put the species in the readout cell too.
- Nothing here is advice for a person's plan, and no personal data goes into it.
