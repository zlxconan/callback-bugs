"""Optional HTTP debugging adapter for the Investigation service."""

from fastapi import APIRouter

from ops_agent.contracts import Evidence, EvidenceBatch, EvidencePlan, EvidenceRequest, ModuleHealth
from ops_agent.investigation.api.errors import invoke
from ops_agent.investigation.service import InvestigationService


def create_router(service: InvestigationService) -> APIRouter:
    router = APIRouter(prefix="/investigation", tags=["investigation"])

    @router.get("/health", response_model=ModuleHealth)
    async def health() -> ModuleHealth:
        return await service.health()

    @router.post("/collect", response_model=Evidence)
    async def collect(request: EvidenceRequest) -> Evidence:
        return await invoke(lambda: service.collect(request), request)

    @router.post("/collect-batch", response_model=EvidenceBatch)
    async def collect_batch(plan: EvidencePlan) -> EvidenceBatch:
        return await invoke(lambda: service.collect_batch(plan), plan)

    return router
