---
name: journal
description: Use as PLSI Research Orchestrator when a researcher records wet-lab work - an experiment planned, run or finished (PCR, gels, RT-qPCR, westerns, xCELLigence, plate readers, microscopy, cell culture, sorting, animal studies, cloning, transfection, ELISA), a plasmid file, a bench calculation, or the journal page.
---

# Lab journal

Follow persona.md norms and `shared/team`. Owner: **PLSI Research Orchestrator**. The journal is the researcher's
notebook: one entry per experiment, kept under `<PLSI_HOME>/journal/` and drawn on one page. Code saves, derives and
flags; what the experiment means is the researcher's.

## When to use

- "I'm running a qPCR today", "log this gel", "here are my Cts", "passaged HEK293 to P12", "the mice weighed ...",
  a plate-reader or xCELLigence export, a micrograph or gel photo, a SnapGene or GenBank file.
- "How much stock for 100 µM in 1 mL?", "seeding 96 wells at 10k", "master mix for 30 reactions": `journal calc`.
- "Show me my journal", "open the entry", "sign it".
- A journal from the Lab Journal bot or the Cursor plugin (a folder, zip or .tar.gz holding `journal/`): unpack it, run
  `plsi journal import --from <folder> --dry-run`, say in one line what comes in and what stays in the original files
  only, then import on the researcher's yes. Entries already in the journal are never touched; an entry signed in the
  Lab Journal comes in unsigned (its record says who signed it there), for the researcher to sign again here.
- **Not this skill:** literature research and notes (`lab/research`, `lab/session`); a journal entry never becomes a
  research note or a Mothership package by itself.

## Steps

1. **Pick the entry.** A new experiment: start from the kind's template and give it a short id (`qpcr-p21-20261117`).
   An experiment already in the journal (same aim, same day or a continuation): `journal list` and save its next
   version under the same id. One experiment per entry; a follow-up experiment (imaging sorted cells, a western on
   the qPCR's samples, a sequencing check of a clone) is a new entry with `"related": ["<earlier id>"]`: the
   later entry points to the earlier one it builds on (the qPCR to the culture that gave its cells, never back).

   ```bash
   plsi journal list --kind qpcr
   plsi journal template --kind qpcr
   ```

2. **Fill it from what the researcher gave, never from what is usual.** Values, units, lot numbers, temperatures and
   times are copied as written; a value not given is left out, not guessed (the template's example numbers go).
   Steps done are `"done": true`. Samples carry a `group`; the comparison the results use needs `control_group`
   (and, for qPCR, `reference_targets`). When the control or reference is not clear, ask ONE card ("Which group
   is the control?" with the groups as options). An export (Ct table, plate-reader CSV, RTCA export, FlowJo table)
   is read into the matching result list row by row; say how many rows were read and which were skipped.
   Sample ids are lab codes: no patient names, initials, dates of birth or record numbers, ever. A sample is
   named as the researcher calls it ("untransfected", "p21-EGFP", "dmso-1"), never by its file name; the file
   goes with it (`fcs[].file`, `files`). Raw instrument rows are read into their result fields, never copied into
   notes; western bands go in `bands`, while `lanes` are for DNA and RNA gels.

   **Status:** `planned` before the work starts, `running` while protocol steps remain, `done` once the results
   are in and nothing is left to do (most entries saved from an export are `done` at once). `save` asks when
   every step is done but the entry still says running. Band sizes read
   off a gel are estimates by nature: "about 650 bp" goes in `observed_bp` as 650, a faint band in `faint_bp`.
   A ladder lane's `sample` is the product as on the tube ("GeneRuler 1 kb Plus"); plsi draws its standard bands.
   A name that fits several products ("1 kb plus") comes back as a check: ask which one, never pick.
   A plate you lay out puts the controls in the left columns and the cases to the right, each sample's replicates
   side by side (4 unless the researcher says otherwise), NTC and no-RT in their own column.

   **Observations** are what was seen at the bench, short and in plain words, as a scientist writes in a
   notebook ("Single bands at the expected size in colonies 1, 2 and 4; colony 3 has an extra faint band near
   1.9 kb."). Never "as described by the researcher", never file names, hashes, field names, row counts or what
   PLSI did: that bookkeeping goes in `record` (files read, rows imported or skipped, what was not given), which
   the page folds under History. `save` refuses observations that read as bookkeeping.

3. **Calculate with code**, never in your head, and keep the numbers in the entry (the step's `note`):

   ```bash
   plsi journal calc --kind dilution --set c1='10 mM' --set c2='100 uM' --set v2='1 mL'
   plsi journal calc --kind seeding --set cells_per_ml=1.2e6 --set per_well=10000 --set wells=60 --set plate=96
   plsi journal calc --kind mastermix --file mix.json
   ```

   `mastermix` and `protein_load` take their lists in a `--file` (`components: [{name, stock, final}]` or
   `[{name, per_reaction}]`; `samples: [{name, conc}]`). An error (`CALC_IMPOSSIBLE`) is told as it is, with
   what would fix it.

4. **Save, attach, read the checks.**

   ```bash
   plsi journal attach --entry <id> --file <photo.png>
   plsi journal save --file entry.json
   plsi journal show --entry <id>
   ```

   Attach a file first, then list its name in `files` (and in `results.images` with its channel and objective for a
   micrograph). `save` returns `checks` (spread replicates, late Cts, no blank, a weak standard curve, an animal's
   weight loss): give each to the researcher in one line, as a flag, not a verdict. Then the result: the main
   numbers `journal show` derived (fold change per target and group, relative level, concentration, % of parent,
   genotype counts), as a short table. A changed entry gets the next version; an unchanged one says
   `changed: false`. Control wells carry their `role`, never pose as a sample or a group: `"ntc"` and `"no_rt"`
   for qPCR, `"blank"` for medium-only wells of a plate read or an xCELLigence run. A role left unset is taken
   from the name ("NTC", "medium only") and `save` says so; set it.

5. **Flow cytometry.** With the cytometer's FCS files (one per sample), code counts every gate from the events,
   so attach them, list them in `files` and map each to its sample in `results.fcs`. Gates name channels by
   `$PnN` or marker (`"FSC-A"`, `"GFP"`), have a `parent` (none = all events) and one shape: `polygon` or `rect` on
   `x`/`y`, or `interval` on `x`. Vertices are in the channel's own units; take them from the researcher's gating
   (a FlowJo or cytometer export, or what they describe), never invent a gate. A wrong channel refuses the save
   (`FCS_CHANNEL`). A FlowJo or sorter counts table goes in `exported_counts` (`{sample, gate, events}`, row by
   row); `save` flags a file with no spillover matrix and an exported count the file does not give.
   Without FCS files, the counts come from `exported_counts` alone and the page shows the hierarchy.

6. **Plates and vials.** A culture entry lists its vessels (`results.vessels`): each flask, dish, plate or
   cryovial with its label id, type, cell line, passage, date, cells or confluence, medium, location and status
   as recorded. A frozen vial has its `box` and `position` (A1 ... J10). Thawing or discarding a vial is a new
   culture entry that lists the vial again with its new status: the cell bank (`journal bank`) keeps the latest.
   "How many HEK293 vials are left / where?" is `journal bank`, never a count from memory. It flags two vials in
   one position and a frozen vial without a position.

7. **Animals and genotyping.** Each animal goes on the roster (`results.animals`: lab id or ear tag, never a
   person's name; group, sex, born, cage, strain, status). Genotyping: the assay's `alleles` with their band sizes
   (an internal control band has `"control": true`), each animal's `bands` as read from the gel, and the lab's
   written `genotype` when there is one; code calls the genotype from the bands and flags a failed lane, a band
   that matches no allele and a written call the bands contradict. Give `expected` only when the researcher names
   the cross (het x het: 1:2:1); code tests the counts (chi-square) and says when they are too few. Ear marks go
   in `ear_punch` as the researcher made them (`{"ear": "left|right", "at": "front|back|outer|hole"}`, the
   animal's own left; `[]` = unmarked); never derive them from an id number, as facilities number differently.
   The page draws each animal's ears on the roster and per cage; code flags two animals in one cage with the
   same marks. A photo of an animal the researcher sends (identification, phenotype, a lesion) is attached and listed
   in `results.images` with its `animal` id and a short `note`; ask which animal when it is not said.

8. **Plasmids.** A GenBank file (.gb/.gbk from SnapGene, Benchling, Addgene) is saved as it is; a plasmid described
   in words is written as Plasmid JSON with only the features the researcher named. An entry points at it with
   `results.plasmid`.

   ```bash
   plsi journal plasmid save --genbank <file.gb> --name <short-name>
   plsi journal plasmid show --name <short-name> --region <start-end>
   ```

   "Which enzymes cut once in the MCS / between A and B": `--region`, never a reading of positions by eye. Give
   each enzyme's ends (5' or 3' overhang with its bases, or blunt) so compatible pairs can be chosen; Type IIS
   enzymes (BsaI, BsmBI, BbsI, SapI, AarI ...) cut outside their site and leave the overhang shown. The panel is
   86 common enzymes (`enzymes.csv`): an enzyme not in it is "not in PLSI's panel", never "does not cut".

9. **The day.** "Today I want to…", "what's on today?", "done with the transfection": the day's plan is a list of
   items (`text`, optional `time`, the `entry` it works on, `project`, `done`), saved whole for its date. An
   experiment in the plan gets an entry first (from its template, `"status": "planned"`) so the item can link it;
   errands (order primers, autoclave) are items only. When the researcher reports something done, tick it and save
   the plan again. "What's on today" is `journal today`: say the open items in time order, the running experiments
   with their next step, and the flags, in a few lines.

   ```bash
   plsi journal day save --file day.json
   plsi journal today
   ```

10. **The page.** `journal page` writes `journal.html` (after that, every save rebuilds it). Send it as a file
   attachment so the researcher opens it in a browser: the chat preview may not run its script and a `file://`
   path does not open on a phone. Say what is new on it in one line.

   ```bash
   plsi journal page
   ```

11. **Conclusion and signing.** `observations` are what was seen; `conclusion` and `next_steps` are the researcher's
   words, or your draft only after they confirm it. Signing freezes the entry for good: offer it only when the
   researcher says the experiment is finished, with ONE card "Sign <title> as <name>? It can never change again."
   (Sign / Not yet). A correction to a signed entry is a new entry with `"amends": "<id>"`.

   ```bash
   plsi journal sign --entry <id> --by '<name as they gave it>'
   ```

## Rules

- Never invent a value, a lot, a band or a Ct; an empty field is honest.
- The derived numbers (fold change, relative level, concentration, % change) come only from `journal show`; never
  restate them with other arithmetic.
- The journal stays on this computer: never post an entry, its files or the page to the Mothership, a room or a
  worker unless the researcher asks for that one thing.
- An animal study entry records the approved protocol number when the researcher gives it; weight-loss flags are
  passed on as written, and the decision is theirs and their animal welfare body's.
