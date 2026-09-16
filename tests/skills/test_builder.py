from pathlib import Path

import pytest

from ops_agent.skills import CanonicalSkillBuilder, SkillCatalog, SkillTarget

SKILLS_ROOT = Path(__file__).parents[2] / "skills" / "builtin"


@pytest.mark.parametrize("target", list(SkillTarget))
def test_build_smoke_for_every_reserved_target(tmp_path: Path, target: SkillTarget) -> None:
    skill = SkillCatalog(SKILLS_ROOT).get("evidence-planning")
    artifact = CanonicalSkillBuilder().build(skill, target=target, destination=tmp_path)

    assert artifact.target is target
    assert artifact.instructions_path.is_file()
    assert artifact.manifest_path.is_file()
    assert "Missing Evidence" in artifact.instructions_path.read_text(encoding="utf-8")
    assert skill.name in artifact.manifest_path.read_text(encoding="utf-8")
