"""Official MCP Streamable HTTP bridge for the existing Runtime tool registry."""

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from ops_agent.contracts import (
    FinishIncidentRequest,
    IncidentQuery,
    IncidentState,
    RCAReport,
    RuntimeTask,
    StartIncidentRequest,
    TaskResult,
)
from ops_agent.integrations.mcp import McpInvocationError, McpToolRegistry


def create_runtime_mcp_server(registry: McpToolRegistry) -> MCPServer:
    """Expose exactly the Runtime MCP registry through the official MCP protocol."""

    if registry.server != "runtime-mcp":
        raise ValueError("Runtime MCP HTTP bridge requires runtime-mcp")

    server = MCPServer(
        name="ops-agent-runtime",
        title="Ops Agent Runtime MCP",
        description="Contract-validated Incident lifecycle tools owned by Core Runtime.",
        version="0.1.0",
    )

    @server.tool(description="Create an Incident through Core Runtime.", structured_output=True)
    async def incident_start(request: StartIncidentRequest) -> IncidentState:
        result = await _call(registry, "incident_start", request)
        return IncidentState.model_validate(result)

    @server.tool(description="Get the next RuntimeTask without changing workflow rules.")
    async def incident_next(request: IncidentQuery) -> RuntimeTask | None:
        result = await _call(registry, "incident_next", request)
        return None if result is None else RuntimeTask.model_validate(result)

    @server.tool(description="Submit one structured TaskResult to Core Runtime.")
    async def incident_submit(request: TaskResult) -> IncidentState:
        result = await _call(registry, "incident_submit", request)
        return IncidentState.model_validate(result)

    @server.tool(description="Read the authoritative IncidentState from Core Runtime.")
    async def incident_get_state(request: IncidentQuery) -> IncidentState:
        result = await _call(registry, "incident_get_state", request)
        return IncidentState.model_validate(result)

    @server.tool(description="Return the completed RCAReport for an Incident.")
    async def incident_finish(request: FinishIncidentRequest) -> RCAReport:
        result = await _call(registry, "incident_finish", request)
        return RCAReport.model_validate(result)

    return server


async def _call(
    registry: McpToolRegistry,
    name: str,
    request: BaseModel,
) -> dict[str, object] | None:
    try:
        return await registry.call(name, request.model_dump(mode="json"))
    except McpInvocationError as error:
        raise ToolError(error.error.model_dump_json()) from error
