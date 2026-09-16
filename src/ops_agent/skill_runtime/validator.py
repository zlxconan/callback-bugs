"""Manifest, compatibility, package-boundary, and duplicate validation."""

from pathlib import Path

from ops_agent.skill_runtime.manifest import SkillManifest, SkillType


class SkillValidationError(ValueError):
    """An installed package is unsafe or incompatible with this Core."""


class SkillValidator:
    def __init__(self, *, supported_core_api: str = "1.0") -> None:
        self._supported_core_api = supported_core_api

    def validate_package(self, manifest: SkillManifest, package_root: Path) -> Path:
        if manifest.core_api != self._supported_core_api:
            raise SkillValidationError(
                f"Skill {manifest.name} requires Core API {manifest.core_api}; "
                f"supported is {self._supported_core_api}"
            )
        root = package_root.resolve()
        entrypoint = (root / manifest.entrypoint).resolve()
        try:
            entrypoint.relative_to(root)
        except ValueError as error:
            raise SkillValidationError("Skill entrypoint escapes its package") from error
        if not entrypoint.is_file():
            raise SkillValidationError(f"Skill entrypoint does not exist: {entrypoint}")
        if manifest.skill_type in {SkillType.PRODUCT, SkillType.TROUBLESHOOTING}:
            if entrypoint.suffix.lower() != ".json":
                raise SkillValidationError("Product Plugin entrypoint must be JSON")
        return entrypoint

    @staticmethod
    def validate_unique(keys: list[tuple[SkillType, str, str]]) -> None:
        if len(keys) != len(set(keys)):
            raise SkillValidationError("Duplicate Skill type/product/version registration")
