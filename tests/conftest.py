"""Shared immutable Contract fixtures for Engine module tests."""

import json
from pathlib import Path
from typing import Any

import pytest

from ops_agent.contracts import (
    ExperimentExecutionRequest,
    HypothesisGenerationRequest,
    IncidentState,
)
from ops_agent.reproduction.adapters import FakeReproductionEngine

pytest_plugins = ("tests.reproduction.playwright_lab",)

_INCIDENT = (
    Path(__file__).parents[1] / "examples" / "incidents" / "duplicate-order-timeout-retry.json"
)


@pytest.fixture
def fake_incident_state() -> IncidentState:
    document: dict[str, Any] = json.loads(_INCIDENT.read_text(encoding="utf-8"))
    return IncidentState.model_validate(document["final_state"])


@pytest.fixture
def hypothesis_request(fake_incident_state: IncidentState) -> HypothesisGenerationRequest:
    state = fake_incident_state
    assert state.product is not None and state.knowledge is not None
    return HypothesisGenerationRequest(
        **state.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="reasoning-test",
        problem=state.problem,
        product=state.product,
        knowledge=state.knowledge,
        troubleshooting=state.troubleshooting,
        evidence=[],
    )


@pytest.fixture
async def execution_request(fake_incident_state: IncidentState) -> ExperimentExecutionRequest:
    state = fake_incident_state
    plan = state.experiment_plans[0]
    environment = await FakeReproductionEngine().prepare(plan)
    return ExperimentExecutionRequest(
        **state.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="reproduction-test",
        plan=plan,
        environment=environment,
    )
