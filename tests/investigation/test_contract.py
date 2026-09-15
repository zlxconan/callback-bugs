import httpx
import pytest
from fastapi import FastAPI

from ops_agent.contracts import ErrorResponse, EvidenceBatch, IncidentState, ModuleHealth
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.investigation.api import create_router
from ops_agent.investigation.domain import InvestigationConfig
from ops_agent.investigation.service import InvestigationService


@pytest.mark.asyncio
async def test_collect_batch_http_contract_round_trip(fake_incident_state: IncidentState) -> None:
    app = FastAPI()
    service = InvestigationService(FakeInvestigationEngine(), InvestigationConfig())
    app.include_router(create_router(service))
    plan = fake_incident_state.latest_evidence_plan
    assert plan is not None
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/investigation/collect-batch", json=plan.model_dump(mode="json")
        )

    assert response.status_code == 200
    assert len(EvidenceBatch.model_validate(response.json()).evidence) == 4


@pytest.mark.asyncio
async def test_health_and_disabled_error_are_typed(fake_incident_state: IncidentState) -> None:
    app = FastAPI()
    service = InvestigationService(FakeInvestigationEngine(), InvestigationConfig(enabled=False))
    app.include_router(create_router(service))
    plan = fake_incident_state.latest_evidence_plan
    assert plan is not None
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/investigation/health")
        failure = await client.post(
            "/investigation/collect-batch", json=plan.model_dump(mode="json")
        )

    assert ModuleHealth.model_validate(health.json()).status == "disabled"
    assert ErrorResponse.model_validate(failure.json()["detail"]).code == "INVESTIGATION_DISABLED"
