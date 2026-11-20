"""A lab journal entry as the bot writes it (`plsi journal save --file entry.json`): what was planned and done, the
raw results (`plsi.journal.results`), what was seen, and how the entry was made."""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Any

from pydantic import Field, model_validator

from plsi.journal.results import Results, Short, Slug, Text
from plsi.models import Model
from plsi.vocab.journal import EntryStatus, ExperimentKind, PlateFormat

# what an observation must not sound like: the tool's bookkeeping instead of the bench
INTERNAL = re.compile(r"sha-?256|\bschema (field|says|has no)\b|journal show|\bplsi\b|\w+_\w+ (field|values?)|results\.\w+|\b(observed|faint)_bp\b|"
                      r"as (given|described|written|stated|supplied) by the (researcher|user)|\b(rows?|fields?) (read|skipped|imported)\b",
                      re.IGNORECASE)
WELL = r"^[A-P](?:[1-9]|1[0-9]|2[0-4])$"


class Step(Model):
    text: Text
    done: bool = False
    minutes: float | None = Field(default=None, ge=0)
    temp_c: float | None = None
    note: Text | None = None


class Reagent(Model):
    name: Short
    supplier: str | None = None
    catalog: str | None = None
    lot: str | None = None
    stock: str | None = None  # as written: "10 mM", "1:1000"
    amount: str | None = None  # used in this experiment: "2 µL per reaction"


class Sample(Model):
    id: Short
    group: str | None = None  # control, treated, KO, ... (the comparison the results use)
    type: str | None = None  # cell line, tissue, plasmid, RNA, lysate, animal
    detail: str | None = None  # passage, genotype, treatment, concentration as written


class Well(Model):
    well: Annotated[str, Field(pattern=WELL)]
    sample: str | None = None
    group: str | None = None
    label: str | None = None  # what the plate map prints in the well


class Plate(Model):
    format: PlateFormat = PlateFormat.W96
    name: str | None = None
    wells: list[Well] = []


class EntryInput(Model):
    """One experiment. `id` is given on the first save and kept: saving it again writes the next version."""

    id: Slug
    title: Short
    kind: ExperimentKind
    date: dt.date
    project: str | None = None
    status: EntryStatus = EntryStatus.DONE
    aim: Text | None = None
    protocol: list[Step] = []
    reagents: list[Reagent] = []
    samples: list[Sample] = []
    plate: Plate | None = None
    results: Results = Results()
    observations: Text | None = None  # what was seen at the bench, in plain words
    conclusion: Text | None = None
    next_steps: Text | None = None
    record: Text | None = None  # how the entry was made: files read, rows imported or skipped, what was not given
    tags: list[Annotated[str, Field(max_length=40)]] = Field(default=[], max_length=12)
    files: list[Short] = []  # names of files kept in the entry's folder
    amends: Slug | None = None  # the signed entry this one corrects
    related: list[Slug] = Field(default=[], max_length=20)  # entries this one builds on (its samples, cells, plasmid work)

    @model_validator(mode="after")
    def _signed_by_command(self) -> EntryInput:
        if self.status == EntryStatus.SIGNED:
            raise ValueError("an entry is signed only with plsi journal sign")
        if missing := [f.file for f in self.results.fcs if f.file not in self.files]:
            raise ValueError(f"list the FCS files in files too: {', '.join(missing)}")
        return self

    def dump(self) -> dict[str, Any]:
        """Stored without the result parts an experiment did not produce (empty lists, defaults)."""
        return {**super().dump(), "results": self.results.model_dump(mode="json", exclude_none=True, exclude_defaults=True)}

    def bookkeeping(self) -> list[str]:
        """Text fields that read as the tool's bookkeeping rather than the bench (refused at save, never on read)."""
        return [f"{name} reads as bookkeeping ({hit.group(0)!r})" for name in ("observations", "conclusion", "next_steps")
                if (text := getattr(self, name)) and (hit := INTERNAL.search(text))]
