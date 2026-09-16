"""CodeBuddy plugin packaging contract tests."""

import json
from pathlib import Path

from ops_agent.skills import SkillCatalog

ROOT = Path(__file__).parents[3]
PLUGIN = ROOT / "integrations" / "codebuddy" / "ops-agent-plugin"
CANONICAL = ROOT / "skills" / "builtin"
EXPECTED_SKILLS = {
    "incident-analysis",
    "hypothesis-generation",
    "evidence-planning",
    "reflection",
    "reproduction-planning",
    "rca-report",
}


def test_plugin_manifest_uses_official_layout_and_non_sensitive_endpoint() -> None:
    manifest = json.loads(
        (PLUGIN / ".codebuddy-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert manifest["name"] == "ops-agent"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert manifest["userConfig"] == {
        "runtime_endpoint": {
            "description": "Ops Agent Runtime MCP Streamable HTTP endpoint",
            "sensitive": False,
        }
    }
    assert "runtime_token" not in manifest["userConfig"]


def test_plugin_connects_only_to_runtime_mcp_over_http() -> None:
    config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))

    assert config == {
        "mcpServers": {
            "ops-agent-runtime": {
                "type": "http",
                "url": "${user_config.runtime_endpoint}",
                "description": "Ops Agent Core Runtime MCP",
            }
        }
    }


def test_plugin_skills_are_generated_from_canonical_sources() -> None:
    canonical = {skill.name: skill for skill in SkillCatalog(CANONICAL).load_all()}
    generated = {path.parent.name: path for path in (PLUGIN / "skills").glob("*/SKILL.md")}

    assert set(canonical) == EXPECTED_SKILLS
    assert set(generated) == EXPECTED_SKILLS
    for name, path in generated.items():
        assert path.read_text(encoding="utf-8") == canonical[name].instructions

    assert not tuple(PLUGIN.rglob("skill.toml"))
    assert "TestProduct" not in "".join(
        path.read_text(encoding="utf-8") for path in PLUGIN.rglob("*.md")
    )
