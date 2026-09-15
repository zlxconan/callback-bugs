"""Evidence request, plan, and observation contracts."""

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from ops_agent.contracts.base import (
    Confidence,
    ContractBase,
    EvidenceId,
    HypothesisId,
    NonEmptyString,
    RawReference,
    TimeRange,
)
from ops_agent.contracts.enums import EvidenceAcquisitionStatus, EvidenceType


class EvidenceRequest(ContractBase):
    """A bounded request for evidence needed to test hypotheses."""

    hypothesis_ids: list[HypothesisId] = Field(default_factory=list)
    evidence_type: EvidenceType
    description: NonEmptyString
    query: NonEmptyString
    acquisition_method: NonEmptyString
    priority: int = Field(ge=1, le=5)
    required: bool
    time_range: TimeRange | None = None


class EvidencePlan(ContractBase):
    """An ordered collection strategy for evidence requests."""

    objective: NonEmptyString
    requests: list[EvidenceRequest] = Field(min_length=1)
    completion_criteria: list[NonEmptyString] = Field(min_length=1)


class Evidence(ContractBase):
    """A provenance-preserving observation linked to hypotheses."""

    evidence_id: EvidenceId
    evidence_type: EvidenceType
    raw_reference: RawReference
    structured_value: JsonValue | None = None
    observed_at: AwareDatetime
    supports_hypotheses: list[HypothesisId] = Field(default_factory=list)
    contradicts_hypotheses: list[HypothesisId] = Field(default_factory=list)
    confidence: Confidence
    acquisition_status: EvidenceAcquisitionStatus

    @model_validator(mode="after")
    def hypothesis_relationships_must_not_overlap(self) -> "Evidence":
        overlap = set(self.supports_hypotheses) & set(self.contradicts_hypotheses)
        if overlap:
            raise ValueError("evidence cannot both support and contradict one hypothesis")
        return self
