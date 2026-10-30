"""`plsi` CLI: one COMMANDS table (plsi.commands), one JSON envelope on stdout, fixed exit codes.

Each command names ONE library function ("module:function"); it is called with the parsed arguments whose names
match its parameters. Exit codes: 0 ok, 1 refused (gate/validation/not found), 2 usage, 3 environment.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import string
import sys
import traceback
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pydantic

from plsi import __version__, errors, keys
from plsi.commands import COMMANDS, Cmd
from plsi.models import Model, validation_error


# ---------------------------------------------------------------- parser

class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Any:  # type: ignore[override]
        raise errors.UsageError(message, hint=f"{self.prog} --help")


def build_parser() -> argparse.ArgumentParser:
    root = _Parser(prog="plsi", description="PLSI toolbelt: JSON in, one JSON envelope out.")
    root.add_argument("--version", action="version", version=f"plsi {__version__}")
    groups: dict[tuple[str, ...], Any] = {(): root.add_subparsers(dest="_c0", metavar="COMMAND", required=True, parser_class=_Parser)}
    for name, cmd in COMMANDS.items():
        words = tuple(name.split())
        for depth in range(1, len(words)):
            if words[:depth] not in groups:
                group = groups[words[: depth - 1]].add_parser(words[depth - 1], help=f"{' '.join(words[:depth])} ...")
                groups[words[:depth]] = group.add_subparsers(dest=f"_c{depth}", metavar="SUBCOMMAND", required=True, parser_class=_Parser)
        parser = groups[words[:-1]].add_parser(words[-1], help=cmd.help, description=cmd.help)
        parser.set_defaults(_command=name)
        for spec in cmd.args:
            if spec[0] == "__mx__":
                group = parser.add_mutually_exclusive_group(required=spec[2])
                for flags, kw in spec[1]:
                    group.add_argument(*flags, **kw)
            else:
                parser.add_argument(*spec[0], **spec[1])
    return root


# ---------------------------------------------------------------- dispatch and envelope

def _resolve(target: str) -> Callable[..., Any]:
    module, func = target.split(":")
    return getattr(importlib.import_module(module), func)


def _call(cmd: Cmd, ns: argparse.Namespace) -> Any:
    func = _resolve(cmd.target)
    params = inspect.signature(func).parameters
    return func(**{k: getattr(ns, k) for k in params if hasattr(ns, k)})


def _next(cmd: Cmd, ns: argparse.Namespace) -> list[str]:
    out = []
    values = vars(ns)
    for template in cmd.next:
        fields = [f for _, f, _, _ in string.Formatter().parse(template) if f]
        if all(values.get(f) is not None for f in fields):
            out.append(template.format(**values))
    return out


def _guess_command(argv: Sequence[str]) -> str:
    words: list[str] = []
    for token in argv:
        if token.startswith("-"):
            break
        words.append(token)
        if " ".join(words) in COMMANDS:
            break
    return " ".join(words[:3])


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, Model):
        return obj.dump()
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    raise TypeError(f"not JSON serializable: {type(obj).__name__}")


def _failure(command: str, exc: errors.PlsiError) -> dict[str, Any]:
    error: dict[str, Any] = {"code": exc.code, "message": keys.redact(exc.message)}
    if exc.violations:
        error["violations"] = [{k: keys.redact(v) for k, v in item.items()} for item in exc.violations]
    if exc.hint:
        error["hint"] = keys.redact(exc.hint)
    if remote := getattr(exc, "remote", None):
        error["remote"] = remote
    return {"ok": False, "command": command, "error": error}


def _as_plsi_error(exc: BaseException) -> errors.PlsiError:
    if isinstance(exc, errors.PlsiError):
        return exc
    if isinstance(exc, pydantic.ValidationError):
        return validation_error(exc, "input")
    return errors.PlsiError(f"{type(exc).__name__}: {exc}", code="INTERNAL_ERROR", hint="rerun with PLSI_DEBUG=1 for a traceback")


def _dumps(envelope: dict[str, Any]) -> str:
    return json.dumps(envelope, ensure_ascii=False, allow_nan=False, default=_jsonable)


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass
    argv = list(sys.argv[1:] if argv is None else argv)
    command = _guess_command(argv)
    errors.drain_warnings()
    try:
        ns = build_parser().parse_args(argv)
        command = ns._command
        cmd = COMMANDS[command]
        data = _call(cmd, ns)
        envelope = {"ok": True, "command": command, "data": data, "warnings": errors.drain_warnings(), "next": _next(cmd, ns)}
        out, code = _dumps(envelope), 0  # serialised before writing: unserializable data fails here, not mid-write
    except SystemExit as exc:  # --help / --version
        return int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001 - every failure becomes an envelope
        err = _as_plsi_error(exc)
        if os.environ.get("PLSI_DEBUG") == "1":
            sys.stderr.write(keys.redact(traceback.format_exc()))
        out, code = _dumps(_failure(command, err)), err.exit_code
    sys.stdout.write(out + "\n")
    sys.stdout.flush()
    return code


# ---------------------------------------------------------------- commands owned by the CLI

def instance_status(instance: str) -> dict[str, Any]:
    """Subject, event counts, stored states (hash-checked) and plans."""
    from plsi.life.store import EventStore, event_counts
    from plsi.map import mapper
    from plsi.policy.plan import list_plans

    store = EventStore(instance)
    states = []
    for latest in sorted((store.dir / "states").glob("*/latest.json")):
        try:
            doc = mapper.latest_state(instance, latest.parent.name)
            states.append({"map_id": doc.map_id, "as_of": doc.as_of, "generated_at": doc.generated_at,
                           "state_hash": doc.state_hash, "hash_ok": doc.verify_hash()})
        except errors.PlsiError:
            states.append({"map_id": latest.parent.name, "error": "unreadable latest.json"})
    return {
        "instance": instance,
        "path": str(store.dir),
        "subject": store.subject.dump(),
        "events": event_counts(instance),
        "states": states,
        "user_maps": sorted(p.stem for p in (store.dir / "maps" / "user").glob("*.yaml")),
        "plans": list_plans(instance),
    }


if __name__ == "__main__":
    raise SystemExit(main())
