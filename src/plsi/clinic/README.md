# plsi.clinic

The physician's clinic (skills `panel/*`, commands `plsi clinic ...`). Each patient on the panel has a roster row in
`<PLSI_HOME>/work/panel/roster.json` and two folders on the clinic shared drive: an inbox the patient uploads to and a
shared folder the patient reads. Every sync and publish outcome is a line of `<PLSI_HOME>/work/panel/synced.jsonl`.
A patient's email address is used for the share only and never stored.

| Module | Holds | Commands |
|---|---|---|
| `drive.py` | the Google Drive client (service account, token signed locally), the Drive id pattern | |
| `roster.py` | roster rows and their checks, folder sharing rules, the ledger, routing synced files | `check`, `link`, `sharing`, `sync` |
| `publish.py` | what the service account writes: the folders, the share, an approved report | `setup`, `share`, `publish` |
| `patient.py` | one patient's records as the dashboard reads them: grouped, one series per test | |
| `dashboard.py` | the panel dashboard (`<PLSI_HOME>/work/clinic-dashboard/dashboard.html`) and its rebuild after a command that changes records | `dashboard` |

Imports run one way: `drive` <- `roster` <- `publish`, and `roster` <- `patient` <- `dashboard`. The dashboard is
drawn with the blocks of `plsi.report`.
