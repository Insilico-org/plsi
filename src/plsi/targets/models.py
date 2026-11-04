"""What a bot writes about a target: the assessment, the only part of a dossier that holds an opinion.
`extra="forbid"` refuses invented fields; ratings are closed words, and `falsifier` and `next_experiment` are
required so an assessment states how it could be wrong.
"""

from __future__ import annotations

from pydantic import Field

from plsi.models import Model
from plsi.vocab.targets import ExternalSource, TargetModality, TargetRating, TargetVerdict


class TargetRisk(Model):
    """One risk with the evidence for it. `evidence` carries the source id; `mitigation` may be `none known`."""

    dimension: str = Field(min_length=1, max_length=120)
    risk: TargetRating
    evidence: str = Field(min_length=1, max_length=1_200)
    mitigation: str = Field(default="", max_length=1_200)


class TargetStrategy(Model):
    """A way in, ranked by the bot. `description` carries the source id that makes it more than an idea."""

    name: str = Field(min_length=1, max_length=120)
    modality: TargetModality
    description: str = Field(min_length=1, max_length=1_200)


class HarvestedAsset(Model):
    """A drug the structured sources missed, found by hand. The trial id is required and must verify."""

    drug: str = Field(min_length=1, max_length=120)
    mechanism: str = Field(min_length=1, max_length=600)
    nct: str = Field(pattern=r"^NCT\d{8}$")
    sponsor: str = Field(default="", max_length=200)
    indication: str = Field(default="", max_length=200)


class PlatformRead(Model):
    """What a commercial platform said, when the bot asked it. Not a citation and never support for a claim:
    it records the question, the platform and the answer so the opinion reads as model_derived. `asked` keeps
    the question because a platform ranks a gene per disease."""

    source: ExternalSource
    tool: str = Field(min_length=1, max_length=80)  # the MCP tool called, e.g. pandaomics_get_targets
    asked: str = Field(min_length=1, max_length=300)  # the question, incl. the disease when there is one
    says: str = Field(min_length=1, max_length=1_200)  # what came back, in the platform's own terms
    retrieved: str = Field(default="", max_length=40)  # when, if the bot recorded it


class Assessment(Model):
    """`plsi targets assess --file`. Merged into the dossier under `assessment` once every refusal passes."""

    verdict: TargetVerdict
    # The three ratings do not all point the same way:
    druggability: TargetRating  # HIGH is good: it can be drugged
    safety: TargetRating  # HIGH is good: a clean safety outlook. The RISK rows carry the danger
    competition: TargetRating  # HIGH is bad: the field is crowded, which argues against entering
    rationale: str = Field(min_length=1, max_length=4_000)
    falsifier: str = Field(min_length=1, max_length=1_000)  # what we would see if this target were the wrong one
    next_experiment: str = Field(min_length=1, max_length=1_000)  # the cheapest thing that would settle it
    limitations: list[str] = Field(min_length=1)  # what this assessment could not cover; never empty
    risks: list[TargetRisk] = Field(min_length=1)
    indication: str = Field(default="", max_length=200)  # a phase is per indication; say which one this is
    strategies: list[TargetStrategy] = []
    harvested_assets: list[HarvestedAsset] = []
    # Optional: every question in `targets/evaluate` is answerable without a platform.
    platform_reads: list[PlatformRead] = []
