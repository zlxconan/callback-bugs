from pathlib import Path

import pytest

from ops_agent.contracts import IncidentState, RuntimeTask, StartIncidentRequest, TaskStatus
from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import (
    FakeLLMProvider,
    FakeTaskReasoner,
    FixedClock,
    LocalAgentConfig,
    LocalAgentRunner,
    LocalSmallModelAgent,
    StructuredTaskOutputValidator,
)
from ops_agent.integrations.mcp.runtime import RuntimeMcpClient, create_runtime_mcp
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.adapters import FakeReproductionEngine
from ops_agent.skills import CanonicalSkill, SkillCatalog

SKILLS_ROOT = Path(__file__).parents[3] / "skills"


def task_reasoner() -> FakeTaskReasoner:
    return FakeTaskReasoner(
        knowledge=FakeKnowledgeEngine(),
        reasoning=FakeReasoningEngine(),
        investigation=FakeInvestigationEngine(),
        reproduction=FakeReproductionEngine(),
    )


def start_command(state: IncidentState) -> StartIncidentRequest:
    return StartIncidentRequest(
        schema_version=state.schema_version,
        incident_id=state.incident_id,
        request_id=state.request_id,
        timestamp=state.timestamp,
        source="local-agent-e2e",
        problem=state.problem,
    )


@pytest.mark.asyncio
async def test_retry_then_accepts_structured_output(
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
    hypothesis_skills: tuple[CanonicalSkill, ...],
) -> None:
    provider = FakeLLMProvider(task_reasoner(), scripted_responses=["not-json"])
    agent = LocalSmallModelAgent(
        provider=provider,
        validator=StructuredTaskOutputValidator(max_hypotheses=3),
        config=LocalAgentConfig(max_validation_attempts=2),
    )

    result = await agent.reason(hypothesis_task, fake_incident_state, hypothesis_skills)

    assert result.status is TaskStatus.SUCCEEDED
    assert provider.call_count == 2
    assert agent.retry_count == 1


@pytest.mark.asyncio
async def test_falls_back_after_validation_retries(
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
    hypothesis_skills: tuple[CanonicalSkill, ...],
) -> None:
    provider = FakeLLMProvider(
        task_reasoner(), scripted_responses=["not-json", '{"hypotheses": {}}']
    )
    fallback = FakeLLMProvider(task_reasoner()).as_reasoning_owner()
    agent = LocalSmallModelAgent(
        provider=provider,
        validator=StructuredTaskOutputValidator(max_hypotheses=3),
        config=LocalAgentConfig(max_validation_attempts=2),
        fallback=fallback,
    )

    result = await agent.reason(hypothesis_task, fake_incident_state, hypothesis_skills)

    assert result.status is TaskStatus.SUCCEEDED
    assert provider.call_count == 2
    assert agent.fallback_count == 1


@pytest.mark.asyncio
async def test_fake_llm_provider_drives_complete_runtime_e2e(
    fake_incident_state: IncidentState,
) -> None:
    runtime = RuntimeMcpClient(
        create_runtime_mcp(
            CoreRuntime(
                repository=InMemoryStateRepository(),
                clock=FixedClock(fake_incident_state.timestamp),
                config=RuntimeConfig(max_attempts=3, task_timeout_seconds=30),
            )
        )
    )
    provider = FakeLLMProvider(task_reasoner())
    agent = LocalSmallModelAgent(
        provider=provider,
        validator=StructuredTaskOutputValidator(max_hypotheses=3),
        config=LocalAgentConfig(max_validation_attempts=2),
    )
    runner = LocalAgentRunner(
        runtime=runtime,
        agent=agent,
        skill_catalog=SkillCatalog(SKILLS_ROOT),
        max_iterations=50,
    )

    outcome = await runner.run(start_command(fake_incident_state))

    assert outcome.final_state.status == "resolved"
    assert outcome.final_state.rca_report is not None
    assert provider.call_count == 10
    assert agent.validated_output_count == 10
