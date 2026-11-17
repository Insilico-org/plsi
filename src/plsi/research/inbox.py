"""`research inbox`: what research has to tell the user since the last notice, batched across projects, at most one
notice a day, each thing told once (research/inbox.json). Unattended runs cannot ask, so this is where their
decisions reach the user: in the orchestrator's own chat, with a question form whose answers map to commands.
A Grok form has 2-8 pages, one question per page, up to 6 options and no default; one page goes as a card."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from plsi import files
from plsi.research import cursor, frontier, ledger, projects, runs, store
from plsi.research.tuning import FORM_OPTIONS, FORM_PAGES, HELD_DAYS, STALLED_DAYS
from plsi.vocab.research import InboxKind, ProjectStatus, ResearchStop

INBOX_FILE = "inbox.json"  # in research/, beside day.json: {told: {key: day}, last_notice: day}
PAGED = (InboxKind.READY, InboxKind.ALMOST, InboxKind.STALLED, InboxKind.ON_HOLD)  # one form page per project


def inbox(form: bool = False, every: bool = False) -> dict[str, Any]:
    """`research inbox [--form]`: the notice due, marked as told; `--all`: the form over every open project,
    whatever was told."""
    if every:
        return {"items": items(), **every_form()}
    return notice(form) or {"says": [], "then": "nothing new: say nothing"}


def notice(form: bool = False) -> dict[str, Any] | None:
    """The notice due, marked as told: what was not told yet, once a day; None when nothing is."""
    path, today = store.root() / INBOX_FILE, store.today()
    with store.locked(store.root()):
        state = files.load_json(path) if path.is_file() else {}
        told = dict(state.get("told") or {})
        if state.get("last_notice") == today:
            return None
        new = [i for i in items() if any(k not in told for k in i["keys"])]
        if not new:
            return None
        told.update({k: today for i in new for k in i["keys"]})
        files.atomic_write_json(path, {"told": told, "last_notice": today})
    return {"says": [f"{i['project']['title']}: {i['says']}" if i["project"] else i["says"] for i in new],
            "items": new, **(spec(new) if form else {}),
            "then": "tell the user in your own chat, in plain words" + (", with the form or card" if form else "")}


def _item(kind: InboxKind, project: dict[str, Any] | None, says: str, *keys: str) -> dict[str, Any]:
    return {"kind": str(kind), "project": project, "says": says, "keys": list(keys)}


def _days(since: str, today: str) -> int:
    return (date.fromisoformat(today) - date.fromisoformat(since[:10])).days


def items() -> list[dict[str, Any]]:
    """Everything worth telling now: ready, almost ready, needs you, stalled, on hold two weeks or more, starving."""
    today, out = store.today(), []
    for meta in projects.every():
        directory, card, held = projects.folder(meta["id"]), projects.card(meta), str(meta.get("held_on") or "")
        if meta.get("status") == ProjectStatus.ON_HOLD and held and _days(held, today) >= HELD_DAYS:
            out.append(_item(InboxKind.ON_HOLD, card, f"on hold since {held}", f"held:{card['id']}:{held}"))
        elif meta.get("status") == ProjectStatus.ACTIVE:
            out += _project(directory, meta, today)
    if fell := ledger.meter_fell(today):
        out.append(_item(InboxKind.NEEDS_YOU, None, f"needs you: the meter read {fell['saw']} after {fell['after']}; "
                                                    "did the week reset?", f"meter:{today}:{fell['saw']}"))
    if refused := runs.refused(runs.read()):
        out.append(_item(InboxKind.NEEDS_YOU, None,
                         f"needs you: the research webhook refused the last run ({refused['failed']}), so research "
                         "runs only once an hour: copy \"POST to\" and the key of the \"PLSI research run\" routine "
                         "into the secret card again (PLSI_RESEARCH_HOOK_URL, PLSI_RESEARCH_HOOK_KEY)",
                         f"hook:{refused['failed']}:{refused['run']}"))
    if hungry := ledger.starving(runs.run_cost(runs.read())):
        out.append(_item(InboxKind.STARVING, None,
                         f"starving: {hungry['working']} projects share {hungry['part']}% a day each, less than one "
                         f"run's {hungry['a_run_costs']}%; putting {hungry['hold']} on hold lets the others progress",
                         f"starving:{hungry['working']}:{hungry['hold']}", ) | {"hold": hungry["hold"]})
    return out


def _project(directory: Path, meta: dict[str, Any], today: str) -> list[dict[str, Any]]:
    card, pid = projects.card(meta), meta["id"]
    active = store.active_name(directory, required=False)
    if active is None:
        metas = {d.name: store.topic_meta(d) for d in store.topic_dirs(directory)}
        last = max(metas, key=lambda n: (str(metas[n].get("updated") or ""), n), default=None)
        ended = str((metas.get(last) or {}).get("ended_reason") or "")
        if ended.startswith(ResearchStop.ANSWERED):
            return [_item(InboxKind.READY, card, f"ready: {last} is answered", f"ready:{pid}:{last}")]
        if ended.startswith(ResearchStop.EXHAUSTED):
            return [_item(InboxKind.STALLED, card, f"stalled: {last} ran out of directions, nothing follows it",
                          f"stalled:{pid}:{last}")]
        asked = meta.get("topic_asked")
        return [_item(InboxKind.NEEDS_YOU, card, "needs you: pick its next topic",
                      f"no_topic:{pid}:{asked}")] if asked else []
    graph = store.load(active)
    if cursor.answers_in_chief(graph):
        return [_item(InboxKind.READY, card, f"ready: {active} has an answer at its depth bar", f"ready:{pid}:{active}")]
    out, tops = [], {q["name"] for q in graph.tops()}
    near = [e["question"] for e in frontier.rank(graph) if e["question"] in tops and e["steps_to_a_verdict"] <= 1]
    if near:
        out.append(_item(InboxKind.ALMOST, card, f"almost ready: {len(near)} direction(s) of {active} one move from "
                                                 "a verdict", *(f"almost:{pid}:{active}:{q}" for q in near)))
    log = store.read_log(graph)
    moved = [str(line["day"]) for line in log if line.get("move") and line.get("day")]
    last = max(moved) if moved else (str(log[0].get("at") or "")[:10] if log else "")
    if last and _days(last, today) >= STALLED_DAYS:
        out.append(_item(InboxKind.STALLED, card, f"stalled: no move on {active} since {last}",
                         f"stalled:{pid}:{active}:{last}"))
    return out


def _option(label: str, do: str | None) -> dict[str, Any]:
    return {"label": label, "do": do or "no change"}


def page(project: dict[str, Any], says: str, held: bool = False) -> dict[str, Any]:
    """One project's page: what to do with it. Skipping the page changes nothing."""
    ref = project["id"]
    close = _option("Close", f"plsi research project --close {ref}")
    options = ([_option("Resume", f"plsi research project --resume {ref}"), _option("Keep on hold", None), close]
               if held else
               [_option("Keep going", None),
                _option("Finish and write it up", f"a write-up session in the project's room, then "
                                                  f"plsi research project --close {ref}"),
                _option("Put on hold", f"plsi research project --hold {ref}"), close])
    return {"question": f"{project['title']}: {says}. What next?", "multi": False, "project": project,
            "options": options}


def _starving_page(hold: int) -> dict[str, Any]:
    """Which working projects go on hold: the ones furthest from an answer. Forms have no defaults, so the
    question names how many."""
    far = []
    for directory, meta in ledger.working():
        ranked = frontier.rank(store.load(store.active_name(directory)))
        far.append((min((e["steps_to_a_verdict"] for e in ranked), default=len(frontier.STEPS)), meta))
    far.sort(key=lambda f: (-f[0], str(f[1].get("title"))))
    options = [_option(m["title"], f"plsi research project --hold {m['id']}") for _, m in far[:FORM_OPTIONS]]
    pick = min(hold, len(options))
    more = f" ({hold - pick} more after these)" if hold > pick else ""
    return {"question": f"Which projects should go on hold? Picking {pick} lets the others make real progress{more}.",
            "multi": True, "options": options}


def _as_form(pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Two pages or more are a form; one alone is a card, and a multi-select card ends with "None of these"."""
    if not pages:
        return {}
    if len(pages) > 1:
        return {"form": pages[:FORM_PAGES]}
    card = pages[0]
    return {"card": {**card, "options": [*card["options"], _option("None of these", None)]} if card["multi"] else card}


def spec(found: list[dict[str, Any]]) -> dict[str, Any]:
    """The form for these items: a page per project raised (up to 7), or the starving page first and then up
    to 6 project pages; a single page is a one-question card."""
    raised: dict[str, dict[str, Any]] = {}
    for i in found:
        if i["project"] and i["kind"] in PAGED:
            raised.setdefault(i["project"]["id"], {"project": i["project"], "says": [],
                                                   "held": i["kind"] == InboxKind.ON_HOLD})["says"].append(i["says"])
    pages = [page(r["project"], "; ".join(r["says"]), r["held"]) for r in raised.values()]
    hungry = next((i for i in found if i["kind"] == InboxKind.STARVING), None)
    if hungry:
        return _as_form([_starving_page(hungry["hold"]), *pages[:FORM_PAGES - 2]])
    return _as_form(pages[:FORM_PAGES - 1])


def every_form() -> dict[str, Any]:
    """`--all`: an opening page "Which projects do you want to change?" (more pages past 6 projects), then, as a
    second form, one page per project picked, 8 pages in all at most."""
    open_ = [m for m in projects.every() if m.get("status") in (ProjectStatus.ACTIVE, ProjectStatus.ON_HOLD)]
    pages = {m["id"]: page(projects.card(m), str(m["status"]).replace("_", " "), m["status"] == ProjectStatus.ON_HOLD)
             for m in open_}
    if len(open_) < 2:
        return _as_form(list(pages.values()))
    chunks = [open_[i:i + FORM_OPTIONS] for i in range(0, len(open_), FORM_OPTIONS)][:FORM_PAGES - 1]
    opening = [{"question": "Which projects do you want to change?" + (f" ({n} of {len(chunks)})" if len(chunks) > 1
                                                                        else ""),
                "multi": True, "options": [{"label": m["title"], "page": m["id"]} for m in chunk]}
               for n, chunk in enumerate(chunks, 1)]
    if len(open_) < FORM_OPTIONS:  # room on the one opening page; past that, the user ticks projects
        opening[0]["options"].append({"label": "All of the above", "pages": [m["id"] for m in open_]})
    left = FORM_PAGES - len(opening)
    return {**_as_form(opening), "pages_by_project": pages,
            "then": f"send the opening page(s); then the pages of the projects picked (\"All of the above\": every "
                    f"one) as a second form, at most {left} (one alone goes as a card)"}
