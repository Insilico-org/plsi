"""DashboardPayload -> a static A4 PDF (matplotlib, no browser), for documents that leave the computer by e-mail.

Same blocks as the HTML report; links print as text, nothing is interactive. Text is drawn with parse_math=False, so
"$" and "_" print as typed.
"""

from __future__ import annotations

import io
import json
import re
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING, Any

from plsi.errors import EnvironmentProblem
from plsi.vocab import BlockType

if TYPE_CHECKING:
    from plsi.report import Block, DashboardPayload

PAGE_W, PAGE_H, MARGIN = 8.27, 11.69, 0.6  # inches, A4
BODY_PT, SMALL_PT, TITLE_PT, HEAD_PT = 9.5, 8, 15, 11.5
LINE = 1.45 / 72  # line height per point of font size, in inches
CHAR_W = 0.55 / 72  # average DejaVu Sans glyph width per point of font size, in inches
MAX_SERIES = 6

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_EMPH = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*")


def _plain(text: Any) -> str:
    s = "" if text is None else str(text)
    s = _LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})", s)
    return _EMPH.sub(lambda m: m.group(1) or m.group(2), s)


def _cell_text(cell: Any) -> str:
    if isinstance(cell, dict):
        return _plain(cell.get("text", ""))
    if isinstance(cell, float):
        return f"{round(cell, 2):g}"
    return _plain(cell)


def _wrap(text: str, width_in: float, pt: float) -> list[str]:
    cols = max(8, int(width_in / (pt * CHAR_W)))
    out = []
    for para in str(text).splitlines() or [""]:
        out += textwrap.wrap(para, cols, break_long_words=True, break_on_hyphens=False) or [""]
    return out


def _date(t: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except ValueError:
        return None


class _Doc:
    def __init__(self, pdf: Any, plt: Any, title: str, stamp: str):
        self.pdf, self.plt, self.title, self.stamp = pdf, plt, title, stamp
        self.fig, self.y, self.page = None, 0.0, 0
        self.width = PAGE_W - 2 * MARGIN
        self._new_page()

    def _new_page(self) -> None:
        if self.fig is not None:
            self._finish_page()
        self.page += 1
        self.fig = self.plt.figure(figsize=(PAGE_W, PAGE_H))
        self.y = PAGE_H - MARGIN

    def _finish_page(self) -> None:
        self.fig.text(MARGIN / PAGE_W, 0.35 / PAGE_H, f"{self.title} · {self.stamp}", fontsize=7, color="#666666",
                      parse_math=False)
        self.fig.text(1 - MARGIN / PAGE_W, 0.35 / PAGE_H, str(self.page), fontsize=7, color="#666666", ha="right",
                      parse_math=False)
        self.pdf.savefig(self.fig)
        self.plt.close(self.fig)

    def close(self) -> None:
        self._finish_page()

    def need(self, height: float) -> None:
        if self.y - height < MARGIN + 0.3:
            self._new_page()

    def text(self, x: float, s: str, pt: float, bold: bool = False, color: str = "black") -> None:
        self.fig.text((MARGIN + x) / PAGE_W, self.y / PAGE_H, s, fontsize=pt, va="top", color=color,
                      fontweight="bold" if bold else "normal", parse_math=False)

    def lines(self, text: str, pt: float = BODY_PT, bold: bool = False, indent: float = 0.0, prefix: str = "",
              color: str = "black") -> None:
        wrapped = _wrap(text, self.width - indent - 0.2, pt)
        for i, line in enumerate(wrapped):
            self.need(pt * LINE)
            if prefix and i == 0:
                self.text(indent - 0.15, prefix, pt)
            self.text(indent, line, pt, bold, color)
            self.y -= pt * LINE

    def gap(self, inches: float = 0.12) -> None:
        self.y -= inches

    def rule(self) -> None:
        self.fig.add_artist(self.plt.Line2D([MARGIN / PAGE_W, 1 - MARGIN / PAGE_W], [self.y / PAGE_H] * 2,
                                            color="#bbbbbb", linewidth=0.6))

    def table(self, columns: list[str], rows: list[list[Any]]) -> None:
        head = [_plain(c) for c in columns]
        body = [[_cell_text(c) for c in r] + [""] * (len(head) - len(r)) for r in rows]
        if not head:
            return
        cols = range(len(head))
        longest = [max([len(head[i])] + [min(len(r[i]), 60) for r in body]) + 2 for i in cols]
        word = [max(len(w) for c in [head[i], *(r[i] for r in body)] for w in (c.split() or [""])) + 2 for i in cols]
        need = [min(n, 24) * SMALL_PT * CHAR_W for n in word]  # the longest word (a date, a value) never splits
        spare = max(0.0, self.width - sum(need))
        extra = [max(0, n - w) for n, w in zip(longest, word)]
        widths = [base + spare * e / (sum(extra) or 1) for base, e in zip(need, extra)]

        def row(cells: list[str], bold: bool) -> None:
            wrapped = [_wrap(c, w - 0.08, SMALL_PT) for c, w in zip(cells, widths)]
            height = max(len(w) for w in wrapped) * SMALL_PT * LINE + 0.05
            self.need(height)
            x = 0.0
            for w, cell in zip(widths, wrapped):
                self.text(x, "\n".join(cell), SMALL_PT, bold)
                x += w
            self.y -= height
            self.rule()
            self.y -= 0.03

        if any(head):
            row(head, True)
        else:
            self.rule()
            self.y -= 0.03
        for r in body:
            row(r, False)

    def chart(self, series: dict[str, Any]) -> None:
        height = 1.9
        name = _plain(series.get("name", ""))
        unit = _plain(series.get("unit", ""))
        pts = [(d, p.get("v")) for p in series.get("points", []) if (d := _date(p.get("t"))) is not None]
        preds = [(d, p) for p in series.get("predictions", []) if (d := _date(p.get("t"))) is not None]
        self.gap(0.08)
        if not pts and not preds:
            self.lines(f"{name}: no values yet", SMALL_PT)
            return
        self.need(height + 0.3)
        self.lines(f"{name} ({unit})" if unit else name, SMALL_PT, bold=True)
        ax = self.fig.add_axes([(MARGIN + 0.45) / PAGE_W, (self.y - height) / PAGE_H, (self.width - 0.5) / PAGE_W,
                                (height - 0.3) / PAGE_H])
        if pts:
            ax.plot([d for d, _ in pts], [v for _, v in pts], marker="o", markersize=3, linewidth=1.2, color="#1f5f8b")
        for d, p in preds:
            ax.errorbar([d], [p["expected"]], yerr=[[p["expected"] - p["low"]], [p["high"] - p["expected"]]],
                        fmt="s", markersize=4, color="#c0622f", capsize=3, linewidth=1)
        ax.tick_params(labelsize=7)
        ax.grid(alpha=0.25, linewidth=0.5)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        if preds:
            ax.legend(handles=[self.plt.Line2D([], [], color="#1f5f8b", marker="o", markersize=3, label="observed"),
                               self.plt.Line2D([], [], color="#c0622f", marker="s", markersize=4, linestyle="",
                                               label="predicted (interval)")], fontsize=6.5, frameon=False)
        self.fig.autofmt_xdate(rotation=0, ha="center")
        self.y -= height + 0.25  # room for the date labels under the axes


def _markdown(doc: _Doc, text: str) -> None:
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line:
            doc.gap(0.06)
        elif line.startswith("#"):
            doc.gap(0.04)
            doc.lines(_plain(line.lstrip("#").strip()), HEAD_PT - 1, bold=True)
        elif line[:2] in ("- ", "* "):
            doc.lines(_plain(line[2:]), indent=0.25, prefix="•")
        else:
            doc.lines(_plain(line))


def _block(doc: _Doc, block: Block) -> None:
    data = block.data
    if block.title:
        doc.need(HEAD_PT * LINE * 3)
        doc.lines(_plain(block.title), HEAD_PT, bold=True)
        doc.gap(0.04)
    kind = block.type
    if kind == BlockType.MARKDOWN:
        _markdown(doc, data.get("text", ""))
    elif kind == BlockType.KV:
        doc.table(["", ""], [[i.get("key", ""), i.get("value", "")] for i in data.get("items", [])])
    elif kind == BlockType.TABLE:
        doc.table(data.get("columns", []), data.get("rows", []))
    elif kind == BlockType.LIST:
        for item in data.get("items", []):
            doc.lines(_cell_text(item), indent=0.25, prefix="•")
    elif kind == BlockType.TIMELINE:
        rows = [[e.get("t", ""), e.get("label", ""), e.get("kind", ""), e.get("detail", "")]
                for e in data.get("events", [])]
        doc.table(["date", "event", "kind", "detail"], rows)
    elif kind == BlockType.TIMESERIES:
        series = data.get("series", [])
        for s in series[:MAX_SERIES]:
            doc.chart(s)
        if len(series) > MAX_SERIES:
            doc.lines(f"{len(series) - MAX_SERIES} more series not shown.", SMALL_PT, color="#666666")
    else:
        doc.lines(json.dumps(data, indent=1, ensure_ascii=False), SMALL_PT)
    doc.gap(0.18)


def render_pdf(payload: DashboardPayload) -> bytes:
    """Pure: payload -> PDF bytes."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError as e:  # matplotlib is in the bot's environment, not a plsi dependency
        raise EnvironmentProblem("PDF reports need matplotlib", code="PDF_UNAVAILABLE",
                                 hint="uv pip install matplotlib") from e
    plt.rcParams.update({"pdf.fonttype": 42, "font.family": "DejaVu Sans"})
    stamp = payload.generated_at.date().isoformat()
    buf = io.BytesIO()
    with PdfPages(buf, metadata={"Title": payload.title, "Creator": "PLSI"}) as pdf:
        doc = _Doc(pdf, plt, _plain(payload.title), stamp)
        doc.lines(_plain(payload.title), TITLE_PT, bold=True)
        doc.lines(stamp, SMALL_PT)
        doc.gap(0.2)
        for block in payload.blocks:
            _block(doc, block)
        doc.close()
    return buf.getvalue()
