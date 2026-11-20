"""The lab journal vocabulary: experiment kinds, entry states, plasmid features and the calculators."""

from __future__ import annotations

from enum import StrEnum


class ExperimentKind(StrEnum):
    """What a journal entry records; the kind decides which result sections its page draws."""

    PCR = "pcr"
    GEL = "gel"  # agarose or polyacrylamide electrophoresis
    QPCR = "qpcr"  # RT-qPCR, relative quantification
    WESTERN = "western"
    XCELLIGENCE = "xcelligence"  # real-time impedance (cell index)
    FLUORIMETRY = "fluorimetry"  # plate-reader fluorescence or absorbance
    MICROSCOPY = "microscopy"
    CULTURE = "culture"  # cell culture: thawing, passaging, freezing, seeding
    SORTING = "sorting"  # flow cytometry and FACS: FCS files, gates, dot plots
    ANIMAL = "animal"  # an in vivo study: groups, dosing, weights, endpoints
    CLONING = "cloning"  # plasmids: digest, ligation, transformation, minipreps
    TRANSFECTION = "transfection"
    ELISA = "elisa"
    OTHER = "other"


class EntryStatus(StrEnum):
    """An entry is a draft until it is signed; a signed entry never changes again (amend it with a new entry)."""

    PLANNED = "planned"
    RUNNING = "running"
    DONE = "done"
    SIGNED = "signed"


class AnimalStatus(StrEnum):
    ALIVE = "alive"
    ENDPOINT = "endpoint"  # reached the planned end of the study
    HUMANE_ENDPOINT = "humane_endpoint"
    FOUND_DEAD = "found_dead"
    REMOVED = "removed"  # taken off the study for another reason (note says why)


class WellRole(StrEnum):
    """What a well is for: only samples enter the results; a control that amplifies or a blank that rises is flagged."""

    SAMPLE = "sample"
    NTC = "ntc"  # no-template control
    NO_RT = "no_rt"  # RNA without reverse transcriptase: genomic DNA carry-over
    BLANK = "blank"  # medium or buffer only: no cells, no sample


class VesselType(StrEnum):
    T25 = "t25"
    T75 = "t75"
    T175 = "t175"
    DISH_6CM = "dish_6cm"
    DISH_10CM = "dish_10cm"
    DISH_15CM = "dish_15cm"
    PLATE_6 = "plate_6"
    PLATE_12 = "plate_12"
    PLATE_24 = "plate_24"
    PLATE_48 = "plate_48"
    PLATE_96 = "plate_96"
    CRYOVIAL = "cryovial"
    TUBE_15 = "tube_15"
    TUBE_50 = "tube_50"
    OTHER = "other"


class VesselStatus(StrEnum):
    IN_USE = "in_use"  # in the incubator
    FROZEN = "frozen"  # in a freezer box or liquid nitrogen
    THAWED = "thawed"
    DISCARDED = "discarded"
    SHIPPED = "shipped"


class Ear(StrEnum):
    """The animal's own left or right."""

    LEFT = "left"
    RIGHT = "right"


class PunchSite(StrEnum):
    """Where an ear mark sits, the head seen from above, nose forward: a notch on the rim, or a hole."""

    FRONT = "front"  # rim toward the nose
    BACK = "back"  # rim toward the tail
    OUTER = "outer"  # the ear's outer edge
    HOLE = "hole"  # a punched hole in the middle


class FeatureKind(StrEnum):
    """Plasmid map features, as SnapGene and GenBank name them (others map to MISC)."""

    CDS = "cds"
    PROMOTER = "promoter"
    TERMINATOR = "terminator"
    ORIGIN = "origin"  # rep_origin
    MARKER = "marker"  # antibiotic or selection marker
    TAG = "tag"  # epitope or fluorescent tag
    PRIMER = "primer"  # primer_bind
    SITE = "site"  # a restriction or recombination site
    MISC = "misc"


class Strand(StrEnum):
    FORWARD = "+"
    REVERSE = "-"
    NONE = "."


class PlateFormat(StrEnum):
    """Wells per plate; rows x columns follow the SBS layout."""

    W6 = "6"
    W12 = "12"
    W24 = "24"
    W48 = "48"
    W96 = "96"
    W384 = "384"


class CalcKind(StrEnum):
    """`plsi journal calc --kind <kind>`: each is arithmetic only and writes nothing."""

    MOLARITY = "molarity"  # mass, volume, molecular weight, concentration: any three give the fourth
    DILUTION = "dilution"  # C1 V1 = C2 V2
    SERIAL = "serial"  # a serial dilution series
    SEEDING = "seeding"  # cells per well from a count
    HEMOCYTOMETER = "hemocytometer"  # cells/mL and viability from square counts
    MASTERMIX = "mastermix"  # a PCR or qPCR master mix for n reactions with overage
    LIGATION = "ligation"  # insert mass for a molar insert:vector ratio
    DNA_MOLES = "dna_moles"  # ng of DNA to pmol (ds or ss)
    PROTEIN_LOAD = "protein_load"  # sample and buffer volumes for equal µg per lane
    DOSE = "dose"  # mg/kg to the volume each animal receives
    AGAROSE = "agarose"  # grams of agarose for a gel percentage
    DOUBLING = "doubling"  # population doubling time from two counts
