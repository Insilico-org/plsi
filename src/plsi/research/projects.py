"""Projects: a titled aim at the top of the research tree, <PLSI_HOME>/research/projects/<title> · <id8>/, holding
project.md, topics/, notes/ and data/.

The id is a uuid so a project can later be shared; `owner: self` and `members: []` hold its place until then. A
project is found by its id or title in project.md, never by its folder name. Any number of projects are active
at once: creating one never touches another, and only the user closes one or brings it back. No command guesses a
project when more than one is active (`pick`). The `research project` command itself is in status.py, beside the
project map it shows; `--adopt` is adopt.py.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from plsi import files, paths
from plsi.errors import NotFound, UsageError, ValidationError
from plsi.mothership.note import MAX_TITLE
from plsi.research import store
from plsi.vocab.research import ProjectStatus

FOLDER_TITLE = 60  # characters of the title in a project's folder name, as the Mother names its project folders


def scan() -> list[tuple[Path, dict[str, Any]]]:
    """(folder, frontmatter) of every project with an id."""
    found = [(d, store.read_md(d / store.PROJECT_FILE)[0]) for d in store.project_dirs()]
    return [(d, m) for d, m in found if m.get("id")]


def every() -> list[dict[str, Any]]:
    """Every project's frontmatter, by the day it was created, then by title."""
    return sorted((m for _, m in scan()),
                  key=lambda m: (str(m.get("created") or ""), str(m.get("title") or "").casefold()))


def actives() -> list[dict[str, Any]]:
    return [m for m in every() if m.get("status") == ProjectStatus.ACTIVE]


def folder(pid: str) -> Path:
    found = next((d for d, m in scan() if m["id"] == pid), None)
    if found is None:
        raise NotFound(f"no research project {pid!r}", code="PROJECT_NOT_FOUND", hint="plsi research project")
    return found


def resolve(ref: str) -> dict[str, Any]:
    """A project named by its id or its title (case-insensitive)."""
    key = str(ref or "").strip().casefold()
    hits = [m for m in every() if key in (str(m["id"]).casefold(), str(m.get("title") or "").casefold())]
    if len(hits) != 1:
        raise NotFound(f"no research project {ref!r}" if not hits else f"{len(hits)} projects are titled {ref!r}",
                       code="PROJECT_NOT_FOUND", hint="plsi research project  # name it by its id")
    return hits[0]


def pick(ref: str | None) -> dict[str, Any]:
    """The project a command works in: the one named, else the only active one. Never a guess between several."""
    if ref:
        return resolve(ref)
    found = actives()
    if len(found) == 1:
        return found[0]
    if not found:
        raise NotFound("no active research project", code="PROJECT_REQUIRED",
                       hint="plsi research project --new '<title>' --aim '<one line>'")
    raise UsageError(f"{len(found)} projects are active: name one with --project "
                     f"({'; '.join(repr(m['title']) for m in found)})", code="PROJECT_REQUIRED",
                     hint="plsi research project")


def card(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    """What a topic, a note or a wire message names a project by."""
    return {"id": meta["id"], "title": meta["title"]} if meta else None


def active_cards() -> list[dict[str, Any] | None]:
    return [card(m) for m in actives()]


def folder_name(title: str, pid: str) -> str:
    return f"{store.sanitise(title[:FOLDER_TITLE])} · {pid[:8]}"


def _write(meta: dict[str, Any], directory: Path) -> None:
    body = f"# {meta['title']}\n\n{meta.get('aim') or ''}"
    with store.locked(directory):
        files.atomic_write_text(directory / store.PROJECT_FILE, store.render(meta, body, True))


def create(title: str, aim: str | None = None) -> dict[str, Any]:
    """A new active project with its folders; every other project stays as it is."""
    title = " ".join(str(title).split())
    if not title or len(title) > MAX_TITLE:
        raise ValidationError(f"a project title is 1-{MAX_TITLE} characters", hint="a short plain title")
    if any(str(m.get("title") or "").casefold() == title.casefold() for m in every()):
        raise ValidationError(f"project {title!r} already exists", hint=f"plsi research project --reopen '{title}'")
    meta = {"id": str(uuid.uuid4()), "title": title, "aim": " ".join(str(aim or "").split()),
            "status": str(ProjectStatus.ACTIVE), "created": store.today(), "owner": "self", "members": []}
    directory = paths.safe_join(store.root(), store.PROJECTS_FOLDER, folder_name(title, meta["id"]))
    for sub in (store.TOPICS_FOLDER, store.NOTES_FOLDER, store.DATA_FOLDER):
        (directory / sub).mkdir(parents=True, exist_ok=True)
    _write(meta, directory)
    return meta


def set_status(ref: str, status: ProjectStatus) -> dict[str, Any]:
    """Close a project or reopen it, with everything in it kept."""
    meta = resolve(ref)
    if meta.get("status") == status:
        raise UsageError(f"project {meta['title']!r} is already {status.value}", hint="plsi research project")
    meta = {**meta, "status": str(status)}
    _write(meta, folder(meta["id"]))
    return meta


def topic_asked(directory: Path, today: str | None) -> str | None:
    """The day this project first asked the user for its next topic, recorded as `today` when nothing was asked yet;
    None clears it (a topic became active). Kept in the project's own project.md, under its lock."""
    with store.locked(directory):
        meta = store.read_md(directory / store.PROJECT_FILE)[0]
        before = None if meta.get("topic_asked") is None else str(meta["topic_asked"])  # YAML reads a date back
        asked = today and (before or today)
        if asked != before:
            _write({**meta, "topic_asked": asked}, directory)
    return asked


def topics_of(pid: str) -> list[str]:
    return store.list_topics(folder(pid))


def active_topic(ref: str | None) -> str:
    """The active topic of the project named, or of the only active project."""
    return str(store.active_name(folder(pick(ref)["id"])))
