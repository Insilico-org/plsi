"""The `plsi` command table: every command, the ONE library function ("module:function") it calls,
its arguments, help and the next commands to suggest. plsi.cli parses and dispatches it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from plsi import clock
from plsi.vocab import (ContributionKind, EventType, ExportFormat, ObservationKind, ReferenceKind, Relation, ReportFormat, ResearchItemKind,
                        ResearchStatus, SearchSource, Sex, SourceKind, UserRole)

def iso_datetime(value: str) -> datetime:
    return clock.parse_time(value)


def iso_date(value: str) -> date:
    return date.fromisoformat(value)


def A(*flags: str, **kw: Any) -> tuple[tuple[str, ...], dict[str, Any]]:
    return flags, kw


def V(enum: type[StrEnum]) -> list[str]:
    """argparse choices as plain values (Python 3.11 shows enum members as reprs in usage errors)."""
    return [m.value for m in enum]


def MX(*args: tuple[tuple[str, ...], dict[str, Any]], required: bool = True) -> tuple[str, tuple, bool]:
    return "__mx__", args, required


INSTANCE = A("--instance", required=True, help="instance name")
FILE = A("--file", required=True, help="input path ('-' = stdin)")
PLAN = A("--plan", dest="plan_id", required=True, help="plan id")
MAP = A("--map", dest="map_id", required=True)
MAP_OPT = A("--instance", help="include this instance's user maps")
SENDER = A("--instance", help="the contributor's instance (install token); omit for professional files")


@dataclass(frozen=True)
class Cmd:
    target: str
    args: tuple = ()
    help: str = ""
    next: tuple[str, ...] = ()


COMMANDS: dict[str, Cmd] = {
    # system
    "doctor": Cmd("plsi.doctor:doctor", (A("--online", action="store_true", help="also check reachability of references"),),
                  "versions, extras, PLSI_HOME, keys and fixes", ("plsi keys status",)),
    "keys status": Cmd("plsi.keys:status", (), "which key variables are set (booleans only)"),
    "keys scan": Cmd("plsi.keys:scan", (), "names only: unset key variables, mappings, other secrets present",
                     ("plsi keys map",)),
    "keys map": Cmd("plsi.keys:map_key", (A("--name", required=True, help="PLSI key variable"),
                                          A("--from", dest="source", required=True, help="the user's existing secret's name")),
                    "read a key variable from a secret the user already has (names only)", ("plsi keys status",)),
    "keys unmap": Cmd("plsi.keys:unmap_key", (A("--name", required=True),), "forget a key mapping"),
    "contracts export": Cmd("plsi.schemas:export_json_schemas", (), "write contracts/*.schema.json"),
    "role show": Cmd("plsi.role:show", (), "the user's role (individual, physician or researcher)"),
    "role set": Cmd("plsi.role:set_role", (A("--role", required=True, choices=V(UserRole)),), "store the user's role",
                    ("plsi role show",)),
    # extensions
    "ext list": Cmd("plsi.extensions:list_extensions", (), "installed code extensions and their active versions"),
    "ext install": Cmd("plsi.extensions:install", (A("--dir", required=True, help="extension source directory"),),
                       "check, test and activate a code extension", ("plsi ext list",)),
    "ext test": Cmd("plsi.extensions:test", (A("--id", required=True),), "re-run an extension's tests"),
    "ext disable": Cmd("plsi.extensions:disable", (A("--id", required=True),), "deactivate an extension"),
    # instance and life
    "init": Cmd("plsi.life.store:init_instance",
                (INSTANCE, A("--birth-year", type=int), A("--sex", choices=V(Sex)),
                 A("--relation", choices=V(Relation), help="who this person is to the user"),
                 A("--country", help="ISO 3166 alpha-3 country of residence (life tables, base rates)"), A("--update", action="store_true")),
                "create an instance (existing -> created false)", ("plsi ingest --instance {instance} --file obs.json --dry-run",)),
    "status": Cmd("plsi.cli:instance_status", (INSTANCE,), "instance overview"),
    "instances list": Cmd("plsi.life.store:list_instances", (), "every instance (one per person) with its relation"),
    "instances delete": Cmd("plsi.life.store:delete_instance",
                            (INSTANCE, A("--confirm", required=True, help="repeat the instance name to confirm")),
                            "delete one person's instance for good (export first)", ("plsi instances list",)),
    "events list": Cmd("plsi.life.store:list_events",
                       (INSTANCE, A("--type", choices=V(EventType)),
                        A("--kind", choices=V(ObservationKind)), A("--limit", type=int)),
                       "list events (newest last)"),
    "ingest": Cmd("plsi.life.ingest:ingest",
                  (INSTANCE, MX(A("--file", help="ObservationInput JSON list"), A("--fhir", help="FHIR Bundle JSON"),
                                A("--csv", help="canonical long CSV"), A("--methylation", help="beta matrix CSV"),
                                A("--ext", help="importer extension id (with --input)")),
                   A("--input", help="file read by the --ext importer"),
                   A("--sample", help="methylation sample column"), A("--effective-at", type=iso_datetime, help="methylation draw date"),
                   A("--update", action="store_true", help="let FHIR Patient fields change subject.json"),
                   A("--dry-run", action="store_true")),
                  "ingest observations", ("plsi maps select --instance {instance}",)),
    "normalize observations": Cmd("plsi.life.normalize:normalize_observations",
                                  (A("--in", dest="in_path", required=True, help="ObservationInput JSON list ('-' = stdin)"),
                                   A("--out", dest="out_path", required=True, help="output JSON path")),
                                  "LOINC/RxNorm-code observations (network)", ("plsi ingest --instance <name> --file {out_path} --dry-run",)),
    "retract": Cmd("plsi.life.ingest:retract",
                   (INSTANCE, A("--event", dest="event_id", required=True), FILE, A("--replacement", help="ObservationInput JSON")),
                   "retract an event (events.jsonl is never edited)"),
    # map
    "maps list": Cmd("plsi.map.registry:list_maps", (MAP_OPT,), "list State Maps"),
    "maps show": Cmd("plsi.map.registry:show", (A("map_id", metavar="ID"), MAP_OPT), "show one map"),
    "maps validate": Cmd("plsi.map.registry:validate_file", (A("file", metavar="FILE"), A("--live", action="store_true")),
                         "validate a map file", ("plsi maps install --instance <name> --file {file}",)),
    "maps install": Cmd("plsi.map.registry:install", (INSTANCE, FILE), "install a user map",
                        ("plsi project --instance {instance} --map <map_id>",)),
    "maps select": Cmd("plsi.map.registry:select", (INSTANCE,), "coverage of every map for this instance",
                       ("plsi project --instance {instance} --map <map_id>",)),
    "project": Cmd("plsi.map.mapper:project",
                   (INSTANCE, MAP, A("--as-of", type=iso_datetime),
                    A("--no-storyline", dest="storyline", action="store_false")),
                   "project the log into a state document", ("plsi report --instance {instance} --map {map_id}",)),
    "state show": Cmd("plsi.map.protocol:published", (INSTANCE, MAP),
                      "the last published state document (read-only)"),
    "handoff check": Cmd("plsi.map.protocol:check", (FILE,), "validate a handoff message between PLSI bots"),
    "calc convert": Cmd("plsi.map.calc:convert",
                        (MAP, A("--coordinate", required=True), A("--value", type=float, required=True),
                         A("--unit", required=True), MAP_OPT),
                        "a value into the coordinate's canonical unit (writes nothing)"),
    "calc derive": Cmd("plsi.map.calc:compute",
                       (MAP, A("--coordinate", required=True), MAP_OPT,
                        A("--inputs", help="{coordinate: value} JSON (canonical units)"),
                        A("--set", dest="set_values", action="append", help="coordinate=value override (repeatable)"),
                        A("--birth-year", type=int), A("--sex", choices=V(Sex)), A("--at", type=iso_datetime)),
                       "a derived coordinate from published or what-if inputs (writes nothing)"),
    "calc survival": Cmd("plsi.map.survival:survival", (FILE,),
                         "remaining lifespan per scenario from a life table and cited hazard ratios (writes nothing)"),
    "calc course": Cmd("plsi.map.course:course", (FILE,),
                       "a measurement's course per scenario toward a cited steady state (writes nothing)"),
    "clocks list": Cmd("plsi.map.derive:clocks", (), "native and biolearn clocks"),
    # policy
    "evidence search": Cmd("plsi.policy.evidence:search",
                           (A("--source", required=True, help=f"{', '.join(s.value for s in SearchSource)} or ext:<extension id>"), A("--query", required=True),
                            A("--limit", type=int, default=10)),
                           "search literature, trials, labels or Evipedia (network)", ("plsi evidence verify --kind <kind> --id <id>",)),
    "evidence verify": Cmd("plsi.policy.evidence:verify",
                           (A("--kind", required=True, choices=V(SourceKind)), A("--id", required=True)),
                           "verify one identifier into the ledger"),
    "screen": Cmd("plsi.policy.screen:screen",
                  (INSTANCE, FILE, A("--findings", help="{action local_id: [Finding]} the bot's own findings (raise only)")),
                  "screen every plan action (blocking)", ("plsi plan check --instance {instance} --file {file}",)),
    "plan check": Cmd("plsi.policy.gates:check", (INSTANCE, FILE), "run all gates, write nothing",
                      ("plsi plan record --instance {instance} --file {file}",)),
    "plan record": Cmd("plsi.policy.plan:record", (INSTANCE, FILE), "gate and record a plan",
                       ("plsi plan adopt --instance {instance} --plan <plan_id>",)),
    "plan adopt": Cmd("plsi.policy.plan:adopt", (INSTANCE, PLAN, A("--start-on", type=iso_date)), "adopt a recorded plan",
                      ("plsi due --instance {instance}",)),
    "plan review": Cmd("plsi.policy.plan:review", (INSTANCE, PLAN, FILE), "continue | modify | stop | complete a plan"),
    "plan list": Cmd("plsi.policy.plan:list_plans", (INSTANCE,), "plans and their states"),
    "due": Cmd("plsi.policy.score:due", (MX(A("--instance"), A("--all", dest="all_instances", action="store_true")),),
               "predictions due for measurement", ("plsi score --instance {instance}",)),
    "score": Cmd("plsi.policy.score:score", (INSTANCE,), "score due predictions; calibration",
                 ("plsi report --instance {instance}",)),
    "oracle pandaclaw": Cmd("plsi.policy.oracles:pandaclaw",
                            (MX(A("--file", help="OracleInput JSON (asks once)"),
                                A("--session", dest="session_id", help="resume a session without asking again")),),
                            "ask PandaClaw (model_derived); --session follows a timed-out or interrupted run"),
    "oracle pandaclaw-skills": Cmd("plsi.policy.oracles:pandaclaw_skills",
                                          (A("--catalog", choices=["recommended", "all"], default="recommended"), A("--topic")),
                                          "list PandaClaw skills for the ask file's skill (not a run)"),
    "oracle pandaomics tools": Cmd("plsi.policy.oracles:pandaomics_tools", (), "list PandaOmics tools"),
    "oracle pandaomics call": Cmd("plsi.policy.oracles:pandaomics_call", (A("--tool", required=True), FILE), "call a PandaOmics tool"),
    "oracle l-llm": Cmd("plsi.policy.oracles:l_llm", (FILE,), "ask the Longevity-LLM (model_derived)"),
    # output
    "report": Cmd("plsi.report:report", (INSTANCE, MX(A("--map", dest="map_id"), A("--payload", help="DashboardPayload JSON"), required=False),
                                         A("--format", dest="fmt", choices=V(ReportFormat), default="html")),
                  "render the self-contained HTML dashboard, or a static PDF for e-mail"),
    "export": Cmd("plsi.export:export",
                  (INSTANCE, A("--format", choices=V(ExportFormat), default="json"), A("--out", help="output folder")),
                  "save the instance as one JSON bundle or CSV tables"),
    "refs list": Cmd("plsi.references:list_refs", (A("--kind", choices=V(ReferenceKind)),),
                     "trusted references, grouped by kind"),
    "refs show": Cmd("plsi.references:show", (A("id", metavar="ID"),), "one reference"),
    # research graph (<PLSI_HOME>/research)
    "research index": Cmd("plsi.research_graph:index", (), "check every research item and rewrite research/index.md",
                          ("plsi research list --status ready",)),
    "research list": Cmd("plsi.research_graph:list_items",
                         (A("--project"), A("--kind", choices=V(ResearchItemKind)), A("--status", choices=V(ResearchStatus))),
                         "research items with their links, filtered"),
    "research retire": Cmd("plsi.research_graph:retire",
                           (A("--id", required=True, help="item marked status: retire"),
                            A("--reason", required=True, help="one line, logged in research/retired.md")),
                           "remove a retired item; links to it become its title"),
    # Longevity Mothership
    "mothership join": Cmd("plsi.mothership.enroll:join",
                           (INSTANCE, A("--kind", action="append", required=True, choices=V(ContributionKind)),
                            A("--consent-version", required=True, help="version marker of mothership/consent.md shown to the user"),
                            A("--code", help="one-time enrollment code from the relay's /join page (first join only)")),
                           "record the user's consent to share the chosen kinds", ("plsi mothership pack --instance {instance}",)),
    "mothership status": Cmd("plsi.mothership.enroll:status", (INSTANCE,), "enrollment, consent, address and what was sent"),
    "mothership pack": Cmd("plsi.mothership.pack:pack", (INSTANCE, A("--out", help="output file")),
                           "build the deidentified package (gate-checked, not sent)"),
    "mothership check": Cmd("plsi.mothership.send:check", (FILE, SENDER), "gate-check a file before sending"),
    "mothership send": Cmd("plsi.mothership.send:send", (FILE, SENDER),
                           "gate-check, POST to the Mothership relay with the sender's token and log"),
    "mothership receipt": Cmd("plsi.mothership.send:receipt",
                              (SENDER, A("--wait", type=int, default=0, help="seconds to keep asking while pending (max 300)")),
                              "fetch the Mother's receipts for sent messages from the relay (network)"),
    "mothership note": Cmd("plsi.mothership.research:note",
                           (INSTANCE, A("--file", required=True, help="Explorer contribution.json (research_note | registry_update)")),
                           "build a research note or registry update (gate-checked, not sent)",
                           ("plsi mothership send --instance {instance} --file <file> (registry update)",
                            "plsi mothership email --file <file> (research note)")),
    "mothership email": Cmd("plsi.mothership.research:email", (FILE,),
                            "draft the email for a research note: to, subject, body (gate-checked, not sent)"),
    "mothership whoami": Cmd("plsi.mothership.professional:whoami", (), "role, scopes and expiry of the professional token"),
    "mothership catalog": Cmd("plsi.mothership.public:catalog", (), "the Mothership's public catalog of pooled data (network)"),
    "mothership release": Cmd("plsi.mothership.public:release",
                              (A("--version", required=True, help="release version or latest"), A("--out", help="output file")),
                              "download a data release (professional token; network)",
                              ("plsi mothership analyze --release <file> --spec spec.json",)),
    "mothership findings": Cmd("plsi.mothership.public:findings", (), "the findings ledger (network)"),
    "mothership analyze": Cmd("plsi.mothership.stats:analyze",
                              (A("--release", required=True, help="downloaded release JSON"),
                               A("--spec", required=True, help="analysis spec JSON (compare_groups | age_trend)")),
                              "run an analysis on a data release (local; writes nothing)"),
    "mothership prereg": Cmd("plsi.mothership.professional:prereg", (A("--spec", required=True, help="preregistration JSON"),),
                             "preregister a hypothesis and its analysis (gate-checked, not sent)",
                             ("plsi mothership send --file <file>",)),
    "mothership finding": Cmd("plsi.mothership.professional:finding",
                              (A("--prereg", required=True, help="the preregistration message file"),
                               A("--release", required=True, help="downloaded release JSON"),
                               A("--summary", required=True, help="plain-language summary of the result")),
                              "run the preregistered analysis and build the finding (gate-checked, not sent)",
                              ("plsi mothership send --file <file>",)),
    "mothership leave": Cmd("plsi.mothership.enroll:leave", (INSTANCE, A("--delete", action="store_true", help="also ask to delete everything"),
                                                              A("--anyway", action="store_true", help="delete while a receipt is pending (user agreed)")),
                            "stop sharing; writes the withdrawal file for plsi mothership send"),
}
