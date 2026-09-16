from datetime import UTC, datetime
from pathlib import Path

import pytest

from ops_agent.contracts import IncidentSeverity, ProblemContext
from ops_agent.knowledge.adapters import RealKnowledgeEngine
from ops_agent.skill_runtime import SkillLoader, SkillRegistry, SkillResolver

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "product-skills"
NOW = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)


@pytest.fixture
def real_knowledge() -> RealKnowledgeEngine:
    registry = SkillRegistry(SkillLoader(FIXTURE_ROOT))
    registry.refresh()
    return RealKnowledgeEngine(SkillResolver(registry))


def product_problem(*, product: str = "TestProduct", version: str = "1.0") -> ProblemContext:
    return ProblemContext(
        incident_id="INC-REAL-KNOWLEDGE",
        request_id="REQ-REAL-KNOWLEDGE",
        timestamp=NOW,
        source="real-knowledge-test",
        title="Create order timed out and was retried",
        description="The retry created a duplicate order for one business key.",
        symptoms=["first response timed out", "client retried", "duplicate order"],
        severity=IncidentSeverity.HIGH,
        observed_at=NOW,
        affected_services=["create-api"],
        environment={"product": product, "version": version},
    )
