"""Loader and referential-integrity validator for Canonical Skills."""

import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from ops_agent.skill_runtime import SkillType
from ops_agent.skills.models import CanonicalSkill


class SkillCatalogError(ValueError):
    """Invalid canonical metadata or reference."""


class SkillCatalog:
    def __init__(self, root: Path) -> None:
        self._root = root

    def load_all(self) -> tuple[CanonicalSkill, ...]:
        return tuple(self._load(path) for path in sorted(self._root.glob("*/skill.toml")))

    def get(self, name: str) -> CanonicalSkill:
        path = self._root / name / "skill.toml"
        if not path.is_file():
            raise SkillCatalogError(f"Canonical Skill not found: {name}")
        return self._load(path)

    def validate(
        self,
        skills: tuple[CanonicalSkill, ...],
        *,
        contracts: ModuleType,
        mcp_tool_names: set[str],
    ) -> None:
        names: set[str] = set()
        for skill in skills:
            if skill.name in names:
                raise SkillCatalogError(f"Duplicate Skill name: {skill.name}")
            names.add(skill.name)
            if skill.source_directory.name != skill.name:
                raise SkillCatalogError(f"Skill directory/name mismatch: {skill.name}")
            if skill.skill_type is not SkillType.BUILTIN_METHOD:
                raise SkillCatalogError(
                    f"Canonical catalog only accepts BUILTIN_METHOD: {skill.name}"
                )
            for contract_name in (*skill.input_contracts, *skill.output_contracts):
                contract = getattr(contracts, contract_name, None)
                if not isinstance(contract, type) or not issubclass(contract, BaseModel):
                    raise SkillCatalogError(f"Unknown Contract in {skill.name}: {contract_name}")
            unknown_tools = set(skill.mcp_tools) - mcp_tool_names
            if unknown_tools:
                raise SkillCatalogError(
                    f"Unknown MCP tools in {skill.name}: {sorted(unknown_tools)}"
                )

    @staticmethod
    def _load(manifest_path: Path) -> CanonicalSkill:
        metadata: dict[str, Any] = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        entrypoint = metadata.get("entrypoint", "SKILL.md")
        if not isinstance(entrypoint, str):
            raise SkillCatalogError(f"Invalid entrypoint: {manifest_path}")
        instructions_path = manifest_path.parent / entrypoint
        if not instructions_path.is_file():
            raise SkillCatalogError(f"Missing instructions: {instructions_path}")
        return CanonicalSkill.model_validate(
            {
                **metadata,
                "source_directory": manifest_path.parent,
                "instructions_path": instructions_path,
                "instructions": instructions_path.read_text(encoding="utf-8"),
            }
        )
