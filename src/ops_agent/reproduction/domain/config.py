"""Configuration value for the Reproduction module."""

from pydantic import BaseModel, ConfigDict, Field


class ReproductionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = True
    adapter_name: str = Field(default="fake", min_length=1)
