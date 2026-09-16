"""Protocol tests for the Runtime MCP Streamable HTTP server adapter."""

from pathlib import Path

import pytest
from mcp import Client
from mcp.types import TextContent

from ops_agent.bootstrap.application import build_application_container
from ops_agent.contracts import IncidentQuery, IncidentState, StartIncidentRequest
from ops_agent.integrations.mcp.runtime.http import create_runtime_mcp_server
from ops_agent.skill_runtime import SkillInstallationConfig

ROOT = Path(__file__).parents[3]


@pytest.mark.asyncio
async def test_runtime_server_exposes_only_the_five_runtime_tools(
    fake_incident_state: IncidentState,
) -> None:
    container = build_application_container(
        SkillInstallationConfig(
            builtin_skills_path=ROOT / "skills" / "builtin",
            product_skills_path=ROOT / "tests" / "fixtures" / "product-skills",
        )
    )
    server = create_runtime_mcp_server(container.runtime_mcp)
    command = StartIncidentRequest(
        schema_version=fake_incident_state.schema_version,
        incident_id="INC-HTTP-MCP",
        request_id="REQ-HTTP-MCP",
        timestamp=fake_incident_state.timestamp,
        source="http-mcp-test",
        problem=fake_incident_state.problem.model_copy(
            update={"incident_id": "INC-HTTP-MCP", "request_id": "REQ-HTTP-MCP"}
        ),
    )

    async with Client(server) as client:
        tools = await client.list_tools()
        started = await client.call_tool(
            "incident_start",
            {"request": command.model_dump(mode="json")},
        )
        missing = await client.call_tool(
            "incident_get_state",
            {
                "request": IncidentQuery(
                    incident_id="INC-MISSING-HTTP-MCP",
                    request_id="REQ-MISSING-HTTP-MCP",
                    timestamp=fake_incident_state.timestamp,
                    source="http-mcp-test",
                ).model_dump(mode="json")
            },
        )

    assert {tool.name for tool in tools.tools} == {
        "incident_start",
        "incident_next",
        "incident_submit",
        "incident_get_state",
        "incident_finish",
    }
    assert all(tool.input_schema["required"] == ["request"] for tool in tools.tools)
    assert not started.is_error
    assert started.structured_content is not None
    assert started.structured_content["incident_id"] == "INC-HTTP-MCP"
    assert missing.is_error
    assert isinstance(missing.content[0], TextContent)
    assert "MCP_TOOL_EXECUTION_ERROR" in missing.content[0].text
