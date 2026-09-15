"""Typed Port clients over a transport-neutral MCP registry."""

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    Evidence,
    EvidenceRequest,
    ExperimentExecutionRequest,
    ExperimentResult,
    KnowledgeContext,
    KnowledgeQuery,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.integrations.mcp.registry import McpToolRegistry


class EvidenceMcpClient:
    """Collect-shaped Tool Port client for observability or code MCP tools."""

    def __init__(self, registry: McpToolRegistry, tool_name: str) -> None:
        tool = registry.get(tool_name)
        if tool.input_model is not EvidenceRequest or tool.output_model is not Evidence:
            raise ValueError(f"MCP tool is not an evidence collector: {tool_name}")
        self._registry = registry
        self._tool_name = tool_name

    async def collect(self, request: EvidenceRequest) -> Evidence:
        payload = await self._registry.call(self._tool_name, request.model_dump(mode="json"))
        return Evidence.model_validate(payload)


class ExecutionMcpClient:
    """Execute-shaped Tool Port client for browser, API, or Shell MCP tools."""

    def __init__(self, registry: McpToolRegistry, tool_name: str) -> None:
        tool = registry.get(tool_name)
        if (
            tool.input_model is not ExperimentExecutionRequest
            or tool.output_model is not ExperimentResult
        ):
            raise ValueError(f"MCP tool is not an experiment executor: {tool_name}")
        self._registry = registry
        self._tool_name = tool_name

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        payload = await self._registry.call(self._tool_name, request.model_dump(mode="json"))
        return ExperimentResult.model_validate(payload)


class FaultInjectionMcpClient:
    """FaultInjectionToolPort client using inject and cleanup MCP operations."""

    def __init__(self, registry: McpToolRegistry) -> None:
        self._registry = registry
        registry.get("fault_inject")
        registry.get("experiment_cleanup")

    async def apply(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        payload = await self._registry.call("fault_inject", request.model_dump(mode="json"))
        return ExperimentResult.model_validate(payload)

    async def rollback(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        payload = await self._registry.call("experiment_cleanup", request.model_dump(mode="json"))
        return CleanupResult.model_validate(payload)


class KnowledgeMcpClient:
    """KnowledgePort client suitable for a remote deployment adapter."""

    def __init__(self, registry: McpToolRegistry) -> None:
        if registry.server != "knowledge-mcp":
            raise ValueError("KnowledgeMcpClient requires knowledge-mcp")
        self._registry = registry

    async def resolve_product(self, problem: ProblemContext) -> ProductContext:
        payload = await self._registry.call("product_query", problem.model_dump(mode="json"))
        return ProductContext.model_validate(payload)

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext:
        payload = await self._registry.call("version_query", query.model_dump(mode="json"))
        return KnowledgeContext.model_validate(payload)

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext:
        payload = await self._registry.call("troubleshooting_query", query.model_dump(mode="json"))
        return TroubleshootingContext.model_validate(payload)
