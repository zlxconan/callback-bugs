import httpx
import pytest
from fastapi import FastAPI

from ops_agent.contracts import (
    ErrorResponse,
    ExperimentExecutionRequest,
    ExperimentResult,
    ModuleHealth,
)
from ops_agent.reproduction.adapters import FakeReproductionEngine
from ops_agent.reproduction.api import create_router
from ops_agent.reproduction.domain import ReproductionConfig
from ops_agent.reproduction.service import ReproductionService


@pytest.mark.asyncio
async def test_execute_http_contract_round_trip(
    execution_request: ExperimentExecutionRequest,
) -> None:
    app = FastAPI()
    service = ReproductionService(FakeReproductionEngine(), ReproductionConfig())
    app.include_router(create_router(service))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/reproduction/execute",
            json=execution_request.model_dump(mode="json"),
        )

    assert response.status_code == 200
    assert ExperimentResult.model_validate(response.json()).outputs["orders_created"] == 2


@pytest.mark.asyncio
async def test_health_and_disabled_error_are_typed(
    execution_request: ExperimentExecutionRequest,
) -> None:
    app = FastAPI()
    service = ReproductionService(FakeReproductionEngine(), ReproductionConfig(enabled=False))
    app.include_router(create_router(service))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/reproduction/health")
        failure = await client.post(
            "/reproduction/execute", json=execution_request.model_dump(mode="json")
        )

    assert ModuleHealth.model_validate(health.json()).status == "disabled"
    assert ErrorResponse.model_validate(failure.json()["detail"]).code == "REPRODUCTION_DISABLED"
