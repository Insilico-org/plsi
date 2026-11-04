"""The `plsi research` command table: the autoresearch loop, its topics and budget, and the research notes."""

from __future__ import annotations

from plsi.cmdspec import A, MX, V, Cmd
from plsi.vocab.research import ResearchDepth, ResearchNoteStatus, TopicSource

COMMANDS: dict[str, Cmd] = {
    # autoresearch (<PLSI_HOME>/research/<topic>): `next` and `save` run the loop, the rest are for the user
    "research topic": Cmd("plsi.research.topics:topics",
                          (MX(A("--new", help="title of a new topic"), A("--switch", help="make this topic active"),
                              A("--park", help="stop work on this topic; its cursor is kept"), required=False),
                           A("--question", help="the question in chief (with --new)"),
                           A("--kind", choices=V(TopicSource), help="where the topic came from (with --new)"),
                           A("--because", help="one line: why this question, now (with --new)"),
                           A("--rests-on", dest="rests_on", action="append",
                             help="what it rests on, repeatable: medication:<event> | <map>:<coordinate> | PMID:<id> | user"),
                           A("--instance", help="the record a personal topic rests on"),
                           A("--depth", choices=V(ResearchDepth),
                             help="how thorough this topic is: how strong an answer must be before it counts "
                                  "as finished. With --new, or alone to change the topic named by --topic"),
                           A("--topic", help="the topic --depth applies to (default: the active one)"),
                           A("--reason", help="why it is parked")),
                          "list research topics, or create, switch to or park one",
                          ("plsi research next --topic '{new}' --usage <percent used this week>",)),
    "research reframe": Cmd("plsi.research.topics:reframe",
                            (A("--question", required=True, help="the question in chief, as it should now read"),
                             A("--because", required=True, help="one line: what the research learned that changed it"),
                             A("--topic",)),
                            "change a topic's question in chief, keeping the old wording and why it changed",
                            ("plsi research status",)),
    "research propose": Cmd("plsi.research.propose:propose",
                            (A("--instance", help="the person whose record suggests topics"),
                             A("--online", action="store_true", help="also read the Mothership findings ledger")),
                            "grounded candidates for the topic card; chooses nothing",
                            ("plsi research topic --new '<title>' --question '<q>' --kind <kind> --because '<why>'",)),
    "research discover": Cmd("plsi.research.discover:discover",
                             (A("--about", required=True, help="the subject: a drug, a gene, a condition"),
                              A("--entity", help="its PubTator id, when the name does not resolve "
                                                 "(@CHEMICAL_<Name>, @DISEASE_<Name>, @GENE_<SYMBOL>)"),
                              A("--limit", type=int, help="how many candidates (1-12, default 6)"),
                              A("--trials", action="store_true",
                                help="also what ClinicalTrials.gov says is being asked right now")),
                             "what is asserted about a subject and where it thins out; chooses nothing",
                             ("plsi research topic --new '<title>' --question '<q>' --kind open_question "
                              "--because '<why now>' --rests-on PMID:<id> --depth <how thorough>",)),
    "research budget": Cmd("plsi.research.topics:set_budget",
                           (A("--share", type=float, help="percent of the weekly meter research may use per day"),
                            A("--ceiling", type=float,
                              help="percent of the weekly meter research may use in a week; "
                                   "left alone it is four days' worth of --share")),
                           "show or change what research may spend, per day and per week, across every topic",
                           ("plsi research status",)),
    "research next": Cmd("plsi.research.loop:next_move",
                         (A("--topic"), A("--usage", type=float, help="percent of this week's limit used, read now; "
                                                                      "required to open a day and after an unsaved move")),
                         "everything the next move needs, in one response",
                         ("plsi research save --topic '{topic}' --file move.json",)),
    "research save": Cmd("plsi.research.save:save",
                         (A("--topic"), A("--file", required=True, help="the move's output ('-' = stdin)")),
                         "record the move, charge the meter and rewrite the frontier",
                         ("plsi research next --topic '{topic}'",)),
    "research status": Cmd("plsi.research.status:status",
                           (A("--topic"), A("--full", action="store_true",
                                            help="also every log row (what each move cost and changed), the "
                                                 "evidence for and against each hypothesis and each finding's "
                                                 "source ids")),
                           "the question, the answer so far, the frontier, the budget and what it bought"),
    # the research note: written by a bot, reviewed by Challenger, received by the Mothership
    "research notes": Cmd("plsi.research.notes:list_notes",
                          (A("--topic"), A("--status", choices=V(ResearchNoteStatus))),
                          "research notes in research/notes/, filtered by topic and status"),
    "research retire": Cmd("plsi.research.notes:retire",
                           (A("--name", required=True, help="note marked status: retire"), A("--topic"),
                            A("--reason", help="one line, logged in research/notes/retired.md")),
                           "remove a retired research note"),
}
