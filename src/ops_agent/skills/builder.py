"""Minimal builder abstraction for platform-specific Skill packaging."""

from pathlib import Path
from typing import Protocol

from ops_agent.skills.models import BuiltSkillArtifact, CanonicalSkill, SkillTarget


class SkillBuilder(Protocol):
    def build(
        self,
        skill: CanonicalSkill,
        *,
        target: SkillTarget,
        destination: Path,
    ) -> BuiltSkillArtifact: ...


class CanonicalSkillBuilder:
    """Emit the canonical body unchanged; target customization is intentionally deferred."""

    def build(
        self,
        skill: CanonicalSkill,
        *,
        target: SkillTarget,
        destination: Path,
    ) -> BuiltSkillArtifact:
        output_directory = destination / target.value / skill.name
        output_directory.mkdir(parents=True, exist_ok=True)
        instructions_path = output_directory / "SKILL.md"
        manifest_path = output_directory / "skill.toml"
        instructions_path.write_text(skill.instructions, encoding="utf-8")
        manifest_path.write_text(self._manifest(skill, target), encoding="utf-8")
        return BuiltSkillArtifact(
            name=skill.name,
            target=target,
            output_directory=output_directory,
            instructions_path=instructions_path,
            manifest_path=manifest_path,
        )

    @staticmethod
    def _manifest(skill: CanonicalSkill, target: SkillTarget) -> str:
        def array(values: tuple[str, ...]) -> str:
            return "[" + ", ".join(f'"{value}"' for value in values) + "]"

        return "\n".join(
            (
                f'name = "{skill.name}"',
                f'version = "{skill.version}"',
                f'description = "{skill.description}"',
                f'target = "{target.value}"',
                f"input_contracts = {array(skill.input_contracts)}",
                f"output_contracts = {array(skill.output_contracts)}",
                f"mcp_tools = {array(skill.mcp_tools)}",
                "",
            )
        )
