from datetime import UTC, datetime

import pytest

from ops_agent.core.runtime import CoreRuntime
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import FixedClock
from ops_agent.integrations.mcp import McpToolRegistry
from ops_agent.integrations.mcp.code import create_code_mcp
from ops_agent.integrations.mcp.fake import FakeEvidenceTool, FakeExecutionTool
from ops_agent.integrations.mcp.knowledge import create_knowledge_mcp
from ops_agent.integrations.mcp.observability import create_observability_mcp
from ops_agent.integrations.mcp.reproduction import create_reproduction_mcp
from ops_agent.integrations.mcp.runtime import create_runtime_mcp
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.reproduction.adapters import FakeReproductionEngine


@pytest.fixture
def mcp_tool_names() -> set[str]:
    evidence = FakeEvidenceTool()
    execution = FakeExecutionTool()
    runtime = CoreRuntime(
        repository=InMemoryStateRepository(),
        clock=FixedClock(datetime(2026, 9, 15, 6, 0, tzinfo=UTC)),
    )
    registries: list[McpToolRegistry] = [
        create_runtime_mcp(runtime),
        create_knowledge_mcp(FakeKnowledgeEngine()),
        create_observability_mcp(
            trace=evidence,
            log=evidence,
            metric=evidence,
            k8s=evidence,
            change=evidence,
            topology=evidence,
        ),
        create_code_mcp(evidence),
        create_reproduction_mcp(
            browser=execution,
            api=execution,
            shell=execution,
            fault=execution,
            reproduction=FakeReproductionEngine(),
        ),
    ]
    return {name for registry in registries for name in registry.names()}
