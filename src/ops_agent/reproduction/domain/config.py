"""Configuration value for the Reproduction module."""

from pydantic import BaseModel, ConfigDict, Field


class ReproductionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    adapter_name: str = Field(default="fake", min_length=1)
    tool_timeout_seconds: float = Field(default=5.0, gt=0)
    allowed_environment_kinds: tuple[str, ...] = (
        "sandbox",
        "test",
        "demo",
        "isolated",
        "fake",
    )
