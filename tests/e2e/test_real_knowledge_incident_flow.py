from datetime import UTC, datetime
from pathlib import Path

import pytest

from ops_agent.contracts import IncidentSeverity, ProblemContext, RuntimeStage, StartIncidentRequest
from ops_agent.core.runtime import CoreRuntime
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent.fake_runner import FakeIncidentRunner, FixedClock
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import RealKnowledgeEngine
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.adapters import FakeReproductionEngine
from ops_agent.skill_runtime import SkillLoader, SkillRegistry, SkillResolver

NOW = datetime(2026, 9, 16, 3, 0, tzinfo=UTC)
FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "product-skills"


@pytest.mark.asyncio
async def test_real_knowledge_replaces_fake_in_complete_runtime_flow() -> None:
    problem = ProblemContext(
        incident_id="INC-REAL-KNOWLEDGE-E2E",
        request_id="REQ-REAL-KNOWLEDGE-E2E",
        timestamp=NOW,
        source="real-knowledge-e2e",
        title="Create order timed out and retry produced a duplicate",
        description="One business key has two orders after an automatic retry.",
        symptoms=["first response timed out", "client retried", "duplicate order"],
        severity=IncidentSeverity.HIGH,
        observed_at=NOW,
        affected_services=["create-api"],
        environment={"product": "TestProduct", "version": "1.0"},
    )
    registry = SkillRegistry(SkillLoader(FIXTURE_ROOT))
    registry.refresh()
    runner = FakeIncidentRunner(
        runtime=CoreRuntime(
            repository=InMemoryStateRepository(),
            clock=FixedClock(NOW),
        ),
        knowledge=RealKnowledgeEngine(SkillResolver(registry)),
        reasoning=FakeReasoningEngine(),
        investigation=FakeInvestigationEngine(),
        reproduction=FakeReproductionEngine(),
    )

    outcome = await runner.run(
        StartIncidentRequest(
            incident_id=problem.incident_id,
            request_id=problem.request_id,
            timestamp=NOW,
            source="real-knowledge-e2e",
            problem=problem,
        )
    )

    assert outcome.final_state.runtime_stage is RuntimeStage.COMPLETED
    assert outcome.final_state.product is not None
    assert outcome.final_state.product.product_name == "TestProduct"
    assert outcome.final_state.product.product_version == "1.0"
    assert outcome.final_state.knowledge is not None
    assert outcome.final_state.knowledge.skill_ids == ["test-product-product-v1"]
    assert any("duplicate create" in fact for fact in outcome.final_state.knowledge.facts)
    assert outcome.report is not None
    assert outcome.report.root_causes
