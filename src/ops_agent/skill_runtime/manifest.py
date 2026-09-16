"""Provider-neutral manifests for built-in and installable Incident Skills."""

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SkillType(StrEnum):
    BUILTIN_METHOD = "BUILTIN_METHOD"
    PRODUCT = "PRODUCT"
    TROUBLESHOOTING = "TROUBLESHOOTING"


class SkillManifest(BaseModel):
    """Metadata shared by Core methods and external Product Plugin packages."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    skill_type: SkillType
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    entrypoint: str = Field(min_length=1)
    core_api: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    product: str | None = None
    product_versions: tuple[str, ...] = ()
    description: str | None = None
    input_contracts: tuple[str, ...] = ()
    output_contracts: tuple[str, ...] = ()
    mcp_tools: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_type_scope_and_entrypoint(self) -> "SkillManifest":
        path = PurePosixPath(self.entrypoint)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("entrypoint must stay inside the Skill package")
        if self.skill_type is SkillType.BUILTIN_METHOD:
            if self.product is not None or self.product_versions:
                raise ValueError("BUILTIN_METHOD cannot declare product scope")
        elif self.product is None or not self.product_versions:
            raise ValueError("Product Plugin Skill requires product and product_versions")
        return self
