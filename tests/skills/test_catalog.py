from pathlib import Path

from ops_agent import contracts
from ops_agent.skill_runtime import SkillType
from ops_agent.skills import SkillCatalog

SKILLS_ROOT = Path(__file__).parents[2] / "skills" / "builtin"
EXPECTED_SKILLS = {
    "incident-analysis",
    "hypothesis-generation",
    "evidence-planning",
    "reflection",
    "reproduction-planning",
    "rca-report",
}


def test_canonical_skill_metadata_and_references_are_valid(mcp_tool_names: set[str]) -> None:
    catalog = SkillCatalog(SKILLS_ROOT)

    skills = catalog.load_all()
    catalog.validate(skills, contracts=contracts, mcp_tool_names=mcp_tool_names)

    assert {skill.name for skill in skills} == EXPECTED_SKILLS
    assert all(skill.version == "1.0.0" for skill in skills)
    assert all(skill.skill_type is SkillType.BUILTIN_METHOD for skill in skills)
    assert all(skill.input_contracts for skill in skills)
    assert all(skill.output_contracts for skill in skills)
    assert all(skill.instructions_path.name == "SKILL.md" for skill in skills)


def test_each_skill_contains_required_operational_sections() -> None:
    required = {
        "## Skill 目标",
        "## 适用场景",
        "## 输入 Contract",
        "## 输出 Contract",
        "## 操作步骤",
        "## 可调用 MCP",
        "## 禁止行为",
        "## 退出条件",
        "## 失败处理",
        "## 示例",
    }

    for skill in SkillCatalog(SKILLS_ROOT).load_all():
        assert required.issubset(set(skill.instructions.splitlines()))
