"""The dashboard vocabulary: export and report formats, live pages, and the blocks, icons, levels and groups a
dashboard draws with."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ExportFormat", "ReportFormat", "LivePage", "BlockType", "BlockIcon", "AlertLevel", "MeasureGroup"]


class ExportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"


class ReportFormat(StrEnum):
    HTML = "html"
    PDF = "pdf"


class LivePage(StrEnum):
    """A page a command rewrites in place after it changes what the page shows (`Cmd.refresh`)."""

    CLINIC = "clinic"  # the physician's clinic dashboard
    JOURNAL = "journal"  # the lab journal


class BlockType(StrEnum):
    MARKDOWN = "markdown"
    KV = "kv"
    TABLE = "table"
    TIMESERIES = "timeseries"
    LIST = "list"
    TIMELINE = "timeline"
    PARTS = "parts"  # one whole split into at most 6 parts
    METER = "meter"  # one share against its total
    SCALE = "scale"  # marks on one number line, e.g. ages
    BARS = "bars"  # signed amounts around zero


class BlockIcon(StrEnum):
    """The line icon beside a dashboard section's title."""

    PATIENT = "patient"
    PANEL = "panel"
    VISITS = "visits"
    LAB = "lab"
    VITALS = "vitals"
    DEVICE = "device"
    MEDICINE = "medicine"
    CONDITION = "condition"
    DIET = "diet"
    PLAN = "plan"
    FOLLOW_UP = "follow_up"
    FILE = "file"
    TREND = "trend"
    ALERT = "alert"
    NOTE = "note"
    AGE = "age"


class AlertLevel(StrEnum):
    """How a dashboard marks a timeline event, a table cell or a part; neutral is a part with no status."""

    INFO = "info"
    WATCH = "watch"
    HIGH = "high"
    NEUTRAL = "neutral"


class MeasureGroup(StrEnum):
    """Where the clinic dashboard shows a measurement."""

    LAB = "lab"  # carries a specimen, a report range, a lab flag, or came from a methylation array
    DEVICE = "device"  # a wearable or importer extension
    BODY = "body"  # everything else: weight, blood pressure and other vitals
