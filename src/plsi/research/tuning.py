"""Every number the loop is tuned by: what each depth asks for, the budget's multiples (in percentage points of
the weekly meter), when a direction is given up, and how much of the graph one reply carries."""

from __future__ import annotations

from plsi.vocab.research import ResearchDepth, ResearchVerdict

DEFAULT_DEPTH = ResearchDepth.STANDARD
# The weakest verdict an answer may have for the topic to finish as `answered`; `None` is no bar. Below the
# floor the topic ends `exhausted` once the frontier empties. `fast` has no bar because `refuted` is a real
# result and ranks lowest.
DEPTH_FLOOR: dict[ResearchDepth, ResearchVerdict | None] = {
    ResearchDepth.FAST: None, ResearchDepth.STANDARD: ResearchVerdict.THIN,
    ResearchDepth.DEEP: ResearchVerdict.SUPPORTED, ResearchDepth.EXHAUSTIVE: ResearchVerdict.SUPPORTED}
# How many independent lines make a leaf answerable without proposing a candidate; `None` means never, so the
# direction goes through Explain. Above `standard` it is off because findings alone stop at `thin`, below the
# `supported` floor those depths require.
DEPTH_ANSWER_FROM_FINDINGS: dict[ResearchDepth, int | None] = {
    ResearchDepth.FAST: 1, ResearchDepth.STANDARD: 2, ResearchDepth.DEEP: None, ResearchDepth.EXHAUSTIVE: None}
# (max depth, max breadth): advisory, reported in `limits` and enforced by nothing. The agent decomposes.
DEPTH_LIMITS = {ResearchDepth.FAST: (1, 3), ResearchDepth.STANDARD: (3, 5),
                ResearchDepth.DEEP: (4, 6), ResearchDepth.EXHAUSTIVE: (5, 8)}
DEPTH_WORDS = {
    ResearchDepth.FAST: "one pass. Whatever answer the evidence allows, including a thin one",
    ResearchDepth.STANDARD: "an answer has to rest on something before the topic is finished",
    ResearchDepth.DEEP: "replication before the topic is finished, and every direction goes through Explain",
    ResearchDepth.EXHAUSTIVE: "the same bar as deep, with more room to branch",
}

AGGREGATE_WEIGHT = 2  # replicated by construction; never the pooled count, which is a number nobody can check
MIN_ABSENCE_ROUNDS = 2  # "none found" is earned by two rounds with different vocabularies, not by one
STAGNATION_NOVELTY = 0.2  # a gather whose new share of hits is below this is quiet
ADOPT_AFTER = 2  # a novel gap label used this many times is offered for adoption

SEED_COST = 1.0  # a move's estimate until one has been observed
SEED_RUN_COST = 0.25  # a research run's cost until runs have been measured (about 0.2-0.3 of the weekly meter)
MOVES_PER_DIRECTION = 3.5  # typical moves to bring one direction to a verdict
CEILING_MULTIPLE = 4.0  # the default weekly ceiling, in days' worth of the daily share
HEADROOM = 10.0  # of the weekly meter, kept back for the user whatever the share is
MAX_ATTEMPTS = 3  # unsaved attempts on one direction before it is closed as stuck
UNPRODUCTIVE_STOP = 3  # moves in a row on one direction that changed nothing before it is closed
CONTINUATIONS_MAX = 8  # continuations offered once the frontier empties

# the research chain: one run at a time, each on one project, the next asked for at the end of the last
RUN_MINUTES = 10  # a run's time box: `next` says `time_box` after it; it ends sooner when code says stop
OPEN_RUN_STALE_MIN = 30  # a run with no start, `next` or save for this long counts as dead (one move takes minutes)
RUN_CAP_MULTIPLE, RUN_CAP_MIN = 3, 6  # runs a day may take: this many times the runs the day's target expects
KICK_STALE_MIN = 5  # a kicked run that has not started after this long is asked for again (runs start 5-9 s later)
KICK_TIMEOUT_S = 15.0  # the webhook POST that asks for the next run
START_HOUR = 6  # UTC hour a new research day may start, unless the user set another (`budget --start-hour`)
# the research inbox (inbox.py) and its question form, within Grok's limits
STALLED_DAYS = 14  # an active topic with no move for this long is stalled
HELD_DAYS = 14  # a project on hold this long is raised again
FORM_PAGES, FORM_OPTIONS = 8, 6  # a Grok form: 2-8 pages, one question each, up to 6 options per page

# what one `next` or `save` reply carries; `research status` carries everything
FRONTIER_IN_CONTEXT = 12  # open directions; `frontier_total` says how many were not sent
CLOSED_IN_CONTEXT, CLOSED_REASON_CHARS = 5, 200
WORKING_SET_MAX, NOTE_CHARS = 40, 1400  # findings in the working set; characters of a node's body
TRIED_MOVES, TRIED_CHARS = 3, 900  # moves in `already_tried`; characters per section

# `research discover`: the candidate band, in papers per relation and absolute whatever the subject. Below
# MIN_SUPPORT a relation is mostly extraction noise; from WELL_STUDIED up it is what the field has already settled.
MIN_SUPPORT, THINLY_STUDIED, WELL_STUDIED = 3, 25, 50
MAX_CANDIDATES, DEFAULT_CANDIDATES = 12, 6  # candidates one discover returns
SUPPORT_FOR, SUPPORT_PAPERS = 5, 3  # candidates that get their papers fetched (one request each, at 3/s); papers each
TRIALS_MAX = 10  # trials `--trials` lists
# `research propose`
MOVED_BY = 0.2  # a coordinate whose series changed by this fraction is worth a question
MAX_PER_KIND = 6  # candidates of each kind on the card
