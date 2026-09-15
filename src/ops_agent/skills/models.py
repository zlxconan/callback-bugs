"""Canonical Skill metadata and build artifacts."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class SkillTarget(StrEnum):
    CODEX = "codex"
    CODEBUDDY = "codebuddy"
    LOCAL = "local"


class CanonicalSkill(BaseModel):
    """Platform-neutral Skill metadata plus its single instruction source."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    description: str = Field(min_length=1)
    input_contracts: tuple[str, ...] = Field(min_length=1)
    output_contracts: tuple[str, ...] = Field(min_length=1)
    mcp_tools: tuple[str, ...] = ()
    source_directory: Path
    instructions_path: Path
    instructions: str = Field(min_length=1)


class BuiltSkillArtifact(BaseModel):
    """Files emitted for one reserved Agent Host target."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str
    target: SkillTarget
    output_directory: Path
    instructions_path: Path
    manifest_path: Path
