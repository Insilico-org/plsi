"""`research watchdog`: the hourly "PLSI research watchdog" routine, the research chain's only schedule. A run that
died, a kick that never started a run and a new day are its whole job, and every check logs itself in runs.jsonl,
since the bot cannot see a routine's run history. It never researches itself, except without a usable hook (the
user gave no webhook address and key, or the webhook refused the last kick), when each check does one run in place,
so research still spends its share."""

from __future__ import annotations

from typing import Any

from plsi.research import chain, inbox, ledger, runs, store
from plsi.research.tuning import KICK_STALE_MIN, OPEN_RUN_STALE_MIN
from plsi.vocab.research import KickSource, RunEvent

TELL = "post the inbox notice (with its form or card) in your own chat, then stop"


def watchdog(usage: float | None = None) -> dict[str, Any]:
    """In order: a run with no end after OPEN_RUN_STALE_MIN minutes is restarted; a kicked run that has not started
    after KICK_STALE_MIN minutes is asked for again; a new day past the start hour, with work and no run yet, is
    started; else the check is logged. The inbox notice comes when no run was kicked."""
    usage = ledger.reading(usage)
    if not chain.hooked() or runs.refused(runs.read()):
        return _in_place(usage)
    with store.locked(store.root()):
        lines = runs.read()
        event, why, kick = _rule(lines, usage)
        dead = runs.unended(lines) if event == RunEvent.RESTART else None
        runs.log(event, (dead or {}).get("run"), KickSource.WATCHDOG, project=(dead or {}).get("project"), why=why,
                 usage=usage, day=store.today())
    kicked = chain.ask(KickSource.WATCHDOG) if kick else None  # outside the lock: the started run takes it
    if kicked and not kicked["kicked"]:  # the webhook refused: this check runs it, and the inbox tells the user
        return {"check": str(event), "why": why, "kicked": kicked, **_in_place(usage)}
    notice = None if kicked else inbox.notice(form=True)
    return {"check": str(event), "why": why, "kicked": kicked, "inbox": notice,
            "then": TELL if notice else "nothing more to do here: stop"}


def _in_place(usage: float) -> dict[str, Any]:
    """No usable hook: one run in place, as `run --start` would; a stop comes with the inbox notice, if one is due."""
    started = chain.start_run(usage, KickSource.WATCHDOG)
    if "stop" not in started:
        return {"in_place": True, **started}
    notice = inbox.notice(form=True)
    return {"in_place": True, **started, "inbox": notice, **({"then": TELL} if notice else {})}


def _rule(lines: list[dict[str, Any]], usage: float) -> tuple[RunEvent, str, bool]:
    """The line the check logs, why, and whether it kicks a run."""
    dead = runs.unended(lines)
    if dead and runs.idle_minutes(dead, lines) >= OPEN_RUN_STALE_MIN:
        return RunEvent.RESTART, f"run {dead['run']} has been silent for {OPEN_RUN_STALE_MIN} minutes", True
    if dead:
        return RunEvent.CHECK, f"run {dead['run']} is open", False
    kicked = runs.last_kicked(lines)
    if kicked and not any(line.get("run") == kicked["run"] and line.get("event") != RunEvent.KICKED for line in lines):
        if runs.age_minutes(kicked) >= KICK_STALE_MIN:
            return RunEvent.CHECK, f"run {kicked['run']} was asked for and never started: asked again", True
        return RunEvent.CHECK, f"run {kicked['run']} was just asked for", False
    if runs.now().hour < chain.start_hour():
        return RunEvent.CHECK, f"the research day starts at {chain.start_hour():02d}:00 UTC", False
    if runs.of_day(lines, RunEvent.START, store.today()):
        return RunEvent.CHECK, "today's chain has started", False
    if halt := chain.hard_stop(usage):
        return RunEvent.CHECK, halt[1], False
    pick = chain.work(lines)
    if isinstance(pick, tuple):
        return pick[0], pick[2], False
    return RunEvent.CHECK, "a new research day is due: started", True
