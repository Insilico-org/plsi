# plsi.journal

The wet-lab journal of a researcher's PLSI (`plsi journal`, skill `lab/journal`). Everything lives under
`<PLSI_HOME>/journal/`:

```
entries/<id>/entry.json      the current version: the entry, its version, hash and signature
entries/<id>/history.jsonl   one line per save and per signature (version, time, status, hash)
entries/<id>/files/          gel photos, micrographs, plate exports, traces, FCS files (`plsi journal attach`)
entries/<id>/flow-cache.json gate counts and plots from the FCS files, rebuilt when a file or a gate changes
plasmids/<name>.json         a plasmid: length, features, sequence when known
days/<date>.json             the day's plan (`plsi journal day save`), shown by `journal today` and on the Today tab
journal.html                 the page (`plsi journal page`), rebuilt after every command that changes the journal
```

| Module | Role |
|---|---|
| `home` | where everything above lives |
| `models` | `EntryInput` (what the bot writes): aim, protocol, reagents, samples, plate, observations, record |
| `results` | the typed results per kind (Cts, lanes, bands, cell index, readings, images, passages, vessels, gates, animals) |
| `store` | entries: save (next version, history line), list, show with `derived`, sign, attach; the status (signed once signed); the bank command |
| `analysis` | numbers derived from raw results: 2^-ΔΔCt, band ÷ loading control, blank and standard curve, normalised cell index, gates from exported counts, doubling time; well roles; each block with its checks |
| `animals` | genotypes called from genotyping bands (zygosity, or presence with a control band), the roster with weights, ear marks that clash within a cage, the genotype counts against the cross, weight change per group |
| `flow`, `fcs` | FCS 2.0-3.1 reading with the file's spillover matrix (numpy); gates counted from the events within their parent; dots and histograms for the page; a cache per entry |
| `plasmid` | plasmids on disk, GenBank import, and where the enzymes of `enzymes.csv` cut, with ends and overhangs |
| `ladders` | DNA ladders by product name (`ladders.csv`): standard band sizes for a ladder lane recorded without sizes; an ambiguous or unknown name is a check |
| `cellbank` | an entry's flasks, plates and vials, and the cell bank: every cryovial at its latest record (latest entry date, then save time), by box and position |
| `days` | the bench planner: one plan per day, and `journal today` |
| `calc` | bench calculators (`plsi journal calc`) |
| `stats`, `tuning` | the statistics the checks use; every threshold, display limit and file cap in one place |
| `templates` | a starter entry per experiment kind (`plsi journal template`) |
| `page` | the payload and the page: `journal.html` (the frame and its CSP) filled with `page/journal.css` and the script parts of `page/` in `page.SCRIPT` order: `core` (DOM, icons, colours, cards), one part per area of views, `shell` (sidebar, overview) and `app` (routing, reload) |

Rules: code computes and flags; the conclusion is the scientist's. A signed entry is never saved again: a correction
is a new entry with `amends`. Nothing in the journal leaves the computer.
