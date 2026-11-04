---
name: research-graph
description: Use when writing to or reading a research topic - the node kinds, the fields each one carries, what `plsi research save` accepts and what it refuses. Read it before any save; the move pages (autopilot/ask, gather, explain, test) say what to produce, this says how it is written down.
---

# The research graph

Follow persona.md norms and `shared/team`. Shared: PLSI Research Autopilot writes it; PLSI, Citizen Researcher,
Challenger and Memory Hole read it.

One topic is one folder under `<PLSI_HOME>/research/`; switching topic is switching folder. Topics never link to
each other, and a topic folder is self-contained (it opens as an Obsidian vault).

```
<PLSI_HOME>/research/
  day.json                 the day's allocation and the week's ceiling, shared by every topic
  notes/<name>.md          research notes from asked sessions - never written by the loop
  <topic>/
    topic.md               the question in chief and the cursor
    log.jsonl              append-only, one line per move
    questions/<title>.md   hypotheses/<title>.md      findings/<title>.md
```

The ledger and the notes sit beside the topics: one allocation covers every topic, and a note can exist without
any topic. A note names its `topic` in frontmatter when one covers its question.

## Notes and findings do not mix

A **note** is one session's graded judgment (`grade`, written by its author). A **finding** is one observation
with its source, counted by `origin` into a `verdict` that nobody writes.

1. **Different stores:** `research/notes/` against `research/<topic>/`.
2. **The loader reads only `questions/`, `hypotheses/` and `findings/`**, and a file is what its frontmatter
   says: a note dropped into `findings/` is skipped with a `FOREIGN_NODE` warning.
3. **Neither bot holds the other's commands.** The loop has `next/save/status`; a session has `notes`.
   Whether a topic already covers a question is PLSI's check (`plsi research propose`), made on the card that
   starts a session.

A note's `grade` and a node's `verdict` never become each other: a note that rests on nodes names them, and the
verdict is read off them.

**A node's name is its title.** No ids or prefixes - `[[Does the effect hold in women]]` reads as a sentence.
`save` checks the name case-insensitively and adds a numeric suffix on a genuine collision; titles are kept as
written, including non-Latin scripts. **Titles are immutable**: a question whose framing changed is a new
question, with the old one `superseded` and cited. **Nothing is deleted**: a node that dies gets
`status: closed` and a reason. `closed` in `plsi research status` lists every resolved question, `answered` ones
included.

You never write a `[[link]]` yourself. Name the other node in the right field and `save` writes the links.

## The four kinds

● required, ○ optional. `save` refuses an unknown field, so this list is exact.

**question** — ● `status` (`open` · `answered` · `superseded` · `closed`), `stakes` (`high` · `some` ·
`low`, ordinal) ○ `parent`, `link` (`decomposes` · `continues` — **recorded at creation; it cannot be worked out
later**), `gap`, `gap_why`, `angle`, `last_search` `{rounds, hits, new}`, `answer`, `cites`, `closed_reason`.

**hypothesis** — ● `question`, `if_false`, `status` (`open` · `superseded` · `closed`) ○ `tested_by` (the
questions that would settle it), `boundaries` `[{between, differ_in, note, spawned}]`, `closed_reason`.

**finding** — ● `question`, `design`, `species`, `sources` `[{id, quote, text}]` ○ `status` (`open` ·
`superseded`, default `open`), `supports` / `contradicts`, `population`, `origin`, `observed`, `studies`.

**`design` and `species` are closed lists**, because code counts on both:

| | values | what it is for |
|---|---|---|
| `design` | `aggregate` · `controlled-trial` · `observational` · `single-arm` · `mechanistic` · `audit` · `narrative-review` · `personal-record` | the shape of the evidence. `aggregate` (pools independent sources) is the only one weighted differently |
| `species` | `human` · `animal` · `in-vitro` · `not-applicable` | what the result is about. `animal` and `in-vitro` sit outside the count; `not-applicable` is for research with no biological subject |

A value outside either list is refused with the list. Detail goes in `population` and the body, which `next`
hands back to you. A closed list cannot catch a wrong value from inside it, so make `population` and the body
say what the source really is.

- **`observed`** is when the thing happened, not when you read it or when a study was registered. On the user's
  own record it carries the temporal order a refutation rests on. On a published finding, fill it only if the
  source says when the measurement was made; otherwise leave it empty.
- **`studies`** is a descriptor only. An aggregate weighs the minimum that means replicated, whatever it pools.
- **Weight is not independence.** `supported` needs **two distinct origins**, whatever they weigh: an aggregate
  weighs 2 and is still one source.
- **`supports` and `contradicts` are the only links you type**, usually in Test by `update`, since the
  hypotheses do not exist yet at Gather. Same for `tested_by`: leave it empty until the settling question exists.
  A link must resolve at the moment it is saved (refusal 6).
- **`quote_verified` is not yours to write.** Pass the retrieved text as the source's `text`; code checks the
  quote against it (ignoring markup, case, spacing and punctuation) and drops the text. No `text` means
  unverified, the honest state for the user's own record and for private sources.

**topic** — written by `plsi research topic`; you never edit it. Its **`depth`** is the user's decision:

| `depth` | a leaf is answerable without a candidate when… | the topic is finished when an answer reaches… |
|---|---|---|
| `fast` | one independent line bears on it | any answer at all |
| `standard` (default) | two independent lines bear on it | `thin` |
| `deep` | never — every direction goes through Explain | `supported` |
| `exhaustive` | never | `supported`, with more room to branch |

`next` returns it as `depth` and `answer_must_reach`, and sizes the advisory `limits` from it. A topic short of
its bar ends `exhausted`; the user may lower it with `plsi research topic --switch '<topic>' --depth standard`.
The user may reframe the `question_in_chief` through PLSI (`plsi research reframe --question … --because …`):
the old wording is kept in `superseded` and the graph is untouched.

## Three kinds of label

| | Example | Rule |
|---|---|---|
| **describes** | `gap_why`, `angle`, `population`, the body | free; it only has to be true |
| **decides** | `origin`, `design`, `species`, `gap` | counted, so closed where a list exists, canonicalised otherwise, and reused exactly |
| **computed** | `verdict`, `route`, the ranking | never yours to write |

`angle` and `gap` are open vocabularies: if no canonical word fits, write the true one and give one line of
`gap_why`. Canonical gaps: `unsearched` · `unstudied` · `nothing-usable` · `unexplained` · `unreplicated` ·
`surrogate-only` · `disputed`. Usual angles: `mechanism` · `magnitude` · `boundary` · `alternative` · `harm`.
`gap` is compared after folding case, spacing and hyphens, because refusal 3 and the ranking read it.

**`origin` is the independence key.** The count is distinct origins. It is the narrowest shared source of the
result: a named cohort, else the trial, else the consortium, else the research group. `next` hands you
`origins_in_use`; reuse the exact string for a source already in the topic. Mechanical variation is absorbed
(`NCT01234567`, `NCT 01234567`, `nct01234567` are one trial), but a second wording ("the bone study") is a
phantom independent line nothing can catch. If you cannot tell, leave it empty: findings with no origin collapse
into a single line between them.

## What code computes, so you never write it

`verdict` (`untested` · `thin` · `supported` · `contested` · `refuted`; `supported` is the ceiling), the count of
independent lines, the `gap` for every case except `surrogate-only`, the `route`, the frontier and its ranking,
and whether a parent is ready to roll up. None is stored; all are recomputed from the files every time.

## The two calls

```bash
plsi research next --topic "<topic>" --usage <percent of this week's limit used>
plsi research save --topic "<topic>" --file move.json
```

`next` hands over everything one move needs: the question in chief, the current question, the move due, the
budget, the ranked frontier, and the findings and hypotheses for this question. Do not walk the folder. In it:

- **`note`** on each node: what was written in its body (a search strategy composed in Ask, for example).
- **`already_tried`**: the `open` and `dropped` sections of the last three moves on this direction.
- **`children_resolved`** on a question that is `ready_to_answer`: the resolved children with answers and
  verdicts.
- **`budget.affordable`**: which moves the remainder can fund, with their estimates.
- **`closed`**: the five most recent, with `closed_total`; the full list is in `plsi research status`.

`save` takes one object:

```json
{
  "move": "gather",
  "usage": 41.5,
  "chars_in": 38000, "chars_out": 5200,
  "nodes":  [{"kind": "finding", "title": "...", "...": "...", "body": "one or two plain lines"}],
  "update": [{"name": "<an existing node>", "status": "closed", "closed_reason": "..."}],
  "expanded": "...", "dropped": "...", "open": "...", "requests": "...",
  "question": "<the question you worked, if not the one next suggested>",
  "close_direction": "asked and answered; nothing further here would change it"
}
```

- **`usage` is required**: the meter reading taken after the move. A save without it is refused. A reading
  lower than the last one charges nothing and ends the run (the week reset, or the reading was wrong).
- A link may name an existing node or a node created in the same save.
- **Take the name to link by from the reply's `change.created`.** A title over 150 bytes is shortened at a word
  boundary with a `TITLE_SHORTENED` warning.
- **`open`**: what you did not get to, every time.
- **The move and the direction are yours.** `next` recommends; `save` takes whichever you worked. Name the
  question if it is not the one suggested; the divergence is counted, not argued with.
- **`close_direction`** finishes the question you are on, and only you write it. `signals` in the reply (a quiet
  round, two empty rounds) are observations, not actions. `stop` is not a save field; the run ends when `next`
  returns one.
- **The `gap` you write is the gap.** Code fills it only when you leave it blank.

## What save refuses

There is no override, and none of these is about research judgment.

| | Refused | Because |
|---|---|---|
| 1 | a finding with no source id, or a source with no verbatim quote | fabrication |
| 2 | a hypothesis with no `if_false` | unfalsifiable |
| 3 | `gap: unstudied` with fewer than two recorded search rounds | "none found" has to be earned |
| 4 | an `answer` that `cites` nothing, or a topic that rests on nothing; a `personal_data` or `personal_case` topic must point at data that resolves | an unsupported claim |
| 5 | a finding saved from a search that returned nothing, or from a gather with no `last_search` (the user's own record is exempt) | with retrieval empty, models answer from memory; a genuine zero is recorded as an absence |
| 6 | a link to, or an update of, a node that does not exist | graph corruption |
| 7 | a `verdict`, or a verdict word used as a `status` | it is arithmetic |
| — | a value outside a closed list (`CLOSED_VOCABULARY`), checked only on what your payload writes | code counts on it |
| — | a save with no `usage` reading, or one that is not a percent from 0 to 100 | every move is charged to the meter |
| — | a save that no `next` started (`NEXT_REQUIRED`): research Off, the topic parked or done, no day open today, or two saves with no `next` between | `next` is where the day, the week and Off are checked |

A refusal returns every violation at once and writes nothing: fix them together and save again.

The budget is not a refusal: the cost arrives after the work. `next` ends the day before a move starts; a move
`next` started may still be saved when it ran over, and `save` warns when a reading went past the allocation, and the overrun counts against the week's ceiling.

## Reading it without the loop

```bash
plsi research status                 # the answer so far, the frontier, the budget and what it bought
plsi research status --full          # also the log rows, the evidence lines and each finding's source ids
plsi research budget                 # what a day and a week may use
plsi research notes                  # research notes, by topic and status
plsi research retire                 # remove a note marked retire (Memory Hole's)
plsi research topic                  # every topic and its cursor
```

## Rules

- **Nothing about the user leaves the topic folder.** Their own data enters as a finding with
  `design: personal-record`, which may refute a hypothesis but never makes one `supported`: one person is one
  line and the threshold is two.
- One claim per finding; two papers reporting the same result in the same cohort are one finding with two
  sources.
- The report renders locally. Anything for the platform is built only from the public half of a topic and goes
  through Data Controller (`controller/egress`); personal findings are referred to by name, never quoted.
