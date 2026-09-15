"""Reproduction and execution Tool Ports exposed through MCP tools."""

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentResult,
)
from ops_agent.integrations.mcp import McpPermissionRisk, McpTool, McpToolRegistry
from ops_agent.ports import (
    ApiToolPort,
    BrowserToolPort,
    FaultInjectionToolPort,
    ReproductionPort,
    ShellToolPort,
)


def create_reproduction_mcp(
    *,
    browser: BrowserToolPort,
    api: ApiToolPort,
    shell: ShellToolPort,
    fault: FaultInjectionToolPort,
    reproduction: ReproductionPort,
) -> McpToolRegistry:
    registry = McpToolRegistry("reproduction-mcp")
    execution_tools = [
        (
            "browser_action",
            "执行受控浏览器动作",
            "BrowserToolPort.execute",
            McpPermissionRisk.MEDIUM,
            browser.execute,
        ),
        (
            "api_call",
            "执行受控 API 调用",
            "ApiToolPort.execute",
            McpPermissionRisk.MEDIUM,
            api.execute,
        ),
        (
            "shell_execute",
            "执行受控 Shell 操作",
            "ShellToolPort.execute",
            McpPermissionRisk.HIGH,
            shell.execute,
        ),
        (
            "fault_inject",
            "执行已批准的故障注入",
            "FaultInjectionToolPort.apply",
            McpPermissionRisk.HIGH,
            fault.apply,
        ),
        (
            "experiment_execute",
            "执行完整实验计划",
            "ReproductionPort.execute",
            McpPermissionRisk.HIGH,
            reproduction.execute,
        ),
    ]
    for name, purpose, port, risk, handler in execution_tools:
        registry.register(
            McpTool(
                name,
                "reproduction-mcp",
                purpose,
                ExperimentExecutionRequest,
                ExperimentResult,
                port,
                risk,
                True,
                handler,
            )
        )
    registry.register(
        McpTool(
            "experiment_cleanup",
            "reproduction-mcp",
            "清理实验环境",
            EnvironmentCleanupRequest,
            CleanupResult,
            "ReproductionPort.cleanup",
            McpPermissionRisk.MEDIUM,
            True,
            reproduction.cleanup,
        )
    )
    return registry
