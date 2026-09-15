"""Optional HTTP debugging adapter for the Reasoning service."""

from fastapi import APIRouter

from ops_agent.contracts import (
    EvidencePlan,
    EvidencePlanningRequest,
    ExperimentPlan,
    ExperimentPlanningRequest,
    HypothesisGenerationRequest,
    HypothesisSet,
    ModuleHealth,
    ReflectionRequest,
    ReflectionResult,
    RootCauseAssessment,
    RootCauseVerificationRequest,
)
from ops_agent.reasoning.api.errors import invoke
from ops_agent.reasoning.service import ReasoningService


def create_router(service: ReasoningService) -> APIRouter:
    router = APIRouter(prefix="/reasoning", tags=["reasoning"])

    @router.get("/health", response_model=ModuleHealth)
    async def health() -> ModuleHealth:
        return await service.health()

    @router.post("/hypotheses", response_model=HypothesisSet)
    async def hypotheses(request: HypothesisGenerationRequest) -> HypothesisSet:
        return await invoke(lambda: service.generate_hypotheses(request), request)

    @router.post("/evidence-plan", response_model=EvidencePlan)
    async def evidence_plan(request: EvidencePlanningRequest) -> EvidencePlan:
        return await invoke(lambda: service.plan_evidence(request), request)

    @router.post("/reflection", response_model=ReflectionResult)
    async def reflection(request: ReflectionRequest) -> ReflectionResult:
        return await invoke(lambda: service.reflect(request), request)

    @router.post("/root-cause", response_model=RootCauseAssessment)
    async def root_cause(request: RootCauseVerificationRequest) -> RootCauseAssessment:
        return await invoke(lambda: service.verify_root_cause(request), request)

    @router.post("/experiment-plan", response_model=ExperimentPlan)
    async def experiment_plan(request: ExperimentPlanningRequest) -> ExperimentPlan:
        return await invoke(lambda: service.plan_experiment(request), request)

    return router
