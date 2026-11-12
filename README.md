# PLSI: Personal Longevity State Interface

PLSI turns any health record into a deidentified, code-normalized event log, projects it through versioned **State Maps** into a hashed state document, and lets Grok Bot propose screened actions with **explicit, scored next-state predictions**, including aging clocks.

This repo supplies:

- State Map contracts (`contracts/*.schema.json`, `maps/*.yaml`)
- a deterministic CLI toolbelt (`plsi`, JSON in, one JSON envelope out)
- the bots' skills (`skills/`), a first-run file (`plsi.md`) and a versioned persona (`persona.md`)
- the handoff protocol between the bots (`contracts/Handoff.schema.json`, `plsi handoff check`)
- trusted references (`mothership/references/<kind>.yaml`, indexed by id; `plsi refs list [--kind]`)
- opt-in sharing with the Longevity Mothership, Insilico's longevity research initiative (`plsi mothership`,
  `mothership/consent.md`): a weekly pseudonymous (not anonymous) package of coded fields only (codes, numbers,
  units, months, years; no free text, no value computed from age; the person only as sex, age band and ethnicity
  group), gate-checked, posted to Insilico's relay only after the user joins; research notes by the user's own Grok
  email; for invited physicians and researchers, the data catalog, releases and the findings ledger
- usage reports for the PLSI team (`plsi feedback`), sent only on the user's approval from their own Grok email
- autoresearch (`<PLSI_HOME>/research/`, `plsi research`): one folder per topic with questions, hypotheses and
  findings as linked Markdown (an Obsidian vault), research projects that group topics and notes, and an optional
  daily run on the share of the weekly usage the user sets; code computes every verdict
- target discovery for researchers (`<PLSI_HOME>/targets/<gene>/`, `plsi targets`): dossiers from free sources and
  an assessment refused unless every claim is sourced
- local state storage (`instances/<name>/`)

## Disclaimer

Longevity Grok is AI software for personal longevity research and education. It does not provide medical care, does
not diagnose, treat or prescribe, and does not replace your clinician. Outputs are generated automatically, are not
reviewed by any clinician, scientist or team member before you see them, and may be wrong. Automated checks do not
remove that risk, and no health or longevity outcome is promised. Individual academic affiliations are shown for
identification and do not imply institutional endorsement. Talk to your clinician before starting, stopping or
changing any medication, supplement or health routine, and do not delay care because of an output. In an emergency,
contact local emergency services.

By installing, you agree to the [Terms of Service](legal/TERMS.md); see also the [Privacy Policy](legal/PRIVACY.md)
and the [Disclaimer](legal/DISCLAIMER.md). xAI processes the information in your Grok Bot account under its own
terms and privacy policy, and services you connect may also receive information. Insilico receives information from
that account only through contributions or emails you choose to send.

## The team

On Grok Bot, PLSI is a team of Bots with separate chats, memories and contexts; the roster, each bot's skills and
commands and the handoff format are `skills/shared/team` (every bot reads it); the bots' profiles, the team rules and
the flows are `skills/shared/hub` (the hubs only).

- **Hubs** are the bots the user talks to, each in its own chat about its own use case: PLSI · Health Orchestrator
  (own health and family), PLSI · Research Orchestrator (research topics, projects, daily research), PLSI · Clinic
  Orchestrator (a longevity physician's panel) and, in the section **Ward**, one Ward bot per roster patient, pinned
  to that patient's instance. The role (`plsi role set`) picks the primary hub, which runs setup (`plsi.md`) and
  creates the others. Work outside a hub's use case goes hub to hub.
- **Workers** are shared by every hub and reply only to the hub that sent the request: the core team (Data
  Processor, Health Consultant, Nostradamus, Challenger, Reviewer, Data Controller, Memory Hole, Visualizer) and the
  specialists the user picks, in the sidebar section **PLSI Workers**; a physician also gets **PLSI Clinic** and a
  researcher **PLSI Lab**.
- **Session rooms** (`skills/shared/sessions`): a task that needs several workers at once gets a group chat of the
  hub and up to 5 workers in **PLSI Sessions**; cards, approvals and recording stay in the hub's chat.
- **The shared team file** `<PLSI_HOME>/team.json` (`plsi team`): the bots, the primary hub, own health, the Terms
  accepted, the PLSI version; every hub reads the same.

```
                                   user / physician
              (1:1 chats, question cards, approvals, routines)
        |                  |                   |                   |
  Health Orch.      Research Orch.       Clinic Orch.        Ward · <label>
  own health,       topics, projects,    panel, intake,      one patient,
  family            daily research       roster, Ward        pinned instance
        |                  |                   |                   |
        +------------------+---------+---------+-------------------+
                                     |  hubs: conduct threads, batch questions, urgent care
                                     |  every handoff: Handoff JSON; cited states must be current
                                     |  request/answer out, result/question back; hub to hub too
   +---------------------------------+----------------------------------+
   | PLSI Workers (shared by every hub)                                 |
   | core: Data Processor, Health Consultant, Nostradamus, Challenger,  |
   |       Reviewer, Data Controller, Memory Hole, Visualizer           |
   | specialists (opt-in): Wearables, Nutritionist, Coach, Sleep,       |
   |       Biohacker, Explorer, Navigator, Trial Scout, Pharma Analyst, |
   |       Engineer, Writer                                             |
   +--------------------------------------------------------------------+
   | PLSI Clinic (physician): Panel, Visit Prep, Clinical Evidence,     |
   |       Liaison                                                      |
   | PLSI Lab (researcher): Target Hunter, Landscape, Cohort Analyst,   |
   |       Grant Writer                                                 |
   +--------------------------------------------------------------------+
   | PLSI Sessions: one room per task, a hub and up to 5 workers        |
   +--------------------------------------------------------------------+
   Life: ingest ---> Map: project / state show ---> Policy: screen, plan gates, score (referee)
          ^                                                     |
          +----------------- new measurements <-----------------+
```

The bots do the judgment; `plsi` does what an agent should not: calculators (clocks, risk equations, unit
conversion, survival curves from the bundled UN WPP 2024 life tables, CC BY 3.0 IGO), connectors (Hevy, PubMed, ClinicalTrials.gov, openFDA, RxNav, Open Targets, MyGene.info,
Pharos, RCSB PDB, AlphaFold, ChEMBL, UniProt, Open Genes, oracles), the append-only log, the code gates and the
scorer. The Map is the protocol between the bots: Data Processor records and projects state documents, the other
bots cite them by hash. Every plan goes to Challenger before the user sees it; anything leaving the computer passes
the code gate, then Data Controller; predictions are scored by `plsi score`, never by the bot that made them. One
instance per person (`plsi init --relation self|family|other|sample`); every handoff names one.

## Packages

| Package | Role |
|---|---|
| [`plsi.life`](src/plsi/life/README.md) | Life layer: intake (FHIR, canonical CSV, methylation, Grok-extracted JSON), deidentification, LOINC/RxNorm/UCUM normalization, the append-only event log |
| [`plsi.map`](src/plsi/map/README.md) | Map layer: registry, selector, mapper (projection, units), storyline; calculators (convert, derive, range, course, survival) and clocks (native blood PhenoAge, map formulas, biolearn); state documents |
| [`plsi.policy`](src/plsi/policy/README.md) | Policy layer: evidence search and verification, blocking screening, plan gates, scoring and calibration, oracles |
| [`plsi.research`](src/plsi/research/README.md) | autoresearch: topics, projects, the move loop, verdicts, frontier, budget ledger, research notes |
| [`plsi.targets`](src/plsi/targets/README.md) | target discovery: dossiers from free sources, assessments, hallmarks, trials, briefs |
| [`plsi.mothership`](src/plsi/mothership/README.md) | the Longevity Mothership: consent and enrollment, packages, notes, the egress gate, the relay, professional access |
| [`plsi.clinic`](src/plsi/clinic/README.md) | the physician's clinic: patient Drive folders, sync, publishing, the panel dashboard |
| `plsi.vocab` | every enum |
| `plsi` (top-level modules) | the CLI and command table (`cli`, `commands`, `cmdspec`), the team and role, reports, export, feedback, references, keys, HTTP (`net`), extensions |

Rules: `plsi.policy` never imports `plsi.life` and reads the world only through `plsi.map`; `plsi.life` never imports `plsi.map` or `plsi.policy`. The three layers keep a fully local deployment possible.

Commands: `plsi --help` and `plsi <command> --help`; the table is `src/plsi/commands.py` plus the `commands.py`
of `research/`, `targets/` and `mothership/`.

## Extending PLSI

Grok can grow what PLSI does without changing the core. Use the lowest tier that closes the gap:

| Tier | Adds | How | Skill |
|---|---|---|---|
| Map | a new area: coordinates, codes, units | user map YAML, `plsi maps validate` / `install` | processor/add-map |
| Formula | a score, ratio or equation | `derive: {engine: expr, formula: ...}` in a map; a safe evaluator, never `eval` | processor/add-score |
| Extension | an input format (`importer`), a non-formula computation (`deriver`), an evidence source (`evidence_source`) | a tested package installed with `plsi ext install`, versioned under `<PLSI_HOME>/extensions/` | engineer/extend |

Extensions add and never replace. They are full-trust code, installed only with the user's explicit approval naming
the source; `install` runs the package's own tests with a minimal environment (no keys) and refuses imports outside
its layer or any patching of `plsi`, guard rails rather than a sandbox. Values they derive record
`extension:<id>@<version>` in provenance.

## Deidentification profile `plsi-limited-v1`

- The subject keeps only birth year (age 90 or over: `age_group: "90+"`, no birth year) and sex.
- Event dates are kept, so this is a limited data set, not HIPAA Safe Harbor.
- Observation origin keeps `file_sha256` and page, never a path or filename.
- FHIR import keeps codes, values, effective times, clinical status, components, dose text and the structured dose (doseQuantity); it drops identifiers, subject, performer, notes, narrative, contained resources, extensions and attachments.
- Patient name parts, identifier values, telecom and address are held in memory only; any observation whose text contains one is rejected with `IDENTIFIER_IN_TEXT`.
- CSV columns outside the canonical format are dropped and reported by name; methylation sample names are not stored.

## Consent

PLSI collects consent on its question cards (`persona.md`, Consent, batched); standing approvals replace a card until revoked. Joining the Longevity Mothership records the version of `mothership/consent.md` the user saw (`plsi mothership join --consent-version`), and `plsi mothership pack` refuses with `CONSENT_OUTDATED` once that text changes. Outbound oracle text is built in code from the saved state document only (values, item codes and months; never
`personal_context`, and never a coordinate that gives the age back: one in years, derived from the age, or marked
`local_only: true` in its map, the same rule as the Mothership package) and every text sent to an oracle is kept in `egress/oracles.jsonl` (the instance's, or PLSI_HOME's).

**Longevity Mothership wire.** PLSI, the relay (`plsi refs show longevity_mothership`) and the Mother (Insilico's Grok
Bot with its own toolbelt and storage) share one contract, kept with the relay and the Mother in
[`plsi-mothership`](https://github.com/Insilico-org/plsi-mothership). Contributions carry a pseudonym made on the
user's computer (the hash of a local secret, which also proves deletion requests), never the install code; the relay
forwards bodies without the install code and keeps no IP logs; professional tokens come from a one-time emailed invite
after a steward's review and carry scopes. Message kinds: contribution, withdrawal, research note, registry update,
preregistration and finding, each gate-checked on both sides. Research notes never take the relay: they go by email to
the Mother's `+research` address (`plsi refs show longevity_mothership_research`), signed by the sender's address, and
the Mother replies there with a receipt and, after review, the decision.

## Differentiators

The State Map vocabulary: State Map; registry, selector, mapper, storyline; correspondence types terminology | expert | statistical | mechanistic | validated | unmapped; claim ladder designed | instantiated | exercised.

| | Differentiator | Claim level |
|---|---|---|
| a | Scored next-state predictions (interval, basis, horizon) with calibration and misses reported | exercised |
| b | Aging clocks as first-class coordinates and prediction targets (native blood PhenoAge; every biolearn methylation clock through one adapter) | exercised (PhenoAge), instantiated (biolearn) |
| c | Any-modality intake via Grok extraction into code-normalized observations; maps are data the bot can author and validate | instantiated |
| d | Live evidence collection with verification of every cited identifier | instantiated |
| e | Proactive blocking screening of every action | exercised |
| f | A personal companion inside Grok Bot, run as hubs (Health, Research and Clinic orchestrators, one Ward bot per patient) with a shared core team and opt-in specialists in separate contexts, a conducted hubs-and-spokes protocol (one card per decision) with session rooms for multi-worker tasks, an adversarial plan check and an egress check | designed |

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"                  # add ,clocks for methylation clocks
plsi doctor
plsi init --instance me --birth-year 1970 --sex F
plsi ingest --instance me --csv labs.csv --dry-run
plsi ingest --instance me --csv labs.csv
plsi maps select --instance me
plsi project --instance me --map blood_phenoage
plsi report --instance me --map blood_phenoage
```

Canonical CSV header: `effective_at,text,value,unit[,code_system,code,specimen,kind,fasting]`. Units may be written as
labs print them (`mg/dl`, `µmol/l`, `×10⁹/L`, `kg/m²`): `plsi.life.normalize.normalize_unit` gives their UCUM spelling, and
a map converts only through its own sourced factors (a scale, or a scale and an offset) or a generic metric prefix
scale. Grok Bot users start with `plsi.md` instead.

Optional keys go in a gitignored `.env` (copy `.env.example`); the process environment overrides it. `plsi keys status` reports booleans only. A secret the user already has under another name is used through `plsi keys map --name <VAR> --from <their name>` (`plsi keys scan` lists the names); only the names are stored.

## Layout

```
plsi.md  persona.md  AGENTS.md      Grok first-run file, persona, contributor rules
contracts/*.schema.json             generated by `plsi contracts export`
maps/*.yaml                         shipped State Maps
mothership/references/<kind>.yaml   trusted references by id; API base URLs; the Mothership address (contact)
mothership/consent.md               what joining the Longevity Mothership means (versioned)
migration/v<X.Y.Z>.md               moving an earlier install to a version, one `# PLSI vA -> vB` section each (plsi.md step 2)
legal/                              Terms of Service, Privacy Policy and Disclaimer (plsi.md steps 0 and 1)
skills/<role>/<skill>/SKILL.md      one folder per bot: orchestrator/ (Health, and the hub skills every hub shares),
                                    lab/ (Research), clinic/ (Clinic), ward/ (each Ward bot), the workers' folders,
                                    shared/ (team, hub, sessions, l-llm, research-graph)
src/plsi/                           the toolbelt (Packages above)
team.json                           the team every hub shares (`plsi team`; under PLSI_HOME)
instances/<name>/                   subject.json, events.jsonl, maps/user/, states/, reports/, exports/, artifacts/, mothership/
                                    (gitignored; under PLSI_HOME when set)
research/projects/<id>/             one research project: project.md, notes/, data/ and topics/<topic>/ (topic.md,
                                    log.jsonl, questions/ hypotheses/ findings/); day.json beside projects/
                                    (under PLSI_HOME)
targets/<gene>/dossier.json         one target dossier: facts gathered from the free sources, and the bot's
                                    assessment once it passes the refusals (under PLSI_HOME)
```

Contributor and agent rules: [AGENTS.md](AGENTS.md).
