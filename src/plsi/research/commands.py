"""The `plsi research` command table: the research loop, its projects, topics and budget, and the research
notes."""

from __future__ import annotations

from plsi.cmdspec import A, MX, V, Cmd
from plsi.research.tuning import DEFAULT_CANDIDATES, MAX_CANDIDATES
from plsi.vocab.research import ResearchDepth, ResearchNoteStatus, TopicSource

PROJECT = A("--project", help="the project, its id or title (default: the only active project)")
NOTE_PROJECT = A("--project", help="its id or title, when two projects have a note of that name")

COMMANDS: dict[str, Cmd] = {
    # research projects (<PLSI_HOME>/research/projects/<project>/): topics/, notes/ and data/ in each;
    # `next` and `save` run the loop on a project's topic, the rest are for the user
    "research project": Cmd("plsi.research.status:project",
                            (MX(A("--new", help="title of a new project; other projects are not touched"),
                                A("--close", help="close this project (its id or title); everything in it stays"),
                                A("--reopen", help="make this closed project active again (its id or title)"),
                                A("--show", help="the project map: topics, notes, links, what was sent, next steps"),
                                A("--adopt", action="store_true",
                                  help="move research from before projects into project folders (Earlier research)"),
                                required=False),
                             A("--aim", help="one line: what the project is for (with --new)")),
                            "list research projects, or create, close, reopen, show or adopt them",
                            ("plsi research project --show '<project>'",)),
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
                           A("--project", help="the project: where --new makes the topic, whose active topic --depth "
                                               "changes, or whose topics are listed (default: the only active one)"),
                           A("--topic", help="the topic --depth applies to (default: the project's active one)"),
                           A("--reason", help="why it is parked")),
                          "list research topics, or create, switch to or park one",
                          ("plsi research next --topic '{new}' --usage <percent used this week>",)),
    "research reframe": Cmd("plsi.research.topics:reframe",
                            (A("--question", required=True, help="the question in chief, as it should now read"),
                             A("--because", required=True, help="one line: what the research learned that changed it"),
                             A("--topic",), PROJECT),
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
                              A("--limit", type=int,
                                help=f"how many candidates (1-{MAX_CANDIDATES}, default {DEFAULT_CANDIDATES})"),
                              A("--trials", action="store_true",
                                help="also what ClinicalTrials.gov says is being asked right now")),
                             "what is asserted about a subject and where it thins out; chooses nothing",
                             ("plsi research topic --new '<title>' --question '<q>' --kind open_question "
                              "--because '<why now>' --rests-on PMID:<id> --depth <how thorough>",)),
    "research budget": Cmd("plsi.research.topics:set_budget",
                           (A("--share", type=float, help="percent of the weekly meter research may use per day"),
                            A("--ceiling", type=float,
                              help="percent of the weekly meter research may use in a week; "
                                   "left alone it is four days' worth of --share"),
                            A("--meter-reset", action="store_true",
                              help="the user confirmed the weekly meter reset: open today and a fresh week at --usage"),
                            A("--usage", type=float,
                              help="percent of this week's limit used, read now (with --meter-reset)"),
                            A("--reserve", type=int,
                              help="hold this many billed PandaOmics Agent runs of today's cap for --project's session"),
                            A("--release", action="store_true", help="give back --project's reserved runs"),
                            A("--project", help="the project a reservation is for (its id or title)")),
                           "show or change what research may spend, per day and per week, across every topic; "
                           "reserve a session's billed runs",
                           ("plsi research status",)),
    "research next": Cmd("plsi.research.loop:next_move",
                         (A("--topic"), A("--usage", type=float, help="percent of this week's limit used, read now; "
                                                                      "required to open a day and after an unsaved move"),
                          PROJECT),
                         "everything the next move needs, in one response",
                         ("plsi research save --topic '{topic}' --file move.json",)),
    "research save": Cmd("plsi.research.save:save",
                         (A("--topic"), A("--file", required=True, help="the move's output ('-' = stdin)"), PROJECT),
                         "record the move, charge the meter and rewrite the frontier",
                         ("plsi research next --topic '{topic}'",)),
    "research status": Cmd("plsi.research.status:status",
                           (A("--topic"), A("--full", action="store_true",
                                            help="also every log row (what each move cost and changed), the "
                                                 "evidence for and against each hypothesis and each finding's "
                                                 "source ids"),
                            PROJECT),
                           "where a topic stands: the question, the answer so far, the frontier, the budget and what it "
                           "bought; a project's whole view is `research project --show`"),
    # the research note: written by a bot in its project's notes/, reviewed by Challenger, received by the Mothership
    "research notes": Cmd("plsi.research.notes:list_notes",
                          (A("--topic"), A("--status", choices=V(ResearchNoteStatus)),
                           A("--project", help="its id or title (default: every project's notes)")),
                          "research notes, filtered by project, topic and status"),
    "research check": Cmd("plsi.research.notes:check",
                          (A("--name", required=True, help="the note's file name without .md"),
                           NOTE_PROJECT),
                          "check that a research note parses and has every field: run after writing or editing one",
                          ("plsi research notes",)),
    "research mark": Cmd("plsi.research.notes:mark",
                         (A("--name", required=True, help="the note's file name without .md"),
                          A("--status", required=True, choices=V(ResearchNoteStatus)),
                          A("--reason", help="why a note is retired (with retire), or the Mothership's reason (with accepted or rejected)"),
                          NOTE_PROJECT),
                         "set a research note's status: submitted after the send, accepted or rejected on a "
                         "Mothership decision that quotes its kept receipt, retire with a reason",
                         ("plsi research notes",)),
    "research retire": Cmd("plsi.research.notes:retire",
                           (A("--name", required=True, help="note marked status: retire"), A("--topic"),
                            A("--reason", help="one line, logged in the project's notes/retired.md"),
                            NOTE_PROJECT),
                           "remove a retired research note"),
}
