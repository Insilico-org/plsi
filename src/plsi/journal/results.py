"""The results an entry records, one typed part per kind of experiment (`EntryInput.results`)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from pydantic import Field, model_validator

from plsi.journal.tuning import COFACTOR
from plsi.models import Model
from plsi.vocab import Sex
from plsi.vocab.journal import AnimalStatus, Ear, PunchSite, VesselStatus, VesselType, WellRole

Text = Annotated[str, Field(max_length=4000)]
Short = Annotated[str, Field(min_length=1, max_length=200)]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]


class Cycle(Model):
    step: Short  # initial denaturation, denaturation, annealing, extension, final extension, hold
    temp_c: float
    seconds: float = Field(ge=0)
    cycles: int = Field(default=1, ge=1, le=99)


class Lane(Model):
    lane: int = Field(ge=1, le=60)
    sample: str | None = None
    ladder: bool = False
    expected_bp: float | None = Field(default=None, gt=0)
    observed_bp: list[float] = []  # the bands seen, as read off the ladder: "about 650" is 650 (sizes on a gel are estimates)
    faint_bp: list[float] = []  # bands seen but faint
    note: str | None = None


class Ct(Model):
    sample: Short
    target: Short
    ct: float | None = Field(default=None, ge=0, le=60)  # None = undetermined
    group: str | None = None
    role: WellRole = WellRole.SAMPLE  # unset: taken from the name ("NTC", "no RT"), and said so


class Band(Model):
    lane: int = Field(ge=1, le=60)
    sample: Short
    target: Short
    intensity: float = Field(ge=0)
    loading: float | None = Field(default=None, gt=0)  # the loading control's intensity in the same lane
    group: str | None = None
    kda: float | None = Field(default=None, gt=0)


class CiPoint(Model):
    t_h: float = Field(ge=0)
    ci: float


class CiSeries(Model):
    group: Short
    well: str | None = None
    points: list[CiPoint] = Field(min_length=1)
    role: WellRole = WellRole.SAMPLE  # "blank" for medium-only wells; unset: taken from the group's name


class Reading(Model):
    sample: Short
    value: float
    group: str | None = None
    role: WellRole = WellRole.SAMPLE  # "blank" for blank wells; unset: taken from the sample's name
    standard_conc: float | None = None  # a standard of known concentration


class Image(Model):
    file: Short  # name of the file kept with the entry (never a path outside it)
    channel: str | None = None  # DAPI, GFP, brightfield ...
    objective: str | None = None
    sample: str | None = None
    animal: str | None = None  # an animal's id: its photo (ID, phenotype, a lesion)
    note: str | None = None


class Passage(Model):
    date: dt.date
    passage: int | None = Field(default=None, ge=0)
    action: Short  # thawed, split 1:5, seeded, medium change, frozen, mycoplasma test
    confluence_pct: float | None = Field(default=None, ge=0, le=100)
    viability_pct: float | None = Field(default=None, ge=0, le=100)
    cells: float | None = Field(default=None, ge=0)
    note: str | None = None


Point = tuple[float, float]


class Vessel(Model):
    """A flask, dish, plate or cryovial of cells. A frozen vial has a box and a position in it (A1 ... J10)."""

    id: Short  # as on the label
    type: VesselType
    cell_line: str | None = None
    passage: int | None = Field(default=None, ge=0)
    date: dt.date | None = None  # seeded, split into, or frozen
    cells: float | None = Field(default=None, ge=0)
    confluence_pct: float | None = Field(default=None, ge=0, le=100)
    medium: str | None = None
    location: str | None = None  # incubator 2, shelf B; the freezer or tank holding the box
    box: str | None = None
    position: Annotated[str, Field(pattern=r"^[A-J](?:[1-9]|10)$")] | None = None
    status: VesselStatus | None = None  # as recorded; never assumed
    note: str | None = None

    @model_validator(mode="after")
    def _box(self) -> Vessel:
        if self.position and not self.box:
            raise ValueError(f"vessel {self.id!r}: a position needs its box")
        return self


class Gate(Model):
    """A flow gate: with FCS files code counts it from its shape (vertices in channel units, edges straight on the
    plot's scale); without them the counts are the exported ones."""

    name: Short
    parent: str | None = None  # None = all events
    sample: str | None = None  # None = every sample
    x: str | None = None  # channel name or marker, e.g. "FSC-A", "CD45"
    y: str | None = None
    polygon: list[Point] | None = Field(default=None, min_length=3, max_length=200)
    rect: tuple[float, float, float, float] | None = None  # x min, x max, y min, y max
    interval: tuple[float, float] | None = None  # on x only: a histogram gate

    @model_validator(mode="after")
    def _shape(self) -> Gate:
        shapes = [s for s in (self.polygon, self.rect, self.interval) if s is not None]
        if len(shapes) > 1:
            raise ValueError(f"gate {self.name!r}: one shape only (polygon, rect or interval)")
        if (self.polygon or self.rect) and not (self.x and self.y):
            raise ValueError(f"gate {self.name!r}: a polygon or rect needs both x and y channels")
        if self.interval and not self.x:
            raise ValueError(f"gate {self.name!r}: an interval needs its x channel")
        if self.rect and not (self.rect[0] < self.rect[1] and self.rect[2] < self.rect[3]):
            raise ValueError(f"gate {self.name!r}: rect is x min, x max, y min, y max")
        if self.interval and not self.interval[0] < self.interval[1]:
            raise ValueError(f"gate {self.name!r}: interval is low, high")
        if self.parent == self.name:
            raise ValueError(f"gate {self.name!r} cannot be its own parent")
        return self


class ExportedCount(Model):
    """A count from the analysis software (FlowJo, the sorter): checked against the FCS file, or used without one."""

    sample: Short
    gate: Short
    events: int = Field(ge=0)


class FcsFile(Model):
    sample: Short
    file: Short  # an .fcs file kept with the entry (journal attach)


class Group(Model):
    name: Short
    n: int = Field(ge=0)
    treatment: str | None = None
    dose: str | None = None  # as written: "10 mg/kg i.p. daily"


class Allele(Model):
    """A band of the genotyping PCR: what it means and its size. `control` is an internal control band that every
    good lane shows."""

    name: Short
    bp: float = Field(gt=0)
    control: bool = False


class Punch(Model):
    ear: Ear
    at: PunchSite


class Animal(Model):
    id: Short  # the lab's id or ear tag code, never a person's name
    group: str | None = None
    sex: Sex | None = None
    born: dt.date | None = None
    cage: str | None = None
    ear_tag: str | None = None
    ear_punch: list[Punch] | None = Field(default=None, max_length=8)  # the marks as made; [] = none
    strain: str | None = None  # as written: "C57BL/6J", "Cdkn2a-flox x Cre"
    bands: list[float] | None = None  # genotyping PCR bands seen, bp; [] = nothing amplified
    genotype: str | None = None  # the lab's call, when it was written down; code checks it against the bands
    status: AnimalStatus | None = None  # as recorded; never assumed
    note: str | None = None


class Weight(Model):
    animal: Short
    group: Short
    date: dt.date
    grams: float = Field(gt=0)


class Results(Model):
    """Raw results; fill the parts the experiment produced."""

    cycling: list[Cycle] = []
    lanes: list[Lane] = []
    gel: str | None = None  # "1% agarose, 120 V, 40 min" as written
    cts: list[Ct] = []
    reference_targets: list[str] = []  # housekeeping genes for ΔΔCt
    control_group: str | None = None  # the calibrator for ΔΔCt, western and fluorimetry
    bands: list[Band] = []
    ci: list[CiSeries] = []
    treated_at_h: float | None = None  # xCELLigence: the cell index is normalised here
    readings: list[Reading] = []
    reading: str | None = None  # "ex 485 / em 535, gain 80" as written
    images: list[Image] = []
    passages: list[Passage] = []
    vessels: list[Vessel] = []  # flasks, plates and vials of this culture
    gates: list[Gate] = []
    fcs: list[FcsFile] = []  # flow: each sample's file; gates are then counted by code
    exported_counts: list[ExportedCount] = []  # flow: counts as the analysis software exported them
    cofactor: float = Field(default=COFACTOR, gt=0)  # arcsinh cofactor of the fluorescence axes
    compensate: bool = True  # apply the file's own spillover matrix
    groups: list[Group] = []
    weights: list[Weight] = []
    animals: list[Animal] = []
    alleles: list[Allele] = []  # the genotyping PCR's bands
    genotyping: str | None = None  # the assay as written: "ear punch, 3-primer PCR, 2% gel"
    expected: dict[str, float] = {}  # genotype -> expected share from the cross, e.g. {"WT/WT": 1, "WT/flox": 2, "flox/flox": 1}
    plasmid: str | None = None  # a saved plasmid's name (cloning, transfection)
