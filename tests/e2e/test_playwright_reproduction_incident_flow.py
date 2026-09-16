from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.e2e.test_fake_incident_flow import incident_request
from tests.reproduction.playwright_lab import LabServer

from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import FakeIncidentRunner, FixedClock
from ops_agent.integrations.mcp.fake import (
    FakeApiTool,
    FakeFaultInjectionTool,
    FakeShellTool,
)
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.adapters.browser.playwright import (
    PlaywrightBrowserAdapter,
    PlaywrightBrowserConfig,
)
from ops_agent.reproduction.domain import ReproductionConfig
from ops_agent.reproduction.service import RealReproductionEngine


@pytest.mark.asyncio
async def test_playwright_browser_replaces_fake_in_runtime_e2e(
    browser_lab: LabServer,
    tmp_path: Path,
) -> None:
    browser = PlaywrightBrowserAdapter(
        PlaywrightBrowserConfig(base_url=browser_lab.url, screenshot_dir=tmp_path)
    )
    reproduction = RealReproductionEngine(
        browser=browser,
        api=FakeApiTool(),
        shell=FakeShellTool(),
        fault=FakeFaultInjectionTool(),
        config=ReproductionConfig(tool_timeout_seconds=5),
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
    assert outcome.final_state.experiment_results[-1].outputs["request_count"] == 2
    assert outcome.final_state.verification_results[-1].status == "confirmed"
    assert browser.active_browser_count == 0
