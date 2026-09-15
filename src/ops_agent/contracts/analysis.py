"""Verification, reflection, and root-cause assessment contracts."""

from pydantic import Field

from ops_agent.contracts.base import (
    Confidence,
    ContractBase,
    EvidenceId,
    ExperimentId,
    HypothesisId,
    NonEmptyString,
    RequestId,
    StrictModel,
)
from ops_agent.contracts.enums import NextAction, RootCauseStatus, VerificationStatus
from ops_agent.contracts.hypotheses import Hypothesis


class EvidenceBackedClaim(StrictModel):
    """A statement whose provenance is explicit."""

    statement: NonEmptyString
    evidence_ids: list[EvidenceId] = Field(min_length=1)


class RootCause(StrictModel):
    """A candidate or confirmed cause linked to hypotheses and evidence."""

    description: NonEmptyString
    confidence: Confidence
    hypothesis_ids: list[HypothesisId] = Field(min_length=1)
    evidence_ids: list[EvidenceId] = Field(min_length=1)


class VerificationResult(ContractBase):
    """Verifier judgment over hypotheses and experiments."""

    status: VerificationStatus
    hypothesis_ids: list[HypothesisId] = Field(min_length=1)
    experiment_ids: list[ExperimentId] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(min_length=1)
    confirmed_claims: list[NonEmptyString] = Field(default_factory=list)
    rejected_claims: list[NonEmptyString] = Field(default_factory=list)
    unverified_claims: list[NonEmptyString] = Field(default_factory=list)
    rationale: NonEmptyString
    confidence: Confidence


class ReflectionResult(ContractBase):
    """Bounded reflection output that recommends, but does not execute, a next action."""

    summary: NonEmptyString
    retained_hypothesis_ids: list[HypothesisId] = Field(default_factory=list)
    rejected_hypothesis_ids: list[HypothesisId] = Field(default_factory=list)
    new_hypotheses: list[Hypothesis] = Field(default_factory=list)
    missing_evidence: list[RequestId] = Field(default_factory=list)
    next_action: NextAction
    should_continue: bool


class RootCauseAssessment(ContractBase):
    """Evidence-backed assessment made before rendering a final report."""

    status: RootCauseStatus
    confirmed_facts: list[EvidenceBackedClaim] = Field(default_factory=list)
    inferences: list[EvidenceBackedClaim] = Field(default_factory=list)
    root_causes: list[RootCause] = Field(default_factory=list)
    unverified_items: list[NonEmptyString] = Field(default_factory=list)
    overall_confidence: Confidence
