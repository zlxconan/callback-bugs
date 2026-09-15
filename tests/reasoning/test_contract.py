import httpx
import pytest
from fastapi import FastAPI

from ops_agent.contracts import (
    ErrorResponse,
    HypothesisGenerationRequest,
    HypothesisSet,
    ModuleHealth,
)
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reasoning.api import create_router
from ops_agent.reasoning.domain import ReasoningConfig
from ops_agent.reasoning.service import ReasoningService


@pytest.mark.asyncio
async def test_generate_hypotheses_http_contract_round_trip(
    hypothesis_request: HypothesisGenerationRequest,
) -> None:
    app = FastAPI()
    app.include_router(create_router(ReasoningService(FakeReasoningEngine(), ReasoningConfig())))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/reasoning/hypotheses",
            json=hypothesis_request.model_dump(mode="json"),
        )

    assert response.status_code == 200
    assert HypothesisSet.model_validate(response.json()).prioritized_hypothesis_ids[0] == "H-1"


@pytest.mark.asyncio
async def test_health_and_disabled_error_are_typed(
    hypothesis_request: HypothesisGenerationRequest,
) -> None:
    app = FastAPI()
    service = ReasoningService(FakeReasoningEngine(), ReasoningConfig(enabled=False))
    app.include_router(create_router(service))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/reasoning/health")
        failure = await client.post(
            "/reasoning/hypotheses", json=hypothesis_request.model_dump(mode="json")
        )

    assert ModuleHealth.model_validate(health.json()).status == "disabled"
    assert ErrorResponse.model_validate(failure.json()["detail"]).code == "REASONING_DISABLED"
