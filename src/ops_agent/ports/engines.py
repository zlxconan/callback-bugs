"""Ports implemented by the four independent engines."""

from typing import Protocol, runtime_checkable

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    Evidence,
    EvidenceBatch,
    EvidencePlan,
    EvidencePlanningRequest,
    EvidenceRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentPlanningRequest,
    ExperimentResult,
    ExperimentVerificationRequest,
    HypothesisGenerationRequest,
    HypothesisSet,
    KnowledgeContext,
    KnowledgeQuery,
    PreparedEnvironment,
    ProblemContext,
    ProductContext,
    ReflectionRequest,
    ReflectionResult,
    RootCauseAssessment,
    RootCauseVerificationRequest,
    TroubleshootingContext,
    VerificationResult,
)


@runtime_checkable
class KnowledgePort(Protocol):
    """Product and troubleshooting knowledge boundary."""

    async def resolve_product(self, problem: ProblemContext) -> ProductContext: ...

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext: ...

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext: ...


@runtime_checkable
class ReasoningPort(Protocol):
    """Planning and assessment boundary; it never executes tools directly."""

    async def generate_hypotheses(self, request: HypothesisGenerationRequest) -> HypothesisSet: ...

    async def plan_evidence(self, request: EvidencePlanningRequest) -> EvidencePlan: ...

    async def reflect(self, request: ReflectionRequest) -> ReflectionResult: ...

    async def verify_root_cause(
        self, request: RootCauseVerificationRequest
    ) -> RootCauseAssessment: ...

    async def plan_experiment(self, request: ExperimentPlanningRequest) -> ExperimentPlan: ...


@runtime_checkable
class InvestigationPort(Protocol):
    """Evidence acquisition boundary addressed only by the runtime."""

    async def collect(self, request: EvidenceRequest) -> Evidence: ...

    async def collect_batch(self, plan: EvidencePlan) -> EvidenceBatch: ...


@runtime_checkable
class ReproductionPort(Protocol):
    """Safe experiment lifecycle boundary addressed only by the runtime."""

    async def prepare(self, plan: ExperimentPlan) -> PreparedEnvironment: ...

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult: ...

    async def verify(self, request: ExperimentVerificationRequest) -> VerificationResult: ...

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult: ...
