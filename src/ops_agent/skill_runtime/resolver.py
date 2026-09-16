"""Product/version routing facade over the Skill Registry."""

from ops_agent.skill_runtime.loader import LoadedSkill
from ops_agent.skill_runtime.manifest import SkillType
from ops_agent.skill_runtime.registry import SkillRegistry


class SkillResolver:
    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def resolve(
        self,
        *,
        product: str,
        product_version: str,
        skill_type: SkillType,
    ) -> LoadedSkill:
        if skill_type is SkillType.BUILTIN_METHOD:
            raise ValueError("Product/version resolution cannot select BUILTIN_METHOD")
        return self._registry.find(
            product=product,
            product_version=product_version,
            skill_type=skill_type,
        )
