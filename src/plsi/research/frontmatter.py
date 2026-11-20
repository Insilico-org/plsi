"""Markdown with YAML frontmatter: reading a file into (frontmatter, body), writing the pair back, and the small
text operations on a node's body — the bot's prose without the generated link footer, shortening to a limit, and
checking a source's quote against the passage it was supplied with."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from plsi.errors import ValidationError
from plsi.vocab import fold

LINK_MARK = "<!-- links -->"  # everything after it is generated; invisible in Obsidian
# An HTML tag opens with a letter or a slash, so a bare `<` in "p < 0.001" is not taken for one.
_TAGS = re.compile(r"</?[A-Za-z][^<>]*/?>")


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Markdown with YAML frontmatter, as (frontmatter, body). A byte-order mark and CRLF line ends are read
    like plain LF text."""
    text = text.removeprefix("\ufeff").replace("\r\n", "\n")
    if not text.startswith("---\n") or "\n---" not in text[4:]:
        return {}, text
    head, _, body = text[4:].partition("\n---")
    try:
        meta = yaml.safe_load(head)
    except yaml.YAMLError as exc:
        raise ValidationError(f"unreadable frontmatter: {exc}") from None
    return (meta if isinstance(meta, dict) else {}), body.lstrip("\n")


def read_md(path: Path) -> tuple[dict[str, Any], str]:
    """`parse` of one file; unreadable frontmatter is refused naming the file."""
    try:
        return parse(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise ValidationError(f"{path.name}: {exc.message}", code=exc.code, hint=exc.hint) from None


def render(meta: dict[str, Any], body: str, keep_empty: bool = False) -> str:
    """Frontmatter and body as one Markdown file; empty fields are left out unless `keep_empty`."""
    clean = meta if keep_empty else {k: v for k, v in meta.items() if v not in (None, [], {}, "")}
    head = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False, width=100).rstrip("\n")
    return f"---\n{head}\n---\n\n{body.strip()}\n"


def prose(body: str) -> str:
    """The bot's own words, without the generated link footer."""
    return str(body or "").split(LINK_MARK)[0].rstrip()


def clip(text: str, limit: int) -> str:
    """Shorten to `limit` characters at a sentence end where one is near, else at a word boundary."""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind(". "), head.rfind("? "), head.rfind("! "), head.rfind("\n"))
    return (head[:cut + 1] if cut > limit // 2 else head.rsplit(" ", 1)[0]).rstrip() + " […]"


def _flat(text: Any) -> str:
    """Letters and digits only, with markup removed, so the quote check ignores case, spacing and typography."""
    return fold(_TAGS.sub("", str(text or "")))


def verify_quotes(meta: dict[str, Any]) -> dict[str, Any]:
    """Set each source's `quote_verified`: true when the quote occurs in the `text` passed with it.

    This checks the quote against the passage the bot supplied, not against the publication itself. The text
    is dropped rather than stored; a source passed without text keeps its earlier value."""
    for source in meta.get("sources") or []:
        if not isinstance(source, dict):
            continue
        was = bool(source.get("quote_verified"))
        quote, text = _flat(source.get("quote")), _flat(source.pop("text", ""))
        source["quote_verified"] = bool(quote and quote in text) if text else was
    return meta
