from datetime import UTC, datetime

from pydantic import BaseModel

from ops_agent.contracts import IncidentQuery, IncidentState, StartIncidentRequest
from ops_agent.core.runtime import CoreRuntime
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import FixedClock
from ops_agent.integrations.mcp import McpPermissionRisk
from ops_agent.integrations.mcp.registry import McpToolRegistry
from ops_agent.integrations.mcp.runtime import RuntimeMcpClient, create_runtime_mcp
from ops_agent.ports import RuntimePort

NOW = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)


def test_runtime_tools_expose_existing_contract_schemas() -> None:
    runtime = CoreRuntime(repository=InMemoryStateRepository(), clock=FixedClock(NOW))
    registry = create_runtime_mcp(runtime)

    start = registry.get("incident_start")
    state = registry.get("incident_get_state")

    assert start.input_model is StartIncidentRequest
    assert start.output_model is IncidentState
    assert start.input_schema == StartIncidentRequest.model_json_schema()
    assert start.write is True
    assert start.risk is McpPermissionRisk.MEDIUM
    assert state.input_model is IncidentQuery
    assert state.write is False


def test_all_required_mcp_tools_are_registered(
    all_mcp_registries: dict[str, McpToolRegistry],
) -> None:
    expected = {
        "runtime-mcp": {
            "incident_start",
            "incident_next",
            "incident_submit",
            "incident_get_state",
            "incident_finish",
        },
        "knowledge-mcp": {"product_query", "version_query", "troubleshooting_query"},
        "observability-mcp": {
            "trace_query",
            "log_query",
            "metric_query",
            "k8s_inspect",
            "change_query",
            "topology_query",
        },
        "code-mcp": {"code_search", "call_graph", "stack_trace_analysis"},
        "reproduction-mcp": {
            "browser_action",
            "api_call",
            "shell_execute",
            "fault_inject",
            "experiment_execute",
            "experiment_cleanup",
        },
    }

    assert {
        name: set(registry.names()) for name, registry in all_mcp_registries.items()
    } == expected

    for registry in all_mcp_registries.values():
        for name in registry.names():
            tool = registry.get(name)
            assert issubclass(tool.input_model, BaseModel)
            assert issubclass(tool.output_model, BaseModel)
            assert tool.input_model.__module__.startswith("ops_agent.contracts")
            assert tool.output_model.__module__.startswith("ops_agent.contracts")
            assert tool.input_schema["type"] == "object"


def test_runtime_mcp_client_implements_runtime_port() -> None:
    runtime = CoreRuntime(repository=InMemoryStateRepository(), clock=FixedClock(NOW))

    assert isinstance(RuntimeMcpClient(create_runtime_mcp(runtime)), RuntimePort)
