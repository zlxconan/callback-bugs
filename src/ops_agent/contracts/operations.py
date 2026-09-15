"""Strongly typed request and result contracts used by module ports."""

from pydantic import AwareDatetime, Field

from ops_agent.contracts.analysis import RootCauseAssessment, VerificationResult
from ops_agent.contracts.base import (
    ContractBase,
    ExperimentId,
    NonEmptyString,
)
from ops_agent.contracts.contexts import (
    KnowledgeContext,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.contracts.evidence import Evidence
from ops_agent.contracts.experiments import ExperimentPlan, ExperimentResult
from ops_agent.contracts.hypotheses import Hypothesis, HypothesisSet
from ops_agent.contracts.reports import RemediationRecommendation


class IncidentQuery(ContractBase):
    """Correlated request for the current incident aggregate."""


class StartIncidentRequest(ContractBase):
    """Input needed for the runtime to create an incident."""

    problem: ProblemContext
    product: ProductContext | None = None
    troubleshooting: TroubleshootingContext | None = None


class FinishIncidentRequest(ContractBase):
    """Validated material from which the runtime can finish an incident."""

    assessment: RootCauseAssessment
    report_title: NonEmptyString
    executive_summary: NonEmptyString
    remediation_recommendations: list[RemediationRecommendation] = Field(default_factory=list)


class KnowledgeQuery(ContractBase):
    """Version-aware request to a knowledge capability."""

    problem: ProblemContext
    product: ProductContext | None = None
    query: NonEmptyString


class HypothesisGenerationRequest(ContractBase):
    """Complete bounded input for generating hypotheses."""

    problem: ProblemContext
    product: ProductContext
    knowledge: KnowledgeContext
    troubleshooting: TroubleshootingContext | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class EvidencePlanningRequest(ContractBase):
    """Input for turning hypotheses into an evidence plan."""

    problem: ProblemContext
    hypotheses: HypothesisSet
    available_evidence: list[Evidence] = Field(default_factory=list)


class ReflectionRequest(ContractBase):
    """Evidence and experiment snapshot supplied to bounded reflection."""

    hypotheses: HypothesisSet
    evidence: list[Evidence] = Field(default_factory=list)
    experiment_results: list[ExperimentResult] = Field(default_factory=list)
    iteration: int = Field(ge=0)


class RootCauseVerificationRequest(ContractBase):
    """Evidence package used to assess a root cause."""

    hypotheses: HypothesisSet
    evidence: list[Evidence] = Field(min_length=1)
    verification_results: list[VerificationResult] = Field(default_factory=list)


class ExperimentPlanningRequest(ContractBase):
    """Input for designing one experiment around one hypothesis."""

    problem: ProblemContext
    product: ProductContext
    hypothesis: Hypothesis
    evidence: list[Evidence] = Field(default_factory=list)


class EvidenceBatch(ContractBase):
    """Typed batch result returned by InvestigationPort."""

    evidence: list[Evidence] = Field(default_factory=list)


class PreparedEnvironment(ContractBase):
    """Reference to an environment prepared for an experiment."""

    experiment_id: ExperimentId
    environment_ref: NonEmptyString
    ready: bool
    expires_at: AwareDatetime | None = None


class ExperimentExecutionRequest(ContractBase):
    """Approved plan and prepared environment passed to execution."""

    plan: ExperimentPlan
    environment: PreparedEnvironment


class ExperimentVerificationRequest(ContractBase):
    """Experiment material supplied to a reproduction verifier."""

    plan: ExperimentPlan
    result: ExperimentResult
    evidence: list[Evidence] = Field(default_factory=list)


class EnvironmentCleanupRequest(ContractBase):
    """Explicit request to release an experiment environment."""

    experiment_id: ExperimentId
    environment_ref: NonEmptyString


class CleanupResult(ContractBase):
    """Outcome of releasing an experiment environment."""

    experiment_id: ExperimentId
    environment_ref: NonEmptyString
    cleaned: bool
    observations: list[NonEmptyString] = Field(default_factory=list)


__all__ = [
    "CleanupResult",
    "EnvironmentCleanupRequest",
    "EvidenceBatch",
    "EvidencePlanningRequest",
    "ExperimentExecutionRequest",
    "ExperimentPlanningRequest",
    "ExperimentVerificationRequest",
    "FinishIncidentRequest",
    "HypothesisGenerationRequest",
    "IncidentQuery",
    "KnowledgeQuery",
    "PreparedEnvironment",
    "ReflectionRequest",
    "RootCauseVerificationRequest",
    "StartIncidentRequest",
]
