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
MOVES_PER_DIRECTION = 3.5  # typical moves to bring one direction to a verdict
CEILING_MULTIPLE = 4.0  # the default weekly ceiling, in days' worth of the daily share
HEADROOM = 10.0  # of the weekly meter, kept back for the user whatever the share is
MAX_ATTEMPTS = 3  # unsaved attempts on one direction before it is closed as stuck
UNPRODUCTIVE_STOP = 3  # moves in a row on one direction that changed nothing before it is closed
CONTINUATIONS_MAX = 8  # continuations offered once the frontier empties

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
