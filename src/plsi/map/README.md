# plsi.map

The Map layer: State Maps (maps/*.yaml and an instance's maps/user/), the projection of the event log into state
documents, the clocks and the calculators. Commands are listed in `src/plsi/commands.py` (`plsi maps ...`, `project`,
`state show`, `handoff check`, `calc ...`, `clocks list`).

| Module | Role |
|---|---|
| `models` | `MapContract` and its coordinates, `StateDocument`, `CoordinateValue`, `CareContext` |
| `registry` | loading, validating, installing and snapshotting maps; `maps list/show/validate/install/select` |
| `projection` | one map over the active observations: accepted observations, measured and derived values, their days |
| `mapper` | `plsi project` (state, storyline), and Policy's one view of the world (see below) |
| `derive` | the derive engines (native, expr, extension, biolearn), blood PhenoAge, censored-input bounds |
| `formula` | safe arithmetic formulas for `engine: expr` |
| `units` | scaling into a coordinate's canonical unit (identity, a sourced conversion, a generic UCUM scale) |
| `biolearn` | the adapter for biolearn's methylation clocks (the `clocks` extra) |
| `bioage` | blood PhenoAge for a dashboard: the age, each marker's share, a what-if |
| `calc` | `calc convert`, `calc place`, `calc derive` |
| `ranges`, `course`, `survival` | `calc range`, `calc course`, `calc survival` (with the bundled UN WPP 2024 snapshot in `data/`) |
| `protocol` | the handoff messages between bots (`state show`, `handoff check`) |

Rules:

- Map is the only projection layer. Policy reads the world only through `mapper` (states, care context, subject,
  scoring values) and appends its own events through `mapper.event_store`; it never imports `plsi.life`.
- Map reads the log through `plsi.life.store.EventStore` and never writes observations.
- Values are never invented: units convert only through `units`, derived values only through a `derive` engine.
- A shipped map edit changes its hash, so it needs a `map_version` bump; snapshots are written once and never re-expanded.
