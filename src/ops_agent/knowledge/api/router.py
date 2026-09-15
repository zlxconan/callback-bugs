"""Optional HTTP debugging adapter for the Knowledge service."""

from fastapi import APIRouter

from ops_agent.contracts import (
    KnowledgeContext,
    KnowledgeQuery,
    ModuleHealth,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.knowledge.api.errors import invoke
from ops_agent.knowledge.service import KnowledgeService


def create_router(service: KnowledgeService) -> APIRouter:
    router = APIRouter(prefix="/knowledge", tags=["knowledge"])

    @router.get("/health", response_model=ModuleHealth)
    async def health() -> ModuleHealth:
        return await service.health()

    @router.post("/resolve-product", response_model=ProductContext)
    async def resolve_product(problem: ProblemContext) -> ProductContext:
        return await invoke(lambda: service.resolve_product(problem), problem)

    @router.post("/product-knowledge", response_model=KnowledgeContext)
    async def product_knowledge(query: KnowledgeQuery) -> KnowledgeContext:
        return await invoke(lambda: service.query_product_knowledge(query), query)

    @router.post("/troubleshooting", response_model=TroubleshootingContext)
    async def troubleshooting(query: KnowledgeQuery) -> TroubleshootingContext:
        return await invoke(lambda: service.query_troubleshooting(query), query)

    return router
