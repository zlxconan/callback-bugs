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
def all_mcp_registries() -> dict[str, McpToolRegistry]:
    now = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)
    execution = FakeExecutionTool()
    runtime = CoreRuntime(repository=InMemoryStateRepository(), clock=FixedClock(now))
    return {
        "runtime-mcp": create_runtime_mcp(runtime),
        "knowledge-mcp": create_knowledge_mcp(FakeKnowledgeEngine()),
        "observability-mcp": create_observability_mcp(
            trace=FakeEvidenceTool("fake-trace-tool"),
            log=FakeEvidenceTool("fake-log-tool"),
            metric=FakeEvidenceTool("fake-metric-tool"),
            k8s=FakeEvidenceTool("fake-k8s-tool"),
            change=FakeEvidenceTool("fake-change-tool"),
            topology=FakeEvidenceTool("fake-topology-tool"),
        ),
        "code-mcp": create_code_mcp(FakeEvidenceTool("fake-code-tool")),
        "reproduction-mcp": create_reproduction_mcp(
            browser=execution,
            api=execution,
            shell=execution,
            fault=execution,
            reproduction=FakeReproductionEngine(),
        ),
    }
