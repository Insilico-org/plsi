"""The `plsi targets` command table: gathering and judging target dossiers from free sources."""

from __future__ import annotations

from plsi.cmdspec import FILE, A, V, Cmd
from plsi.vocab.targets import AgingHallmark, TargetBand

COMMANDS: dict[str, Cmd] = {
    # target discovery (<PLSI_HOME>/targets/<gene>): free sources gather and count, the bot judges and is
    # refused when the judgment is not grounded, and `brief` is the one way a dossier reaches the research bots
    "targets discover": Cmd("plsi.targets.discover:discover",
                            (A("--disease", help="the disease, by its clinical name or an EFO/MONDO id"),
                             A("--hallmark", choices=V(AgingHallmark),
                               help="a hallmark of aging instead of a disease: the curated aging genes "
                                    "under it, with no band and no ranking"),
                             A("--limit", type=int, help="candidates to return (1-100)"),
                             A("--depth", type=int, help="ranked rows to search before filtering (1-2000); a "
                                                         "clinical-stage target can rank in the thousands"),
                             A("--find", help="locate one gene symbol in the ranking and report its rank"),
                             A("--aging", dest="aging_only", action="store_true",
                               help="keep only candidates Open Genes curates as aging genes"),
                             A("--band", choices=V(TargetBand),
                               help="show only this band: what has already been tried on the target")),
                            "candidates for a disease from Open Targets, banded by what has been tried on each, "
                            "or the curated aging genes under one hallmark (network, free, no key)",
                            ("plsi targets dossier --gene <SYMBOL> --disease '{disease}'",)),
    "targets dossier": Cmd("plsi.targets.dossier:dossier",
                           (A("--gene", required=True, help="HGNC symbol or Ensembl gene id"),
                            A("--disease", help="scope the dossier to one indication; a band needs one"),
                            A("--no-aging", dest="aging_source", action="store_false",
                              help="skip the Open Genes lookup")),
                           "gather one target from the free sources into <PLSI_HOME>/targets/<gene>/ (network)",
                           # the resolved symbol (data.gene) can differ from the name as typed
                           ("plsi targets assess --gene <the resolved symbol in data.gene> --file assessment.json",)),
    "targets assess": Cmd("plsi.targets.assess:assess",
                          (A("--gene", required=True), FILE),
                          "record a bot's judgment on a target; refused whole unless every claim carries a "
                          "source that resolves and the superlatives are earned",
                          ("plsi targets show --gene {gene}",)),
    "targets brief": Cmd("plsi.targets.brief:brief",
                         (A("--gene", required=True),
                          A("--question", help="the research question this is for"),
                          A("--limit", type=int, help="citable rows to return")),
                         "the citable part of a dossier for a research move: claim, identifier and the exact "
                         "record, with what each one is not (writes nothing to a topic or a note)"),
    "targets trials": Cmd("plsi.targets.trials:rollup",
                          (A("--gene", required=True, help="the target the assets are claimed to act on"),
                           A("--asset", dest="assets", action="append", required=True,
                             help="a drug or code name found by hand; repeat for each (1-12)")),
                          "ground harvested asset names on ClinicalTrials.gov: phase, status and sponsor from "
                          "the records, per indication, with the near-misses counted (network; writes nothing)",
                          ("plsi targets assess --gene {gene} --file assessment.json",)),
    "targets show": Cmd("plsi.targets.rank:show", (A("--gene", required=True),),
                        "a stored dossier's identity, computed reads and assessment, read offline (it contacts "
                        "nothing)"),
    "targets unmet": Cmd("plsi.targets.unmet:unmet",
                         (A("--disease", required=True,
                            help="the disease, by its clinical name or an EFO/MONDO id"),),
                         "what an indication already has: approved molecules, how many distinct proteins "
                         "they act on, how deep the pipeline behind them is and how much of it stopped "
                         "(network, free, no key; no unmet-need score is drawn)",
                         ("plsi targets discover --disease '{disease}'",)),
    "targets hallmarks": Cmd("plsi.targets.hallmarks:hallmarks",
                             (A("--gene", required=True),),
                             "which hallmarks of aging a gathered target touches and on which curated "
                             "mechanism each one rests (a lookup over the stored dossier; it contacts "
                             "nothing)",
                             ("plsi targets show --gene {gene}",)),
    "targets list": Cmd("plsi.targets.store:list_dossiers", (), "every stored target dossier, newest first"),
}
