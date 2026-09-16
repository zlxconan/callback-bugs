"""In-process lifecycle and index for discovered Skill packages."""

from ops_agent.skill_runtime.loader import LoadedSkill, SkillLoader
from ops_agent.skill_runtime.manifest import SkillType
from ops_agent.skill_runtime.validator import SkillValidator


class SkillNotInstalledError(LookupError):
    """No installed package matches the requested product/version/type."""


class SkillRegistry:
    def __init__(self, loader: SkillLoader) -> None:
        self._loader = loader
        self._skills: dict[str, LoadedSkill] = {}

    def refresh(self) -> tuple[LoadedSkill, ...]:
        skills = self._loader.discover()
        keys = [self._scope_key(skill) for skill in skills]
        SkillValidator.validate_unique(keys)
        self._skills = {skill.manifest.name: skill for skill in skills}
        return skills

    def install(self, skill: LoadedSkill) -> None:
        candidate = [*self._skills.values(), skill]
        SkillValidator.validate_unique([self._scope_key(item) for item in candidate])
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
        for skill in self._skills.values():
            manifest = skill.manifest
            if (
                manifest.skill_type is skill_type
                and manifest.product == product
                and product_version in manifest.product_versions
            ):
                return skill
        raise SkillNotInstalledError(
            f"No installed {skill_type.value} Skill for {product} {product_version}"
        )

    @staticmethod
    def _scope_key(skill: LoadedSkill) -> tuple[SkillType, str, str]:
        manifest = skill.manifest
        if manifest.skill_type is SkillType.BUILTIN_METHOD:
            return (manifest.skill_type, manifest.name, manifest.version)
        assert manifest.product is not None
        return (
            manifest.skill_type,
            manifest.product,
            ",".join(manifest.product_versions),
        )
