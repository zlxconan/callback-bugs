import pytest

from ops_agent.contracts import IncidentState, RuntimeStage, StartIncidentRequest
from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import FakeIncidentRunner, FixedClock
from ops_agent.integrations.mcp.runtime import RuntimeMcpClient, create_runtime_mcp
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.adapters import FakeReproductionEngine


@pytest.mark.asyncio
async def test_external_agent_completes_fake_e2e_through_runtime_mcp(
    fake_incident_state: IncidentState,
) -> None:
    command = StartIncidentRequest(
        schema_version=fake_incident_state.schema_version,
        incident_id=fake_incident_state.incident_id,
        request_id=fake_incident_state.request_id,
        timestamp=fake_incident_state.timestamp,
        source="runtime-mcp-e2e",
        problem=fake_incident_state.problem,
    )
    core = CoreRuntime(
        repository=InMemoryStateRepository(),
        clock=FixedClock(fake_incident_state.timestamp),
        config=RuntimeConfig(max_attempts=3, task_timeout_seconds=30),
    )
    runtime_client = RuntimeMcpClient(create_runtime_mcp(core))
    runner = FakeIncidentRunner(
        runtime=runtime_client,
        knowledge=FakeKnowledgeEngine(),
        reasoning=FakeReasoningEngine(),
        investigation=FakeInvestigationEngine(),
        reproduction=FakeReproductionEngine(),
    )

    outcome = await runner.run(command)

    assert outcome.final_state.runtime_stage is RuntimeStage.COMPLETED
    assert outcome.report is not None
    assert outcome.report.root_causes[0].hypothesis_ids == ["H-1"]
    assert runtime_client.called_tools[0] == "incident_start"
    assert runtime_client.called_tools.count("incident_submit") == 10
    assert runtime_client.called_tools.count("incident_next") == 11
    assert runtime_client.called_tools.count("incident_get_state") == 11
