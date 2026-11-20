"""The items the user chose to leave out of every Mothership package (`mothership pack --omit`): a life event by its
kind and code, a whole map's state, a state's coordinate or one coded item of it, or a subject field. Named by a
finding's path in one package, remembered by what the item is (never its index), in <instance>/mothership/omitted.json."""

from __future__ import annotations

import re
from functools import partial
from pathlib import Path
from typing import Any

from plsi import files
from plsi.errors import ValidationError
from plsi.mothership.enroll import folder
from plsi.mothership.scan import keyed, listed

EVENT = re.compile(r"life_events\[(\d+)\]")
SUBJECT = re.compile(r"subject\.([a-z_]+)")
STATE = re.compile(r"states\[(\d+)\]\.coordinates\.(.+?)(?:\.items\[(\d+)\])?")
STATE_MAP = re.compile(r"states\[(\d+)\]")  # a whole map's state: every coordinate of it stays local
KEY = re.compile(r"#key\[(\d+)\]")
Key = dict[str, Any]


def _path(instance: str) -> Path:
    return folder(instance) / "omitted.json"


def remembered(instance: str) -> list[Key]:
    path = _path(instance)
    return files.load_json(path) if path.is_file() else []


def remember(instance: str, keys: list[Key]) -> None:
    files.atomic_write_json(_path(instance), [k for n, k in enumerate(keys) if k not in keys[:n]])


def _bad(path: str) -> ValidationError:
    return ValidationError(f"no item to leave out at {path!r}", code="BAD_OMIT",
                           hint="name it as the finding does: life_events[3], states[0] (a whole map), "
                                "states[0].coordinates.<id>, states[0].coordinates.<id>.items[1] or subject.ethnicity")


def _at(items: list[Any], n: str, path: str) -> dict[str, Any]:
    if int(n) >= len(items) or not isinstance(items[int(n)], dict):
        raise _bad(path)
    return items[int(n)]


def key(doc: dict[str, Any], path: str) -> Key:
    """What the item at `path` of the package `doc` is, as remembered."""
    if m := EVENT.fullmatch(path):
        event = _at(listed(doc.get("life_events")), m[1], path)
        return {"section": "life_events", "kind": event["kind"], "code": event["code"]}
    if (m := SUBJECT.fullmatch(path)) and m[1] in keyed(doc.get("subject")):
        return {"section": "subject", "field": m[1]}
    if m := STATE.fullmatch(path):
        state = _at(listed(doc.get("states")), m[1], path)
        coordinates = keyed(state.get("coordinates"))
        coordinate = list(coordinates)[int(k[1])] if (k := KEY.fullmatch(m[2])) and int(k[1]) < len(coordinates) else m[2]
        if coordinate not in coordinates:
            raise _bad(path)
        where = {"section": "states", "map_id": state["map_id"], "coordinate": coordinate}
        return where | ({"code": _at(listed(coordinates[coordinate].get("items")), m[3], path)["code"]} if m[3] else {})
    if m := STATE_MAP.fullmatch(path):  # a whole map: remembered by its map_id, no coordinate
        return {"section": "states", "map_id": _at(listed(doc.get("states")), m[1], path)["map_id"]}
    raise _bad(path)


def _out(left: dict[str, int], label: str, gone: bool) -> bool:
    """Count one item of `label` as gone (or not) in `left`, in place; return `gone` so callers filter on it."""
    left[label] = left.get(label, 0) + gone
    return gone


def apply(doc: dict[str, Any], keys: list[Key]) -> dict[str, int]:
    """Take the items of `keys` out of `doc`; how many of each went: a life event's kind, a whole `map`, `state value`,
    `state item`, `score` or the subject field. A left-out code goes from the whole package (its life events and the
    state items that carry it), a left-out map takes all its coordinates, and a left-out state value or map takes its
    score rows with it."""
    left: dict[str, int] = {}
    codes = [k["code"] for k in keys if "code" in k]
    whole_maps = {k["map_id"] for k in keys if k.get("section") == "states" and set(k) == {"section", "map_id"}}
    scores = keyed(keyed(doc.get("scores")).get("by_coordinate"))
    out = partial(_out, left)
    if "life_events" in doc:
        doc["life_events"] = [e for e in doc["life_events"] if not out(e["kind"], e["code"] in codes)]
    kept = []
    for state in doc.get("states", []):
        if out("map", state["map_id"] in whole_maps):
            for c in state["coordinates"]:
                if out("score", c in scores):
                    del scores[c]
            continue
        for c, value in list(state["coordinates"].items()):
            if out("state value", {"section": "states", "map_id": state["map_id"], "coordinate": c} in keys):
                del state["coordinates"][c]
                if out("score", c in scores):
                    del scores[c]
            elif "items" in value:
                value["items"] = [i for i in value["items"] if not out("state item", i["code"] in codes)]
        kept.append(state)
    if "states" in doc:
        doc["states"] = kept
    for field in list(doc.get("subject", {})):
        if out(field, {"section": "subject", "field": field} in keys):
            del doc["subject"][field]
    return {label: n for label, n in left.items() if n}
