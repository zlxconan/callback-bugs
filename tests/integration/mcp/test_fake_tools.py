import pytest

from ops_agent.contracts import (
    Evidence,
    ExperimentExecutionRequest,
    ExperimentResult,
    IncidentState,
    ProductContext,
)
from ops_agent.integrations.mcp import (
    EvidenceMcpClient,
    ExecutionMcpClient,
    FaultInjectionMcpClient,
    KnowledgeMcpClient,
    McpInvocationError,
    McpToolRegistry,
)
from ops_agent.ports import (
    ApiToolPort,
    FaultInjectionToolPort,
    KnowledgePort,
    TraceToolPort,
)


@pytest.mark.asyncio
async def test_fake_knowledge_and_observability_tools_map_contracts(
    all_mcp_registries: dict[str, McpToolRegistry],
    fake_incident_state: IncidentState,
) -> None:
    state = fake_incident_state
    knowledge = all_mcp_registries["knowledge-mcp"]
    observability = all_mcp_registries["observability-mcp"]
    assert state.latest_evidence_plan is not None

    product_payload = await knowledge.call("product_query", state.problem.model_dump(mode="json"))
    evidence_payload = await observability.call(
        "trace_query",
        state.latest_evidence_plan.requests[0].model_dump(mode="json"),
    )

    assert ProductContext.model_validate(product_payload).product_name == "Order Service"
    assert Evidence.model_validate(evidence_payload).source == "fake-trace-tool"


@pytest.mark.asyncio
async def test_fake_code_and_reproduction_tools_map_contracts(
    all_mcp_registries: dict[str, McpToolRegistry],
    fake_incident_state: IncidentState,
    execution_request: ExperimentExecutionRequest,
) -> None:
    assert fake_incident_state.latest_evidence_plan is not None
    code_payload = await all_mcp_registries["code-mcp"].call(
        "call_graph",
        fake_incident_state.latest_evidence_plan.requests[0].model_dump(mode="json"),
    )
    result_payload = await all_mcp_registries["reproduction-mcp"].call(
        "shell_execute", execution_request.model_dump(mode="json")
    )

    assert Evidence.model_validate(code_payload).source == "fake-code-tool"
    assert ExperimentResult.model_validate(result_payload).outputs["action"] == "execute"


@pytest.mark.asyncio
async def test_typed_mcp_clients_can_be_injected_as_engine_tool_ports(
    all_mcp_registries: dict[str, McpToolRegistry],
    fake_incident_state: IncidentState,
    execution_request: ExperimentExecutionRequest,
) -> None:
    assert fake_incident_state.latest_evidence_plan is not None
    evidence_client = EvidenceMcpClient(all_mcp_registries["observability-mcp"], "trace_query")
    execution_client = ExecutionMcpClient(all_mcp_registries["reproduction-mcp"], "api_call")
    fault_client = FaultInjectionMcpClient(all_mcp_registries["reproduction-mcp"])
    knowledge_client = KnowledgeMcpClient(all_mcp_registries["knowledge-mcp"])

    assert isinstance(evidence_client, TraceToolPort)
    assert isinstance(execution_client, ApiToolPort)
    assert isinstance(fault_client, FaultInjectionToolPort)
    assert isinstance(knowledge_client, KnowledgePort)
    evidence = await evidence_client.collect(fake_incident_state.latest_evidence_plan.requests[0])
    result = await execution_client.execute(execution_request)

    assert evidence.source == "fake-trace-tool"
    assert result.outputs["action"] == "execute"


@pytest.mark.asyncio
async def test_invalid_tool_input_returns_standard_error_contract(
    all_mcp_registries: dict[str, McpToolRegistry],
) -> None:
    registry = all_mcp_registries["runtime-mcp"]

    with pytest.raises(McpInvocationError) as captured:
        await registry.call("incident_start", {})

    assert captured.value.error.code == "MCP_INPUT_VALIDATION_ERROR"
    assert captured.value.error.category == "validation"
