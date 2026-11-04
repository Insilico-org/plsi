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
