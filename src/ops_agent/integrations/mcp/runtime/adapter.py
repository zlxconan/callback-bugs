"""RuntimePort exposed as MCP tools and consumed through an MCP-shaped client."""

from typing import Any

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
from ops_agent.integrations.mcp import McpPermissionRisk, McpTool, McpToolRegistry
from ops_agent.ports import RuntimePort


def create_runtime_mcp(runtime: RuntimePort) -> McpToolRegistry:
    registry = McpToolRegistry("runtime-mcp")
    definitions = [
        McpTool(
            "incident_start",
            "runtime-mcp",
            "创建 Incident",
            StartIncidentRequest,
            IncidentState,
            "RuntimePort.start_incident",
            McpPermissionRisk.MEDIUM,
            True,
            runtime.start_incident,
        ),
        McpTool(
            "incident_next",
            "runtime-mcp",
            "领取下一 RuntimeTask",
            IncidentQuery,
            RuntimeTask,
            "RuntimePort.get_next_task",
            McpPermissionRisk.LOW,
            False,
            runtime.get_next_task,
            output_nullable=True,
        ),
        McpTool(
            "incident_submit",
            "runtime-mcp",
            "提交 TaskResult",
            TaskResult,
            IncidentState,
            "RuntimePort.submit_task_result",
            McpPermissionRisk.MEDIUM,
            True,
            runtime.submit_task_result,
        ),
        McpTool(
            "incident_get_state",
            "runtime-mcp",
            "读取 IncidentState",
            IncidentQuery,
            IncidentState,
            "RuntimePort.get_state",
            McpPermissionRisk.LOW,
            False,
            runtime.get_state,
        ),
        McpTool(
            "incident_finish",
            "runtime-mcp",
            "完成 Incident 并生成报告",
            FinishIncidentRequest,
            RCAReport,
            "RuntimePort.finish_incident",
            McpPermissionRisk.MEDIUM,
            True,
            runtime.finish_incident,
        ),
    ]
    for tool in definitions:
        registry.register(tool)
    return registry


class RuntimeMcpClient:
    """RuntimePort client used by an external Agent over the MCP adapter contract."""

    def __init__(self, registry: McpToolRegistry) -> None:
        if registry.server != "runtime-mcp":
            raise ValueError("RuntimeMcpClient requires runtime-mcp")
        self._registry = registry
        self.called_tools: list[str] = []

    async def _call(self, tool: str, request: BaseModel) -> dict[str, Any] | None:
        self.called_tools.append(tool)
        return await self._registry.call(tool, request.model_dump(mode="json"))

    async def start_incident(self, command: StartIncidentRequest) -> IncidentState:
        return IncidentState.model_validate(await self._call("incident_start", command))

    async def get_next_task(self, query: IncidentQuery) -> RuntimeTask | None:
        value = await self._call("incident_next", query)
        return None if value is None else RuntimeTask.model_validate(value)

    async def submit_task_result(self, result: TaskResult) -> IncidentState:
        return IncidentState.model_validate(await self._call("incident_submit", result))

    async def get_state(self, query: IncidentQuery) -> IncidentState:
        return IncidentState.model_validate(await self._call("incident_get_state", query))

    async def finish_incident(self, command: FinishIncidentRequest) -> RCAReport:
        return RCAReport.model_validate(await self._call("incident_finish", command))
