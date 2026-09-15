"""Optional HTTP debugging adapter for the Reproduction service."""

from fastapi import APIRouter

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentResult,
    ExperimentVerificationRequest,
    ModuleHealth,
    PreparedEnvironment,
    VerificationResult,
)
from ops_agent.reproduction.api.errors import invoke
from ops_agent.reproduction.service import ReproductionService


def create_router(service: ReproductionService) -> APIRouter:
    router = APIRouter(prefix="/reproduction", tags=["reproduction"])

    @router.get("/health", response_model=ModuleHealth)
    async def health() -> ModuleHealth:
        return await service.health()

    @router.post("/prepare", response_model=PreparedEnvironment)
    async def prepare(plan: ExperimentPlan) -> PreparedEnvironment:
        return await invoke(lambda: service.prepare(plan), plan)

    @router.post("/execute", response_model=ExperimentResult)
    async def execute(request: ExperimentExecutionRequest) -> ExperimentResult:
        return await invoke(lambda: service.execute(request), request)

    @router.post("/verify", response_model=VerificationResult)
    async def verify(request: ExperimentVerificationRequest) -> VerificationResult:
        return await invoke(lambda: service.verify(request), request)

    @router.post("/cleanup", response_model=CleanupResult)
    async def cleanup(request: EnvironmentCleanupRequest) -> CleanupResult:
        return await invoke(lambda: service.cleanup(request), request)

    return router
