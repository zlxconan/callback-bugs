"""KnowledgePort exposed through standardized MCP tools."""

from ops_agent.contracts import (
    KnowledgeContext,
    KnowledgeQuery,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.integrations.mcp import McpPermissionRisk, McpTool, McpToolRegistry
from ops_agent.ports import KnowledgePort


def create_knowledge_mcp(knowledge: KnowledgePort) -> McpToolRegistry:
    registry = McpToolRegistry("knowledge-mcp")
    tools = [
        McpTool(
            "product_query",
            "knowledge-mcp",
            "根据问题解析产品和版本上下文",
            ProblemContext,
            ProductContext,
            "KnowledgePort.resolve_product",
            McpPermissionRisk.LOW,
            False,
            knowledge.resolve_product,
        ),
        McpTool(
            "version_query",
            "knowledge-mcp",
            "查询指定产品版本知识",
            KnowledgeQuery,
            KnowledgeContext,
            "KnowledgePort.query_product_knowledge",
            McpPermissionRisk.LOW,
            False,
            knowledge.query_product_knowledge,
        ),
        McpTool(
            "troubleshooting_query",
            "knowledge-mcp",
            "查询结构化排障知识",
            KnowledgeQuery,
            TroubleshootingContext,
            "KnowledgePort.query_troubleshooting",
            McpPermissionRisk.LOW,
            False,
            knowledge.query_troubleshooting,
        ),
    ]
    for tool in tools:
        registry.register(tool)
    return registry
