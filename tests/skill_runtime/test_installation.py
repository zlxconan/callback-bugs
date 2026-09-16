import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ops_agent.bootstrap.skills import build_skill_installation
from ops_agent.ports import KnowledgePort
from ops_agent.skill_runtime import (
    SkillConfigurationError,
    SkillInstallationConfig,
    SkillType,
    verify_skill_installation,
)

REPOSITORY_ROOT = Path(__file__).parents[2]
BUILTIN_ROOT = REPOSITORY_ROOT / "skills" / "builtin"
PRODUCT_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "product-skills"
EXPECTED_BUILTINS = {
    "incident-analysis",
    "hypothesis-generation",
    "evidence-planning",
    "reflection",
    "reproduction-planning",
    "rca-report",
}


def test_installation_config_uses_current_paths_and_requires_product_root() -> None:
    config = SkillInstallationConfig.from_env(
        {
            "OPS_AGENT_BUILTIN_SKILLS_PATH": str(BUILTIN_ROOT),
            "OPS_AGENT_PRODUCT_SKILLS_PATH": str(PRODUCT_ROOT),
        }
    )

    assert config.builtin_skills_path == BUILTIN_ROOT
    assert config.product_skills_path == PRODUCT_ROOT
    assert config.supported_core_api == "1.0"

    with pytest.raises(SkillConfigurationError, match="OPS_AGENT_PRODUCT_SKILLS_PATH"):
        SkillInstallationConfig.from_env({"OPS_AGENT_BUILTIN_SKILLS_PATH": str(BUILTIN_ROOT)})


def test_composition_root_discovers_builtins_and_injects_product_registry() -> None:
    installation = build_skill_installation(
        SkillInstallationConfig(
            builtin_skills_path=BUILTIN_ROOT,
            product_skills_path=PRODUCT_ROOT,
        )
    )

    assert {skill.manifest.name for skill in installation.builtin_skills} == EXPECTED_BUILTINS
    assert all(
        skill.manifest.skill_type is SkillType.BUILTIN_METHOD
        for skill in installation.builtin_skills
    )
    assert len(installation.product_registry.list(skill_type=SkillType.PRODUCT)) == 2
    assert len(installation.product_registry.list(skill_type=SkillType.TROUBLESHOOTING)) == 1
    assert isinstance(installation.knowledge, KnowledgePort)


@pytest.mark.asyncio
async def test_preflight_verifies_test_product_without_writing_plugin_files() -> None:
    config = SkillInstallationConfig(
        builtin_skills_path=BUILTIN_ROOT,
        product_skills_path=PRODUCT_ROOT,
    )
    before = {path: path.read_bytes() for path in PRODUCT_ROOT.rglob("*") if path.is_file()}

    result = await verify_skill_installation(
        config,
        product="TestProduct",
        product_version="1.0",
        comparison_version="2.0",
    )

    assert result.ok
    assert set(result.builtin_skill_names) == EXPECTED_BUILTINS
    assert result.product_skill_name == "test-product-product-v1"
    assert result.troubleshooting_skill_name == "test-product-troubleshooting-v1"
    assert result.comparison_skill_name == "test-product-product-v2"
    assert result.knowledge_fact_count >= 3
    assert result.missing_product_error_verified
    assert result.tool_skills_excluded
    assert before == {path: path.read_bytes() for path in PRODUCT_ROOT.rglob("*") if path.is_file()}


def test_preflight_script_returns_machine_readable_success() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "OPS_AGENT_BUILTIN_SKILLS_PATH": str(BUILTIN_ROOT),
            "OPS_AGENT_PRODUCT_SKILLS_PATH": str(PRODUCT_ROOT),
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts" / "verify_skill_installation.py"),
            "--product",
            "TestProduct",
            "--version",
            "1.0",
            "--comparison-version",
            "2.0",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["ok"] is True
    assert result["product_skill_name"] == "test-product-product-v1"
