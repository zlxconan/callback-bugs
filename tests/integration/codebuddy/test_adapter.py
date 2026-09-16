from pathlib import Path

import pytest

from ops_agent.contracts import IncidentState, RuntimeStage, StartIncidentRequest
from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.codebuddy import (
    CodeBuddyAdapter,
    CodeBuddyAdapterConfig,
    FakeExternalAgent,
    RuntimeTaskSkillRouter,
)
from ops_agent.integrations.local_agent import FakeTaskReasoner, FixedClock
from ops_agent.integrations.mcp.runtime import RuntimeMcpClient, create_runtime_mcp
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.adapters import FakeReproductionEngine
from ops_agent.skills import SkillCatalog

SKILLS_ROOT = Path(__file__).parents[3] / "skills" / "builtin"


def command_from(state: IncidentState) -> StartIncidentRequest:
    return StartIncidentRequest(
        schema_version=state.schema_version,
        incident_id=state.incident_id,
        request_id=state.request_id,
        timestamp=state.timestamp,
        source="codebuddy-adapter-test",
        problem=state.problem,
    )


def test_runtime_task_skill_routing_is_explicit() -> None:
    router = RuntimeTaskSkillRouter(SkillCatalog(SKILLS_ROOT))

    assert router.names_for(RuntimeStage.KNOWLEDGE_LOOKUP) == ("incident-analysis",)
    assert router.names_for(RuntimeStage.HYPOTHESIS) == ("hypothesis-generation",)
    assert router.names_for(RuntimeStage.EVIDENCE_PLAN) == ("evidence-planning",)
    assert router.names_for(RuntimeStage.REFLECT) == ("reflection",)
    assert router.names_for(RuntimeStage.EXPERIMENT_PLAN) == ("reproduction-planning",)
    assert router.names_for(RuntimeStage.RCA) == ("rca-report",)


@pytest.mark.asyncio
async def test_fake_external_agent_runs_next_reason_submit_e2e(
    fake_incident_state: IncidentState,
) -> None:
    core = CoreRuntime(
        repository=InMemoryStateRepository(),
        clock=FixedClock(fake_incident_state.timestamp),
        config=RuntimeConfig(max_attempts=3, task_timeout_seconds=30),
    )
    runtime = RuntimeMcpClient(create_runtime_mcp(core))
    task_executor = FakeTaskReasoner(
        knowledge=FakeKnowledgeEngine(),
        reasoning=FakeReasoningEngine(),
        investigation=FakeInvestigationEngine(),
        reproduction=FakeReproductionEngine(),
    )
    reasoning_owner = FakeExternalAgent(task_executor)
    assert not hasattr(reasoning_owner, "start_incident")
    assert not hasattr(reasoning_owner, "submit_task_result")
    adapter = CodeBuddyAdapter(
        runtime=runtime,
        skill_router=RuntimeTaskSkillRouter(SkillCatalog(SKILLS_ROOT)),
        reasoning_owner=reasoning_owner,
        config=CodeBuddyAdapterConfig(runtime_transport="mcp", max_iterations=50),
    )

    outcome = await adapter.run(command_from(fake_incident_state))

    assert outcome.final_state.runtime_stage is RuntimeStage.COMPLETED
    assert outcome.final_state.rca_report is not None
    assert reasoning_owner.reason_count == 10
    assert outcome.loaded_skills == reasoning_owner.loaded_skills
    assert "incident-analysis" in outcome.loaded_skills
    assert "rca-report" in outcome.loaded_skills
    assert runtime.called_tools.count("incident_next") == 11
    assert runtime.called_tools.count("incident_submit") == 10
