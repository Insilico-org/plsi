"""The `plsi journal` command table: the wet-lab journal (entries, plasmids, the page) and the bench calculators."""

from __future__ import annotations

from plsi.cmdspec import FILE, MX, A, Cmd, V, iso_date
from plsi.vocab import LivePage
from plsi.vocab.journal import CalcKind, ExperimentKind

JOURNAL = LivePage.JOURNAL

ENTRY = A("--entry", required=True, help="the entry id")

COMMANDS: dict[str, Cmd] = {
    "journal template": Cmd("plsi.journal.store:template", (A("--kind", required=True, choices=V(ExperimentKind)),),
                            "a starter entry for one kind of experiment, to fill in and save",
                            ("plsi journal save --file <entry.json>",)),
    "journal save": Cmd("plsi.journal.store:save", (FILE,),
                        "save an entry (EntryInput JSON): the first version, or the next of an unsigned one",
                        ("plsi journal page",), refresh=JOURNAL),
    "journal list": Cmd("plsi.journal.store:list_entries",
                        (A("--project"), A("--kind", choices=V(ExperimentKind))), "entries, newest first"),
    "journal show": Cmd("plsi.journal.store:show", (ENTRY,), "one entry with its derived numbers, checks and history"),
    "journal sign": Cmd("plsi.journal.store:sign",
                        (ENTRY, A("--by", required=True, help="the scientist's name, as they gave it"),
                         A("--witness", help="a second person's name, when one witnessed it")),
                        "sign an entry the user approved: it never changes again", ("plsi journal page",), refresh=JOURNAL),
    "journal attach": Cmd("plsi.journal.store:attach",
                          (ENTRY, A("--file", required=True, help="the file on this computer"),
                           A("--name", help="the name to keep it under")),
                          "keep a gel photo, micrograph, export or trace with an unsigned entry",
                          ("plsi journal save --file <entry.json>",), refresh=JOURNAL),
    "journal calc": Cmd("plsi.journal.calc:calc",
                        (A("--kind", required=True, choices=V(CalcKind)),
                         A("--set", dest="set_values", action="append", help="name=quantity, e.g. c1='10 mM' (repeatable)"),
                         A("--file", help="the inputs as JSON (lists: mastermix components, protein_load samples)")),
                        "bench arithmetic with its steps (writes nothing)"),
    "journal plasmid save": Cmd("plsi.journal.plasmid:save",
                                (MX(A("--file", help="Plasmid JSON"), A("--genbank", help="a GenBank file (.gb, .gbk)")),
                                 A("--name", help="short lower-case name (with --genbank)")),
                                "save a plasmid: its map, features and restriction sites", ("plsi journal page",), refresh=JOURNAL),
    "journal plasmid list": Cmd("plsi.journal.plasmid:list_saved", (), "saved plasmids"),
    "journal plasmid show": Cmd("plsi.journal.plasmid:show",
                                (A("--name", required=True),
                                 A("--region", help="start-end, e.g. 1984-2048: enzymes cutting once in the plasmid, inside it")),
                                "one plasmid with its features, the enzymes that cut it, their ends and overhangs"),
    "journal day save": Cmd("plsi.journal.days:save", (FILE,),
                            "save the plan of one day (DayPlan JSON: items with time, entry, project, done); replaces it",
                            ("plsi journal today",), refresh=JOURNAL),
    "journal today": Cmd("plsi.journal.days:today", (A("--date", type=iso_date, help="YYYY-MM-DD (default today)"),),
                         "the day: its plan, running experiments and their next step, entries of the day, flags, the week ahead"),
    "journal bank": Cmd("plsi.journal.store:bank", (),
                        "the cell bank: every frozen vial at its latest record, by box and position; stock per line and passage"),
    "journal page": Cmd("plsi.journal.page:page", (), "rewrite the lab journal page (one HTML file) in place"),
}
