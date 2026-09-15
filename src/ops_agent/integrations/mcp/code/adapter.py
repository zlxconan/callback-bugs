"""CodeGraphToolPort exposed through read-only MCP tools."""

from ops_agent.contracts import Evidence, EvidenceRequest
from ops_agent.integrations.mcp import McpPermissionRisk, McpTool, McpToolRegistry
from ops_agent.ports import CodeGraphToolPort


def create_code_mcp(code: CodeGraphToolPort) -> McpToolRegistry:
    registry = McpToolRegistry("code-mcp")
    for name, purpose in (
        ("code_search", "搜索代码并返回证据引用"),
        ("call_graph", "查询调用关系图"),
        ("stack_trace_analysis", "分析堆栈与代码位置"),
    ):
        registry.register(
            McpTool(
                name,
                "code-mcp",
                purpose,
                EvidenceRequest,
                Evidence,
                "CodeGraphToolPort.collect",
                McpPermissionRisk.LOW,
                False,
                code.collect,
            )
        )
    return registry
