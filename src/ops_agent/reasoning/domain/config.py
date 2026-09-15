"""Configuration value for the Reasoning module."""

from pydantic import BaseModel, ConfigDict, Field


class ReasoningConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    adapter_name: str = Field(default="fake", min_length=1)
