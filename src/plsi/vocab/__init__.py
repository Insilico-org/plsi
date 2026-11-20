"""Every enum in PLSI, nothing enumerated inline elsewhere. The shared vocabularies re-exported here by domain:
`fold` (label folding), `ranked` (the RankedEnum mixin), `team`, `record`, `evidence`, `clinic`, `plan`, `predict`,
`dashboard`, `mothership`, `onboarding`; research and target discovery stay in `vocab.research` and `vocab.targets`,
the lab bench in `vocab.bio` and `vocab.journal`."""

from __future__ import annotations

from plsi.vocab.clinic import *
from plsi.vocab.dashboard import *
from plsi.vocab.evidence import *
from plsi.vocab.fold import fold
from plsi.vocab.mothership import *
from plsi.vocab.onboarding import *
from plsi.vocab.plan import *
from plsi.vocab.predict import *
from plsi.vocab.ranked import RankedEnum
from plsi.vocab.record import *
from plsi.vocab.team import *
