"""Single-process composition root used by the deployable FastAPI application."""

from dataclasses import dataclass
from datetime import UTC, datetime

from ops_agent.bootstrap.skills import SkillInstallation, build_skill_installation
from ops_agent.bootstrap.reproduction import (
    ReproductionInstallationConfig,
    build_reproduction_service,
)
from ops_agent.core.runtime import CoreRuntime
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.mcp import McpToolRegistry
from ops_agent.integrations.mcp.runtime import create_runtime_mcp
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.investigation.domain import InvestigationConfig
from ops_agent.investigation.service import InvestigationService
from ops_agent.knowledge.domain import KnowledgeConfig
from ops_agent.knowledge.service import KnowledgeService
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reasoning.domain import ReasoningConfig
from ops_agent.reasoning.service import ReasoningService
from ops_agent.reproduction.service import ReproductionService
from ops_agent.skill_runtime import SkillInstallationConfig


class SystemClock:
    """Timezone-aware deployment adapter for the Core Runtime clock port."""

    async def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class ApplicationContainer:
    """Objects hosted by the current modular-monolith process."""

    skills: SkillInstallation
    runtime: CoreRuntime
    runtime_mcp: McpToolRegistry
    knowledge: KnowledgeService
    reasoning: ReasoningService
    investigation: InvestigationService
    reproduction: ReproductionService


def build_application_container(
    config: SkillInstallationConfig,
    *,
    reproduction_config: ReproductionInstallationConfig | None = None,
) -> ApplicationContainer:
    """Assemble existing adapters without changing Contracts, Ports, or workflow behavior."""

    skills = build_skill_installation(config)
    runtime = CoreRuntime(repository=InMemoryStateRepository(), clock=SystemClock())
    return ApplicationContainer(
        skills=skills,
        runtime=runtime,
        runtime_mcp=create_runtime_mcp(runtime),
        knowledge=KnowledgeService(
            skills.knowledge,
            KnowledgeConfig(adapter_name="product-plugin"),
        ),
        reasoning=ReasoningService(
            FakeReasoningEngine(),
            ReasoningConfig(adapter_name="fake"),
        ),
        investigation=InvestigationService(
            FakeInvestigationEngine(),
            InvestigationConfig(adapter_name="fake"),
        ),
        reproduction=build_reproduction_service(
            reproduction_config or ReproductionInstallationConfig.from_env()
        ),
    )
