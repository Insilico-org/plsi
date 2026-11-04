"""The research vocabulary: node kinds and statuses, moves, verdicts and the closed finding fields."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from plsi.vocab import fold


class ResearchNodeKind(StrEnum):
    """The four kinds of node in a research topic (<PLSI_HOME>/research/<topic>, `plsi research next/save`).
    A paper is a source inside a finding, a search is a line in the log, a test is a question."""

    TOPIC = "topic"  # the topic page: the question in chief, the cursor, the depth
    QUESTION = "question"
    HYPOTHESIS = "hypothesis"  # a candidate account, with what we would see if it were false
    FINDING = "finding"  # what was observed, in whom, and where it came from


class ResearchStatus(StrEnum):
    """One state machine for every node kind; KIND_STATUSES says which values each kind may take."""

    OPEN = "open"  # not worked on yet
    ACTIVE = "active"  # the topic being worked on
    ANSWERED = "answered"  # a question with an answer line
    DONE = "done"  # a topic whose question in chief is answered and which has nothing open under it
    PARKED = "parked"  # a topic waiting for budget or for the user
    SUPERSEDED = "superseded"  # reworded or sharpened; the replacement cites it
    CLOSED = "closed"  # dead, with a reason. Nothing is ever deleted


KIND_STATUSES: dict[ResearchNodeKind, frozenset[ResearchStatus]] = {
    ResearchNodeKind.TOPIC: frozenset({ResearchStatus.ACTIVE, ResearchStatus.PARKED, ResearchStatus.DONE}),
    ResearchNodeKind.QUESTION: frozenset({ResearchStatus.OPEN, ResearchStatus.ANSWERED, ResearchStatus.SUPERSEDED,
                                          ResearchStatus.CLOSED}),
    ResearchNodeKind.HYPOTHESIS: frozenset({ResearchStatus.OPEN, ResearchStatus.SUPERSEDED, ResearchStatus.CLOSED}),
    ResearchNodeKind.FINDING: frozenset({ResearchStatus.OPEN, ResearchStatus.SUPERSEDED}),
}
LIVE = frozenset({ResearchStatus.OPEN})  # a node still in play
RESOLVED = frozenset({ResearchStatus.ANSWERED, ResearchStatus.CLOSED, ResearchStatus.SUPERSEDED})


class TopicSource(StrEnum):
    """Where a research topic came from: which kind of question the user ended up with."""

    PERSONAL_DATA = "personal_data"  # a question the user's own record raises: a gap in a map, a marker that moved
    PERSONAL_CASE = "personal_case"  # a decision in their life: a prescription, a diagnosis, a therapy started
    OPEN_QUESTION = "open_question"  # unsettled in the field, independent of this person


PERSONAL_SOURCES = frozenset({TopicSource.PERSONAL_DATA, TopicSource.PERSONAL_CASE})


class ResearchMove(StrEnum):
    """The four research moves, taken in whatever order the research needs."""

    ASK = "ask"  # what specifically don't we know -> questions
    GATHER = "gather"  # what is already known -> findings
    EXPLAIN = "explain"  # what could account for this -> hypotheses
    TEST = "test"  # which evidence separates them -> statuses, boundaries, the answer


class ResearchVerdict(StrEnum):
    """Computed from the counts, never written by a bot and never stored. `supported` is the ceiling."""

    # member order is significant: weakest first (rank 0 .. 4)
    REFUTED = "refuted"  # contradiction only
    UNTESTED = "untested"  # no findings yet
    CONTESTED = "contested"  # support and contradiction both survive the context question
    THIN = "thin"  # one independent line
    SUPPORTED = "supported"  # two or more independent lines, no live contradiction

    @property
    def rank(self) -> int:
        return list(ResearchVerdict).index(self)


class ResearchRoute(StrEnum):
    """How much is left to do on a direction. Descriptive only: it never picks the move."""

    ABSENT = "absent"  # two vocabularies, zero hits: the absence is the result
    SETTLED = "settled"  # an aggregate source: pooled evidence, answerable as it stands
    SHALLOW = "shallow"  # the candidates already standing agree with the evidence
    DEEP = "deep"  # thin, disputed or surrogate-only: the full loop


class QuestionLink(StrEnum):
    """How a child question hangs off its parent. Recorded at creation; it cannot be inferred later."""

    DECOMPOSES = "decomposes"  # a part of the parent; the parent waits for it and then rolls up
    CONTINUES = "continues"  # the branch goes on from a parent that was already answered


class ResearchDepth(StrEnum):
    """How thorough a topic is meant to be: the user's word, set on the topic and changeable at any time.
    It never picks a move; it sets how strong an answer must be and the advisory tree shape."""

    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    EXHAUSTIVE = "exhaustive"


class Stakes(StrEnum):
    """Ordinal only: would resolving this change the answer in chief? Never a score."""

    HIGH = "high"
    SOME = "some"
    LOW = "low"


class ResearchGap(StrEnum):
    """Why a direction is open. An open vocabulary: these are the canonical labels, any other label is kept as
    written and flagged novel. Code computes all but `surrogate-only`, which only the bot can see."""

    UNSEARCHED = "unsearched"  # no search recorded yet
    UNSTUDIED = "unstudied"  # searched, nothing retrieved
    NOTHING_USABLE = "nothing-usable"  # searched, hits, nothing usable in them
    UNEXPLAINED = "unexplained"  # evidence is in and no candidate accounts for it
    UNREPLICATED = "unreplicated"  # no candidate rests on more than one line
    SURROGATE_ONLY = "surrogate-only"  # the evidence measures a surrogate, not the outcome
    DISPUTED = "disputed"  # a candidate is contested

    @classmethod
    def canonical(cls, label: Any) -> str:
        """A gap label in its canonical spelling (`Unstudied`, `un-studied` and `unstudied` are one word); a
        label that matches nothing is returned as written."""
        return next((str(gap) for gap in cls if fold(gap) == fold(label)), str(label or ""))


class ResearchAngle(StrEnum):
    """The angle a question takes on its parent. Open like `gap`: other labels are kept as written."""

    MECHANISM = "mechanism"
    MAGNITUDE = "magnitude"
    BOUNDARY = "boundary"
    ALTERNATIVE = "alternative"
    HARM = "harm"


class ResearchStop(StrEnum):
    """Why `research next` returned a stop instead of a move."""

    DONE = "done"  # the topic is finished
    PARKED = "parked"  # the topic is not active
    METER = "meter"  # a usage reading went backwards; the next day opens fresh
    OFF = "off"  # research has no share of the meter
    HEADROOM = "headroom"  # the user's reserve of the weekly meter would be touched
    CEILING = "ceiling"  # research has used its share of the week
    STUCK = "stuck"  # the first move failed to save too many times
    BUDGET = "budget"  # today's allocation is spent
    ANSWERED = "answered"  # the question in chief is answered and nothing is open under it
    EXHAUSTED = "exhausted"  # the frontier emptied short of an answer at the topic's depth


class ResearchLogEvent(StrEnum):
    """Non-move lines in a topic's log.jsonl (a move line carries `move` instead)."""

    DAY = "day"  # a research day opened at a usage reading
    READING = "reading"  # a usage reading taken on `next`, charging work no save recorded
    STOP = "stop"
    GAVE_UP = "gave_up"  # a direction closed after repeated unsaved attempts
    PIVOT = "pivot"  # a direction closed after moves that changed nothing
    SWITCHED = "switched"
    PARKED = "parked"
    REFRAMED = "reframed"
    DEPTH = "depth"
    BUDGET = "budget"


class ResearchSpend(StrEnum):
    """What a move's cost bought, as segmented in the progress bar."""

    FOUND = "added findings"
    CLOSED = "closed a direction"
    NOTHING = "changed nothing"


class ResearchContinuation(StrEnum):
    """Kinds of suggestion offered when a topic's frontier empties; each is read off what the graph recorded."""

    UNTESTED = "untested hypothesis"
    BOUNDARY = "boundary never followed"
    ABSENT = "nothing published"
    ANGLE = "angle never asked"


# `design` and `species` decide whether a finding counts, so both are closed. Detail belongs in `population`
# and in the node body.
class ResearchDesign(StrEnum):
    AGGREGATE = "aggregate"  # pools sources that were independent of each other
    CONTROLLED_TRIAL = "controlled-trial"
    OBSERVATIONAL = "observational"
    SINGLE_ARM = "single-arm"
    MECHANISTIC = "mechanistic"
    AUDIT = "audit"
    NARRATIVE_REVIEW = "narrative-review"
    PERSONAL_RECORD = "personal-record"  # the user's own record: may refute, never supports


class ResearchSpecies(StrEnum):
    """What the result is about. `not-applicable` is for research with no biological subject."""

    HUMAN = "human"
    ANIMAL = "animal"
    IN_VITRO = "in-vitro"
    NOT_APPLICABLE = "not-applicable"


# Results about something else: kept and shown, never counted for a claim about people.
OFF_TARGET_SPECIES = frozenset({ResearchSpecies.ANIMAL, ResearchSpecies.IN_VITRO})


class ResearchNoteStatus(StrEnum):
    """A research note in research/notes/: the unit PLSI Challenger evaluates and the Longevity Mothership
    receives."""

    ACTIVE = "active"
    READY = "ready"  # complete enough for PLSI Challenger (Note mode)
    SUBMITTED = "submitted"  # emailed to the Mothership
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RETIRE = "retire"  # duplicate, off-topic or obsolete: PLSI Memory Hole removes it (`plsi research retire`)
