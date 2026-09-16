"""Filesystem discovery and loading for Skill packages."""

import hashlib
import json
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue

from ops_agent.skill_runtime.manifest import SkillManifest
from ops_agent.skill_runtime.validator import SkillValidator


class LoadedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    manifest: SkillManifest
    package_root: Path
    entrypoint: Path
    digest: str
    content: JsonValue | str


class SkillLoader:
    """Discover manifests recursively without knowing any concrete product."""

    def __init__(self, root: Path, validator: SkillValidator | None = None) -> None:
        self._root = root
        self._validator = validator or SkillValidator()

    def discover(self) -> tuple[LoadedSkill, ...]:
        return tuple(self.load(path) for path in sorted(self._root.rglob("skill.toml")))

    def load(self, manifest_path: Path) -> LoadedSkill:
        manifest = SkillManifest.model_validate(
            tomllib.loads(manifest_path.read_text(encoding="utf-8"))
        )
        entrypoint = self._validator.validate_package(manifest, manifest_path.parent)
        raw = entrypoint.read_bytes()
        content: JsonValue | str
        if entrypoint.suffix.lower() == ".json":
            content = json.loads(raw)
        else:
            content = raw.decode("utf-8")
        return LoadedSkill(
            manifest=manifest,
            package_root=manifest_path.parent.resolve(),
            entrypoint=entrypoint,
            digest=f"sha256:{hashlib.sha256(raw).hexdigest()}",
            content=content,
        )
