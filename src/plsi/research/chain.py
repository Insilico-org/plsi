"""`research run`: the research chain. Each run of the "PLSI research run" routine starts with `--start`, which
picks the project and reads the meter, works that one project through lab/run, and ends with `--end`, which
charges the run's rise to the moves it saved, rebuilds the project's findings.md, gives the room its line and
asks for the next run while the day's target is not spent: a POST to the routine's webhook (`kick`), whose address
and key are the user's secrets PLSI_RESEARCH_HOOK_URL and PLSI_RESEARCH_HOOK_KEY. Every step logs itself in
runs.jsonl (runs.py); the hourly check is watchdog.py."""

from __future__ import annotations

import math
from collections import Counter
from datetime import date, timedelta
from typing import Any

from plsi import files, keys, net
from plsi.errors import NetworkError, UsageError, ValidationError
from plsi.research import findings, inbox, ledger, loop, projects, runs, store
from plsi.research.tuning import (KICK_TIMEOUT_S, OPEN_RUN_STALE_MIN, RUN_CAP_MIN, QUOTA_CAP, RUN_CAP_MULTIPLE,
                                 RUN_MINUTES)
from plsi.vocab.research import KickSource, ProjectStatus, ResearchLogEvent, RunEvent, RunRest

NOTHING = "end this run here and post nothing"
END_WITH = "plsi research run --end --run {run} --usage <percent of this week's limit used, read now>"
HOOK_URL, HOOK_KEY = "PLSI_RESEARCH_HOOK_URL", "PLSI_RESEARCH_HOOK_KEY"


def run(start: bool = False, end: bool = False, usage: float | None = None, kick: str | None = None,
        rid: str | None = None) -> dict[str, Any]:
    """`research run --start [--kick <body>]` or `--end --run <id>`, each at a meter reading."""
    if kick is not None and not start:
        raise UsageError("--kick goes with --start", hint="plsi research run --start --usage <U> --kick '<body>'")
    if start == bool(rid):
        raise UsageError("--run goes with --end, and only there: the id --start gave this run",
                         hint="plsi research run --end --run <id> --usage <U>")
    usage = ledger.reading(usage)
    out = start_run(usage, *_source(kick)) if start else _end(str(rid), usage)
    if renewed := ledger.quota_renewed(usage):  # the first reading below the cap after a quota stop
        out["quota_renewed"] = {"stopped": renewed, "on_hold": [projects.card(p) for p in projects.every()
                                                                if p.get("status") == ProjectStatus.ON_HOLD],
                                "then": "lab/run Quota: offer to resume the projects on hold"}
    return out


def hooked() -> bool:
    """Whether the user gave the "PLSI research run" routine's webhook (address and key)."""
    return bool(keys.get(HOOK_URL) and keys.get(HOOK_KEY))


def kick(body: dict[str, Any]) -> dict[str, Any] | None:
    """The one call point that asks for a run: POST `body` to the webhook of the "PLSI research run" routine.
    Returns {"http": code} or {"failed": status or error code}, never the address or the key; None while no hook
    is configured, which leaves the next run to the watchdog."""
    url, key = keys.get(HOOK_URL), keys.get(HOOK_KEY)
    if not url or not key:
        return None
    keys.hide(url)  # the address is a secret too, though its name does not say so
    try:
        return {"http": net.post_json(url, body, token=key, timeout=KICK_TIMEOUT_S).status}
    except NetworkError as exc:
        return {"failed": exc.status or exc.code}


def ask(source: KickSource) -> dict[str, Any] | None:
    """Kick a run under a new id, logged as `kicked` before the POST (so the run it starts finds its id however
    slow the answer) and again with what the webhook answered; `kicked` False when it refused. None with no hook."""
    if not hooked():
        return None
    rid = runs.new_id()
    runs.log(RunEvent.KICKED, rid, source)
    sent = kick({"source": str(source), "run": rid}) or {"failed": "NO_HOOK"}
    runs.log(RunEvent.KICKED, rid, source, http=sent.get("http"), failed=sent.get("failed"))
    return {"run": rid, "kicked": "http" in sent, **sent}


def kick_if_idle() -> dict[str, Any] | None:
    """A command created work (a new or switched topic, a resumed or reopened project): ask for a run now, unless
    no hook is configured, research is Off or a run is open (its end picks the next project anyway)."""
    if not hooked() or ledger.is_off() or runs.open_run():
        return None
    return ask(KickSource.USER)


def _source(kick_body: str | None) -> tuple[KickSource, str | None]:
    """Who started this run and the run id it was given; no body is the routine's schedule."""
    text = str(kick_body or "").strip()
    if not text:
        return KickSource.SCHEDULE, None
    hint = 'the run\'s JSON body as it came, e.g. {"source": "chain", "run": "<id>"}, or nothing'
    try:
        body = files.loads_json(text)
    except ValueError:
        raise ValidationError("--kick is not JSON", code="BAD_KICK", hint=hint) from None
    if not isinstance(body, dict) or body.get("source") not in tuple(KickSource):
        raise ValidationError(f"--kick names no source of {', '.join(KickSource)}", code="BAD_KICK", hint=hint)
    return KickSource(body["source"]), (str(body["run"]) if body.get("run") else None)


def start_hour() -> int:
    """The UTC hour a research day may start (`budget --start-hour`)."""
    return int(ledger.state()["start_hour"])


def _early() -> bool:
    """A new day is due (the ledger's day is not today) but the user's start hour has not come."""
    return ledger.state().get("day") != store.today() and runs.now().hour < start_hour()


def _until(why: RunRest) -> str:
    if why in (RunRest.HEADROOM, RunRest.QUOTA, RunRest.CEILING):
        return "when the weekly meter resets"
    if why == RunRest.OFF:
        return "when the user gives research a share again"
    day = date.fromisoformat(store.today()) + timedelta(days=0 if why == RunRest.EARLY else 1)
    return f"{day.isoformat()}T{start_hour():02d}:00:00+00:00"


def _stop(event: RunEvent, rid: str, source: str | None, says: str, why: RunRest | None = None,
          **fields: Any) -> dict[str, Any]:
    """Log a run that ends at its start, or the chain's rest after a run, and say why."""
    until = _until(why) if why else None
    runs.log(event, rid, source, why=None if why is None else str(why), until=until, day=store.today(), **fields)
    return {"run": rid, "stop": str(event), "why": None if why is None else str(why), "says": says, "until": until}


QUOTA_THEN = "lab/run Quota: tell the user which projects were running and ask which resume"


def _then(why: RunRest) -> str:
    return QUOTA_THEN if why == RunRest.QUOTA else NOTHING


def hard_stop(usage: float) -> tuple[RunRest, str] | None:
    """Off, a fallen reading, the user's headroom or the week's ceiling: what ends research whatever is left."""
    if ledger.is_off():
        return RunRest.OFF, "research is Off: its share of the meter is 0"
    if fell := ledger.meter_fell(store.today()):
        return RunRest.METER, (f"the meter read {fell['saw']} after {fell['after']}: the user says whether the week "
                               f"reset (plsi research budget --meter-reset --usage {fell['saw']})")
    if ledger.over_quota(usage, store.today()):
        return RunRest.QUOTA, f"the weekly meter is at {usage}%, the {QUOTA_CAP}% cap at which all research stops"
    room = ledger.headroom(usage)
    if not room["ok"]:
        return RunRest.HEADROOM, f"{room['left']}% of the week is left and the user keeps {room['keeps_back']}%"
    budget = ledger.state()
    if ledger.week_spent(budget) >= ledger.ceiling(budget):  # a new week before its first day opens is not spent
        return RunRest.CEILING, f"research has spent its {ledger.ceiling(budget)}% of this week"
    return None


def work(lines: list[dict[str, Any]]) -> dict[str, Any] | tuple[RunEvent, RunRest | None, str]:
    """The pick (`ledger.pick_next`) for the next run, else the stop that ends the day: `idle` when nothing is
    left to work on, a `rest` when today's target is spent (a day not opened yet still has all of it)."""
    pick = ledger.pick_next(runs.last_runs(lines))
    if pick is None:
        return RunEvent.IDLE, None, "nothing is left to work on today"
    budget = ledger.state()
    if budget.get("day") == store.today() and (
            pick["part"]["project_remaining"] <= 0 or float(budget["allocated"]) - float(budget["spent"]) <= 0):
        return RunEvent.REST, RunRest.TARGET, "the day's target is spent"
    return pick


def _ended_today(lines: list[dict[str, Any]]) -> tuple[RunRest, str] | None:
    """Today's run cap or two empty runs ended the day: only a user's new work starts another run."""
    for line in reversed(runs.of_day(lines, RunEvent.REST, store.today())):
        if line.get("why") in (RunRest.CAP, RunRest.NOTHING_SAVED):
            return RunRest(line["why"]), "the chain already ended today: " + str(line["why"]).replace("_", " ")
    return None


def start_run(usage: float, source: KickSource, asked: str | None = None) -> dict[str, Any]:
    """`run --start` for a run `source` started, under the id its kick gave (`asked`), else a new one."""
    rid = asked or runs.new_id()
    with store.locked(store.root()):
        lines = runs.read()
        if source == KickSource.CHAIN:
            kicked = runs.last_kicked(lines)
            started = any(line.get("event") == RunEvent.START and line.get("run") == rid for line in lines)
            if started or (kicked or {}).get("run") != rid:
                return {**_stop(RunEvent.STRAY, rid, source, "this chain kick is not the one the last run asked for"),
                        "then": NOTHING}
        dead = runs.unended(lines)
        if dead and runs.idle_minutes(dead, lines) < OPEN_RUN_STALE_MIN:
            return {**_stop(RunEvent.BUSY, rid, source, f"run {dead['run']} is still open", busy_with=dead["run"]),
                    "then": NOTHING}
        if dead:  # a run that never ended: charged at most a typical run, the rest of the rise was not research
            _ended(dead, usage, _settle(dead, usage, most=runs.run_cost(lines)), died=True)
        early = (RunRest.EARLY, "the day starts at the user's start hour") if _early() else _ended_today(lines)
        if source != KickSource.USER and early:  # the user's new work starts a run whatever the hour
            return {**_stop(RunEvent.REST, rid, source, early[1], early[0], usage=usage), "then": NOTHING}
        if not ledger.is_off() and not ledger.open_day(usage, store.today()) and not dead:
            ledger.rebase(usage)
        if halt := hard_stop(usage):
            return {**_stop(RunEvent.REST, rid, source, halt[1], halt[0], usage=usage), "then": _then(halt[0])}
        pick = work(lines)
        if isinstance(pick, tuple):
            return {**_stop(pick[0], rid, source, pick[2], pick[1], usage=usage), "then": NOTHING}
        pid = pick["project"]["id"]
        runs.log(RunEvent.START, rid, source, project=pid, usage=usage, day=store.today())
    return {"run": rid, "source": str(source), "project": pick["project"],
            "room": projects.resolve(pid).get("room"), "time_box_minutes": RUN_MINUTES, "part": pick["part"],
            "next": loop.next_move(project=pid),
            "then": f"work this project's moves with lab/run until code says stop (time_box after about "
                    f"{RUN_MINUTES} minutes; inside this run plsi research next and save need no --usage), then "
                    f"{END_WITH.format(run=rid)}"}


def _settle(started: dict[str, Any], usage: float, most: float | None = None) -> dict[str, Any]:
    """Charge the rise since the last reading (at `most` this much: the rest is rebased as not research) and spread
    it over the moves this run saved without a reading of their own: one `run` line in each topic it touched. A run
    that saved none puts the whole rise on one topic of its project, like an unsaved reading. A fallen reading
    charges nothing."""
    rid, budget = started["run"], ledger.state()
    day, last = budget.get("day") or store.today(), budget.get("last_usage")  # the day the rise is charged to
    if most is not None and last is not None and usage - float(last) > most:
        rise = ledger.charge(round(float(last) + most, 4))["delta"]
        ledger.rebase(usage)
    else:
        rise = ledger.charge(usage)["delta"]
    directory = projects.folder(started["project"])
    saved = {d.name: [line for line in files.read_jsonl(d / store.LOG_FILE) if line.get("move") and
                      line.get("run") == rid] for d in store.topic_dirs(directory)}
    saved = {name: moved for name, moved in saved.items() if moved}
    unread = {name: [m for m in moved if (m.get("cost") or {}).get("delta") is None] for name, moved in saved.items()}
    n = sum(len(moved) for moved in unread.values())
    each = round(rise / n, 4) if rise is not None and n else None
    for name, moved in unread.items():
        if each is not None and moved:
            store.append_log(store.load(name), {"event": str(ResearchLogEvent.RUN), "run": rid, "day": day,
                                                "delta": round(each * len(moved), 4), "each": each,
                                                "moves": dict(Counter(m["move"] for m in moved))})
    newest = max(store.topic_dirs(directory), key=lambda d: str(store.topic_meta(d).get("updated") or ""),
                 default=None)
    home = (max(saved, key=lambda name: max(str(m.get("at") or "") for m in saved[name])) if saved else
            store.active_name(directory, required=False) or (newest.name if newest else None))
    if rise and not n and home:  # a charged rise lands on a topic of the project, so share() counts it
        store.append_log(store.load(home), {"event": str(ResearchLogEvent.RUN), "run": rid, "day": day,
                                              "delta": rise, "each": None, "moves": {}})
    moved = [m for lines in saved.values() for m in lines]
    return {"day": day, "rise": rise, "moves": len(moved), "topics": sorted(saved),
            "added": sum(len((m.get("change") or {}).get("created") or []) for m in moved),
            "closed": sum(len((m.get("change") or {}).get("closed") or []) for m in moved),
            "meter_fell": rise is None}


def _ended(started: dict[str, Any], usage: float, settled: dict[str, Any], **fields: Any) -> None:
    runs.log(RunEvent.END, started["run"], started.get("source"), project=started.get("project"), usage=usage,
             day=settled["day"], rise=settled["rise"], moves=settled["moves"], **fields)


def _room_line(title: str, settled: dict[str, Any]) -> str:
    """One plain line for the project's room."""
    if settled["meter_fell"]:
        return f"Research run on {title}: the meter read lower than before, so nothing was charged; waiting for you."
    if not settled["moves"]:
        return f"Research run on {title}: nothing was saved this time ({settled['rise'] or 0}% of the week)."
    return (f"Research run on {title}: {settled['moves']} step(s) on {', '.join(settled['topics'])}, "
            f"{settled['added']} new finding(s) or question(s), {settled['closed']} question(s) settled, "
            f"{settled['rise'] or 0}% of the week. The findings doc is updated.")


def _end(rid: str, usage: float) -> dict[str, Any]:
    """End the run named: one already ended (a later start counted it as dead) is a `stray` and settles nothing.
    The next run is asked for before the doc is rebuilt, so nothing after the end can leave the chain stopped."""
    with store.locked(store.root()):
        lines = runs.read()
        started = next((line for line in lines if line.get("event") == RunEvent.START and line.get("run") == rid),
                       None)
        if started is None:
            raise UsageError(f"no research run {rid} was started", code="NO_RUN",
                             hint="plsi research run --end --run <the id run --start gave> --usage <U>")
        if any(line.get("event") == RunEvent.END and line.get("run") == rid for line in lines):
            return {**_stop(RunEvent.STRAY, rid, started.get("source"),
                            "this run was already ended: a later run counted it as dead"), "then": NOTHING}
        settled = _settle(started, usage)
        _ended(started, usage, settled)
    after = _after(rid, usage)
    meta = projects.resolve(started["project"])
    doc = findings.rebuild(projects.folder(meta["id"]))
    notice = inbox.notice(form=True)
    return {"run": started["run"], "project": projects.card(meta), "room": meta.get("room"),
            "room_line": _room_line(meta["title"], settled), "charged": settled, "findings": str(doc),
            "next": after, "inbox": notice,
            "then": "post room_line in the project's room" + (" and the inbox notice (with its form or card) in "
                                                              "your own chat" if notice else "") +
                    (f"; then {after['then']}" if after.get("then") else "; then stop")}


def _after(ended: str, usage: float) -> dict[str, Any]:
    """Ask for the next run while the day's target is not spent, work remains, the day's run cap is not reached
    and the last two runs were not both empty; else the chain rests until the next day."""
    today, lines = store.today(), runs.read()
    halt = hard_stop(usage)
    ends = runs.of_day(lines, RunEvent.END, today)[-2:]
    # moves only: a meter read in whole percents shows no rise for most good runs; the run cap bounds the rest
    if not halt and len(ends) == 2 and all(not e.get("moves") for e in ends):
        halt = RunRest.NOTHING_SAVED, "two runs in a row saved nothing"
    expected = float(ledger.state()["allocated"]) / runs.run_cost(lines)  # runs the day's target pays for
    cap = max(RUN_CAP_MIN, math.ceil(round(RUN_CAP_MULTIPLE * expected, 6)))
    if not halt and len(runs.of_day(lines, RunEvent.START, today)) >= cap:
        halt = RunRest.CAP, f"today took {cap} runs, the most its target allows"
    if not halt and _early():  # the run crossed into a new day before its start hour
        halt = RunRest.EARLY, "the next day starts at the user's start hour"
    if halt:
        out = _stop(RunEvent.REST, ended, KickSource.CHAIN, halt[1], halt[0], usage=usage)
        return {**out, "then": QUOTA_THEN} if halt[0] == RunRest.QUOTA else out
    pick = work(lines)
    if isinstance(pick, tuple):
        return _stop(pick[0], ended, KickSource.CHAIN, pick[2], pick[1], usage=usage)
    asked = ask(KickSource.CHAIN)
    if asked and asked["kicked"]:
        return asked
    return {**(asked or {}), "kicked": False,
            "says": ("the webhook refused the kick" if asked else "no hook is configured") +
                    ": the watchdog's next check runs the next one in place"}
