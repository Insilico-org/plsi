# plsi.mothership

The client of the Longevity Mothership: what PLSI may share, the gate every file passes before it leaves, and the
relay it is sent through. Commands are listed in `commands.py` (`plsi mothership ...`).

| Module | Role |
|---|---|
| `relay` | addresses (mothership/references/contact.yaml), the wire version and message `header`, timings, one POST or GET, refusal errors |
| `scan` | the string, key and number rules of every message: strict loading, NFKC, identifying patterns, instance names, paths |
| `content` | the coded fields a contribution may carry (field tables, codes, bounded numbers) |
| `note` | the optional parts of a research note: item context, report masks, files, project |
| `gate` | the whole gate per message kind: fields, formats, exemptions, consent, identity; `require` raises `GateFailed` |
| `enroll` | consent, the install token and contributor secret, the outbox, the sent log and its receipts |
| `pack` | the deidentified contribution from published states, life events and scores |
| `research` | research notes and registry updates from Explorer's contribution.json; the email draft |
| `attach` | a research note's data files: checked as the Mother checks them, zipped for the email |
| `send` | `check`, `send` and `receipt` against the relay, with the instance's or the professional's token |
| `professional` | the professional token, preregistrations and findings |
| `stats` | the Mother's analyses of a data release (compare_groups, age_trend) |
| `public` | the published catalog, data releases and findings ledger |

Imports run one way: `relay` and `scan` depend on no other module here; `content` and `note` build on `scan`; `stats`
on `content`; `gate` on those and `enroll`; the commands (`pack`, `research`, `send`, `professional`, `public`) on
`gate` and `relay`.
