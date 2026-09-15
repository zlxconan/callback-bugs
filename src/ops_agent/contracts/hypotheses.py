"""Reasoning hypothesis contracts."""

from pydantic import Field, model_validator

from ops_agent.contracts.base import (
    Confidence,
    ContractBase,
    EvidenceId,
    HypothesisId,
    NonEmptyString,
    RequestId,
)
from ops_agent.contracts.enums import HypothesisStatus


class Hypothesis(ContractBase):
    """A falsifiable explanation with explicit epistemic categories."""

    hypothesis_id: HypothesisId
    fact: list[NonEmptyString] = Field(default_factory=list)
    inference: NonEmptyString
    assumption: list[NonEmptyString] = Field(default_factory=list)
    confidence: Confidence
    supporting_evidence: list[EvidenceId] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceId] = Field(default_factory=list)
    missing_evidence: list[RequestId] = Field(default_factory=list)
    status: HypothesisStatus


class HypothesisSet(ContractBase):
    """A ranked, internally consistent collection of hypotheses."""

    hypotheses: list[Hypothesis] = Field(min_length=1)
    prioritized_hypothesis_ids: list[HypothesisId] = Field(min_length=1)
    selection_rationale: NonEmptyString

    @model_validator(mode="after")
    def priorities_must_reference_members(self) -> "HypothesisSet":
        known_ids = {item.hypothesis_id for item in self.hypotheses}
        priorities = self.prioritized_hypothesis_ids
        if len(priorities) != len(set(priorities)):
            raise ValueError("prioritized_hypothesis_ids must be unique")
        if not set(priorities).issubset(known_ids):
            raise ValueError("prioritized_hypothesis_ids must reference contained hypotheses")
        return self
