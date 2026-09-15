"""Observation Tool Ports exposed through read-only MCP tools."""

from ops_agent.contracts import Evidence, EvidenceRequest
from ops_agent.integrations.mcp import McpPermissionRisk, McpTool, McpToolRegistry
from ops_agent.ports import (
    ChangeToolPort,
    K8sToolPort,
    LogToolPort,
    MetricToolPort,
    TopologyToolPort,
    TraceToolPort,
)


def create_observability_mcp(
    *,
    trace: TraceToolPort,
    log: LogToolPort,
    metric: MetricToolPort,
    k8s: K8sToolPort,
    change: ChangeToolPort,
    topology: TopologyToolPort,
) -> McpToolRegistry:
    registry = McpToolRegistry("observability-mcp")
    definitions = [
        ("trace_query", "查询调用链", trace, "TraceToolPort.collect"),
        ("log_query", "查询日志", log, "LogToolPort.collect"),
        ("metric_query", "查询指标", metric, "MetricToolPort.collect"),
        ("k8s_inspect", "检查 Kubernetes 资源", k8s, "K8sToolPort.collect"),
        ("change_query", "查询变更历史", change, "ChangeToolPort.collect"),
        ("topology_query", "查询服务拓扑", topology, "TopologyToolPort.collect"),
    ]
    for name, purpose, port, port_name in definitions:
        registry.register(
            McpTool(
                name,
                "observability-mcp",
                purpose,
                EvidenceRequest,
                Evidence,
                port_name,
                McpPermissionRisk.LOW,
                False,
                port.collect,
            )
        )
    return registry
