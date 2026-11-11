"""The target-discovery vocabulary (`plsi targets`): bands, stages, modalities, hallmarks and ratings."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from plsi.vocab import fold


class TargetBand(StrEnum):
    """Which of three lists a candidate falls in. **Computed** from the evidence types the association rests on,
    never written by a bot: a band says what has already been tried on a target, not how good it is."""

    CLINICAL = "clinical"  # a drug against this target has reached a clinical trial
    GROUNDED = "grounded"  # human genetics, somatic mutation or an animal model bears on it; no clinical drug
    NOVEL = "novel"  # the association rests on expression, pathways or text alone


class ClinicalStage(StrEnum):
    """How far the most advanced drug against a target has gone, parsed from the source's own words because a
    source writes `PHASE_2_3` where another writes `PHASE2/PHASE3`. Member order is significant: furthest first."""

    APPROVED = "approved"
    PHASE_4 = "phase-4"  # post-marketing; approval is per indication and a phase-4 study is not one
    PHASE_3 = "phase-3"
    PHASE_2 = "phase-2"
    PHASE_1 = "phase-1"
    PRECLINICAL = "preclinical"
    NONE = "none"

    @property
    def rank(self) -> int:
        members = list(ClinicalStage)
        return len(members) - 1 - members.index(self)

    @classmethod
    def top(cls, values: Iterable[ClinicalStage]) -> ClinicalStage:
        """The furthest of values (none when there are none)."""
        return max(values, key=lambda s: s.rank, default=cls.NONE)

    @classmethod
    def parse(cls, label: Any) -> ClinicalStage | None:
        """A source's stage word as a stage, or None when the word is not one STAGE_WORDS knows (Open Targets
        also writes `UNKNOWN` and `WITHDRAWAL`, which are not stages). Callers report None as unrecorded."""
        return STAGE_WORDS.get(fold(label))

    @classmethod
    def parse_all(cls, labels: Iterable[Any]) -> list[ClinicalStage]:
        """The labels that are stage words, parsed; the rest are dropped (callers count them as unrecorded)."""
        return [s for s in map(cls.parse, labels) if s]


# Folded source words -> stage. An unknown word maps to nothing rather than to a guessed stage, and `phase_4`
# is not approval: approval is per indication and only an approval word means it.
STAGE_WORDS = {
    "approval": ClinicalStage.APPROVED, "approved": ClinicalStage.APPROVED,
    "phase4": ClinicalStage.PHASE_4,
    "phase3": ClinicalStage.PHASE_3, "phase23": ClinicalStage.PHASE_3, "phase2phase3": ClinicalStage.PHASE_3,
    "phase2": ClinicalStage.PHASE_2, "phase12": ClinicalStage.PHASE_2, "phase1phase2": ClinicalStage.PHASE_2,
    "phase1": ClinicalStage.PHASE_1, "earlyphase1": ClinicalStage.PHASE_1,
    "preclinical": ClinicalStage.PRECLINICAL,
}


class TargetModality(StrEnum):
    """What could be made against a target; Open Targets' two-letter modality codes map onto it."""

    SMALL_MOLECULE = "small-molecule"
    ANTIBODY = "antibody"
    PROTAC = "protac"
    OTHER = "other-modality"


MODALITY_CODES = {"SM": TargetModality.SMALL_MOLECULE, "AB": TargetModality.ANTIBODY,
                  "PR": TargetModality.PROTAC, "OC": TargetModality.OTHER}

# Open Targets association datatypes. An id outside this list warns (`UNKNOWN_DATATYPE`) and never decides a
# band, so an upstream rename shows up instead of emptying a band.
TARGET_DATATYPES = ("genetic_association", "genetic_literature", "somatic_mutation", "clinical",
                    "affected_pathway", "rna_expression", "literature", "animal_model")
# The datatypes that bear on causation. `genetic_literature` is text-mined, not a curated association, so it
# is not among them.
CAUSAL_DATATYPES = frozenset({"genetic_association", "somatic_mutation", "animal_model"})
# The direction-of-effect pairs (directionOnTrait, directionOnTarget), in words. A pair outside these four is
# counted as unrecognised.
DIRECTION_MEANING: dict[tuple[str, str], str] = {
    ("protect", "LoF"): "loss of function is assessed as protective",
    ("risk", "GoF"): "gain of function is assessed as increasing risk",
    ("protect", "GoF"): "gain of function is assessed as protective",
    ("risk", "LoF"): "loss of function is assessed as increasing risk",
}
# ChEMBL drug warning types read as safety precedent.
WITHDRAWN = "Withdrawn"
BLACK_BOX = "Black Box Warning"
# Open Targets' working threshold for assigning a locus to a gene; the maximum is reported too.
L2G_CONFIDENT = 0.5


class ModalityPrecedent(StrEnum):
    """What the true tractability buckets of one modality record. A modality with no true bucket is absent."""

    CLINICAL = "clinical"  # a drug of this modality reached people
    PRECLINICAL = "preclinical"  # chemical or structural matter exists; nothing of this modality was dosed


class AgingHallmark(StrEnum):
    """The twelve hallmarks of aging (Lopez-Otin et al., Cell 2023, PMID 36599349), closed so one hallmark has
    one spelling. Not Open Targets' `hallmarks` field, which holds the COSMIC cancer hallmarks."""

    GENOMIC_INSTABILITY = "genomic instability"
    TELOMERE_ATTRITION = "telomere attrition"
    EPIGENETIC_ALTERATIONS = "epigenetic alterations"
    LOSS_OF_PROTEOSTASIS = "loss of proteostasis"
    DISABLED_MACROAUTOPHAGY = "disabled macroautophagy"
    DEREGULATED_NUTRIENT_SENSING = "deregulated nutrient-sensing"
    MITOCHONDRIAL_DYSFUNCTION = "mitochondrial dysfunction"
    CELLULAR_SENESCENCE = "cellular senescence"
    STEM_CELL_EXHAUSTION = "stem cell exhaustion"
    ALTERED_INTERCELLULAR_COMMUNICATION = "altered intercellular communication"
    CHRONIC_INFLAMMATION = "chronic inflammation"
    DYSBIOSIS = "dysbiosis"


class StructureState(StrEnum):
    """A deposited PDB entry: with a bound non-polymer ligand (holo) or without one (apo)."""

    HOLO = "holo"
    APO = "apo"


class TargetRating(StrEnum):
    """The only words a target assessment may rate with."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    UNKNOWN = "unknown"  # nothing was recorded either way; NOT the same as low


class ExternalSource(StrEnum):
    """Commercial platforms a user may hold a licence to. Closed so a public database name cannot be written
    into a platform-read block. Both are reached only through `plsi oracle <service>`."""

    PANDAOMICS = "pandaomics"
    PANDACLAW = "pandaclaw"


class DevelopmentLevel(StrEnum):
    """The NIH Illuminating the Druggable Genome target development levels, as Pharos/TCRD assigns them."""

    TCLIN = "Tclin"
    TCHEM = "Tchem"
    TBIO = "Tbio"
    TDARK = "Tdark"


class TargetVerdict(StrEnum):
    """What the bot recommends doing about a target. Never computed - this one is judgment."""

    PURSUE = "pursue"
    MONITOR = "monitor"
    DEPRIORITIZE = "deprioritize"
