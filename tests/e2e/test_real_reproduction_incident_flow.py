from datetime import UTC, datetime

import pytest
from tests.e2e.test_fake_incident_flow import incident_request

from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import FakeIncidentRunner, FixedClock
from ops_agent.integrations.mcp.fake import (
    FakeApiTool,
    FakeBrowserTool,
    FakeFaultInjectionTool,
    FakeShellTool,
)
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.domain import ReproductionConfig
from ops_agent.reproduction.service import RealReproductionEngine


@pytest.mark.asyncio
async def test_real_reproduction_replaces_fake_without_other_engine_changes() -> None:
    fault = FakeFaultInjectionTool()
    reproduction = RealReproductionEngine(
        browser=FakeBrowserTool(),
        api=FakeApiTool(),
        shell=FakeShellTool(),
        fault=fault,
        config=ReproductionConfig(),
    )
    runner = FakeIncidentRunner(
        runtime=CoreRuntime(
            repository=InMemoryStateRepository(),
            clock=FixedClock(datetime(2026, 9, 15, 6, 0, tzinfo=UTC)),
            config=RuntimeConfig(max_reflection_loops=3),
        ),
        knowledge=FakeKnowledgeEngine(),
        reasoning=FakeReasoningEngine(),
        investigation=FakeInvestigationEngine(),
        reproduction=reproduction,
    )

    outcome = await runner.run(incident_request())

    assert outcome.final_state.runtime_stage == "completed"
    assert outcome.final_state.experiment_results[-1].outputs["orders_created"] == 2
    assert outcome.final_state.verification_results[-1].status == "confirmed"
    assert outcome.report is not None
    assert fault.rollback_calls == 1
