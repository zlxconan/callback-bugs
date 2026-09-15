import httpx
import pytest
from fastapi import FastAPI

from ops_agent.contracts import ErrorResponse, IncidentState, ModuleHealth, ProductContext
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.knowledge.api import create_router
from ops_agent.knowledge.domain import KnowledgeConfig
from ops_agent.knowledge.service import KnowledgeService


@pytest.mark.asyncio
async def test_resolve_product_http_contract_round_trip(
    fake_incident_state: IncidentState,
) -> None:
    app = FastAPI()
    app.include_router(create_router(KnowledgeService(FakeKnowledgeEngine(), KnowledgeConfig())))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/knowledge/resolve-product",
            json=fake_incident_state.problem.model_dump(mode="json"),
        )

    assert response.status_code == 200
    assert ProductContext.model_validate(response.json()).product_name == "Order Service"


@pytest.mark.asyncio
async def test_health_and_disabled_error_are_typed(fake_incident_state: IncidentState) -> None:
    app = FastAPI()
    service = KnowledgeService(FakeKnowledgeEngine(), KnowledgeConfig(enabled=False))
    app.include_router(create_router(service))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/knowledge/health")
        failure = await client.post(
            "/knowledge/resolve-product",
            json=fake_incident_state.problem.model_dump(mode="json"),
        )

    assert ModuleHealth.model_validate(health.json()).status == "disabled"
    assert ErrorResponse.model_validate(failure.json()["detail"]).code == "KNOWLEDGE_DISABLED"
