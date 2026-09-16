"""Deployment configuration for built-in and Product Plugin Skill roots."""

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

BUILTIN_SKILLS_PATH_ENV = "OPS_AGENT_BUILTIN_SKILLS_PATH"
PRODUCT_SKILLS_PATH_ENV = "OPS_AGENT_PRODUCT_SKILLS_PATH"
SKILL_CORE_API_ENV = "OPS_AGENT_SKILL_CORE_API"


class SkillConfigurationError(ValueError):
    """Skill installation paths are missing or unusable."""


class SkillInstallationConfig(BaseModel):
    """Single-root, read-only discovery configuration used by the composition root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    builtin_skills_path: Path = Path("skills/builtin")
    product_skills_path: Path
    supported_core_api: str = Field(default="1.0", pattern=r"^\d+\.\d+$")

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> "SkillInstallationConfig":
        values = os.environ if environ is None else environ
        product_root = values.get(PRODUCT_SKILLS_PATH_ENV)
        if not product_root:
            raise SkillConfigurationError(
                f"{PRODUCT_SKILLS_PATH_ENV} must point to the mounted Product Skill root"
            )
        return cls(
            builtin_skills_path=Path(values.get(BUILTIN_SKILLS_PATH_ENV, "skills/builtin")),
            product_skills_path=Path(product_root),
            supported_core_api=values.get(SKILL_CORE_API_ENV, "1.0"),
        )
