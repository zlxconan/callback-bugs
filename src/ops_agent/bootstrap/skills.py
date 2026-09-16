"""Composition root for installed Built-in and Product Plugin Skills."""

from dataclasses import dataclass
from pathlib import Path

from ops_agent.knowledge.adapters import RealKnowledgeEngine
from ops_agent.skill_runtime.config import SkillConfigurationError, SkillInstallationConfig
from ops_agent.skill_runtime.loader import LoadedSkill, SkillLoader
from ops_agent.skill_runtime.manifest import SkillType
from ops_agent.skill_runtime.registry import SkillRegistry
from ops_agent.skill_runtime.resolver import SkillResolver
from ops_agent.skill_runtime.validator import SkillValidationError, SkillValidator


@dataclass(frozen=True)
class SkillInstallation:
    """Objects assembled once at process startup and injected into Knowledge."""

    builtin_skills: tuple[LoadedSkill, ...]
    product_registry: SkillRegistry
    resolver: SkillResolver
    knowledge: RealKnowledgeEngine


def build_skill_installation(config: SkillInstallationConfig) -> SkillInstallation:
    """Discover one read-only built-in root and one read-only plugin root."""

    _require_directory(config.builtin_skills_path, "Built-in Skill")
    _require_directory(config.product_skills_path, "Product Skill Plugin")
    validator = SkillValidator(supported_core_api=config.supported_core_api)

    builtin_skills = SkillLoader(config.builtin_skills_path, validator).discover()
    if any(skill.manifest.skill_type is not SkillType.BUILTIN_METHOD for skill in builtin_skills):
        raise SkillValidationError("Built-in Skill root contains a non-BUILTIN_METHOD package")

    registry = SkillRegistry(SkillLoader(config.product_skills_path, validator))
    installed_plugins = registry.refresh()
    if any(skill.manifest.skill_type is SkillType.BUILTIN_METHOD for skill in installed_plugins):
        raise SkillValidationError("Product Skill root contains a BUILTIN_METHOD package")

    resolver = SkillResolver(registry)
    return SkillInstallation(
        builtin_skills=builtin_skills,
        product_registry=registry,
        resolver=resolver,
        knowledge=RealKnowledgeEngine(resolver),
    )


def _require_directory(path: Path, label: str) -> None:
    if not path.is_dir():
        raise SkillConfigurationError(f"{label} root does not exist or is not a directory: {path}")
