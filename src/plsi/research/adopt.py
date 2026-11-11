"""`research project --adopt`: research filed before projects held everything (topics and notes straight in
research/) moved into project folders. A topic or note that names a project goes there, the rest into Earlier
research, which is made once when something needs it. Run again, it moves nothing."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import ValidationError, warn
from plsi.research import notes, projects, store

EARLIER = "Earlier research"


def _target(pid: Any, earlier: list[dict[str, Any]]) -> dict[str, Any]:
    """The project an old topic or note goes to: the one it names, else Earlier research (made once)."""
    named = next((m for m in projects.every() if pid and m["id"] == pid), None)
    if named:
        return named
    if not earlier:
        earlier.append(next((m for m in projects.every() if m["title"] == EARLIER), None)
                       or projects.create(EARLIER, "research done before projects held every topic and note"))
    return earlier[0]


def _rename_folders() -> list[str]:
    """Project folders named by their bare id get their `<title> · <id8>` name and their sub-folders."""
    renamed = []
    for directory, meta in projects.scan():
        want = directory.with_name(projects.folder_name(meta["title"], meta["id"]))
        if directory != want:
            directory.rename(want)
            renamed.append(meta["title"])
        for sub in (store.TOPICS_FOLDER, store.NOTES_FOLDER, store.DATA_FOLDER):
            (want / sub).mkdir(exist_ok=True)
    return renamed


def _adopt_topics(earlier: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    moved, skipped = [], []
    base = store.root()
    for old in sorted(p.parent for p in base.glob(f"*/{store.TOPIC_FILE}")) if base.is_dir() else []:
        meta = store.topic_meta(old)
        if old.name.casefold() in {n.casefold() for n in store.list_topics()}:
            skipped.append(old.name)
            continue
        target = _target(meta.get("project"), earlier)
        directory = projects.folder(target["id"])
        with store.locked(directory):
            shutil.move(str(old), str(directory / store.TOPICS_FOLDER / old.name))
            graph = store.load(old.name)
            graph.topic["project"] = target["id"]
            store.write_topic(graph)
        moved.append(old.name)
    return moved, skipped


def _adopt_note(old: Path, earlier: list[dict[str, Any]]) -> bool:
    """Move one old note into its project's notes/, naming the project in its frontmatter; False when its name is
    taken there. An unreadable note moves as it is, for `research check` to show."""
    text = old.read_text(encoding="utf-8")
    try:
        meta, body = store.parse(text)
    except ValidationError:
        meta, body = {}, ""
    target = _target(meta.get("project"), earlier)
    directory = projects.folder(target["id"])
    if (directory / store.NOTES_FOLDER / old.name).exists():
        return False
    with store.locked(directory):
        files.atomic_write_text(directory / store.NOTES_FOLDER / old.name,
                                store.render({**meta, "project": target["id"]}, body) if meta else text)
        old.unlink()
    return True


def _adopt_retired(old_folder: Path, earlier: list[dict[str, Any]]) -> None:
    """The old retirement log's lines, appended once to Earlier research's."""
    retired = old_folder / store.RETIRED
    if not retired.is_file():
        return
    directory = projects.folder(_target(None, earlier)["id"])
    with store.locked(directory):
        notes.append_retired(directory / store.NOTES_FOLDER / store.RETIRED,
                             {ln: ln for ln in retired.read_text(encoding="utf-8").splitlines() if ln.startswith("- ")})
        retired.unlink()


def _adopt_notes(earlier: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    moved, skipped = [], []
    old_folder = store.root() / store.NOTES_FOLDER
    for old in sorted(old_folder.glob("*.md")) if old_folder.is_dir() else []:
        if old.name != store.RETIRED:
            (moved if _adopt_note(old, earlier) else skipped).append(old.stem)
    _adopt_retired(old_folder, earlier)
    if old_folder.is_dir() and not any(old_folder.iterdir()):
        old_folder.rmdir()
    return moved, skipped


def adopt() -> dict[str, Any]:
    """Move the old layout's topics and notes into project folders and report what moved and what was left."""
    earlier: list[dict[str, Any]] = []
    renamed = _rename_folders()
    topics, topics_skipped = _adopt_topics(earlier)
    moved_notes, notes_skipped = _adopt_notes(earlier)
    if topics_skipped or notes_skipped:
        warn("ADOPT_SKIPPED", "left in place, the name is already taken: "
                              f"{', '.join(topics_skipped + notes_skipped)}")
    return {"renamed_projects": renamed, "moved_topics": topics, "moved_notes": moved_notes,
            "skipped": topics_skipped + notes_skipped,
            "earlier_research": projects.card(earlier[0]) if earlier else None, "projects": projects.every()}
