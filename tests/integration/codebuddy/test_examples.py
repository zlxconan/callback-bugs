import json
import tomllib
from pathlib import Path

from ops_agent.integrations.codebuddy import CodeBuddyAdapterConfig

EXAMPLES = Path(__file__).parents[3] / "examples" / "integrations" / "codebuddy"


def test_codebuddy_configuration_examples_parse() -> None:
    adapter = tomllib.loads((EXAMPLES / "adapter.example.toml").read_text(encoding="utf-8"))
    mcp = json.loads((EXAMPLES / "mcp.example.json").read_text(encoding="utf-8"))

    config = CodeBuddyAdapterConfig.model_validate(adapter)

    assert config.runtime_transport == "mcp"
    assert config.skills_target == "codebuddy"
    assert "ops-agent-runtime" in mcp["mcpServers"]
    assert mcp["mcpServers"]["ops-agent-runtime"] == {
        "type": "http",
        "url": "http://127.0.0.1:8000/mcp/runtime/",
        "description": "Ops Agent Core Runtime MCP",
    }
    assert set(mcp["mcpServers"]) == {"ops-agent-runtime"}


def test_example_prompt_uses_runtime_protocol() -> None:
    prompt = (EXAMPLES / "example-prompt.md").read_text(encoding="utf-8")

    for operation in ("incident_start", "incident_next", "incident_submit"):
        assert operation in prompt
    assert "不要直接修改 IncidentState" in prompt
