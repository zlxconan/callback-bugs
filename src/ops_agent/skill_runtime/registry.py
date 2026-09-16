"""In-process lifecycle and index for discovered Skill packages."""

from ops_agent.skill_runtime.loader import LoadedSkill, SkillLoader
from ops_agent.skill_runtime.manifest import SkillType
from ops_agent.skill_runtime.validator import SkillValidator


class SkillNotInstalledError(LookupError):
    """No installed package matches the requested product/version/type."""


class SkillProductNotInstalledError(SkillNotInstalledError):
    """No installed package of the requested type declares the product."""


class SkillVersionNotInstalledError(SkillNotInstalledError):
    """The product is installed, but not for the requested product version."""


class SkillRegistry:
    def __init__(self, loader: SkillLoader) -> None:
        self._loader = loader
        self._skills: dict[str, LoadedSkill] = {}

    def refresh(self) -> tuple[LoadedSkill, ...]:
        skills = self._loader.discover()
        SkillValidator.validate_registrations([skill.manifest for skill in skills])
        self._skills = {skill.manifest.name: skill for skill in skills}
        return skills

    def install(self, skill: LoadedSkill) -> None:
        candidate = [*self._skills.values(), skill]
        SkillValidator.validate_registrations([item.manifest for item in candidate])
        self._skills[skill.manifest.name] = skill

    def uninstall(self, name: str) -> LoadedSkill:
        try:
            return self._skills.pop(name)
        except KeyError as error:
            raise SkillNotInstalledError(f"Skill is not installed: {name}") from error

    def list(self, *, skill_type: SkillType | None = None) -> tuple[LoadedSkill, ...]:
        values = tuple(self._skills.values())
        if skill_type is None:
            return values
        return tuple(item for item in values if item.manifest.skill_type is skill_type)

    def find(
        self,
        *,
        product: str,
        product_version: str,
        skill_type: SkillType,
    ) -> LoadedSkill:
        product_skills = [
            skill
            for skill in self._skills.values()
            if skill.manifest.skill_type is skill_type and skill.manifest.product == product
        ]
        if not product_skills:
            raise SkillProductNotInstalledError(
                f"No installed {skill_type.value} Skill for product {product} "
                f"and version {product_version}"
            )
        for skill in product_skills:
            if product_version in skill.manifest.product_versions:
                return skill
        available = sorted(
            version for skill in product_skills for version in skill.manifest.product_versions
        )
        raise SkillVersionNotInstalledError(
            f"No installed {skill_type.value} Skill for {product} {product_version}; "
            f"available versions: {available}"
        )
