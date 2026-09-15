"""Public contracts for service health endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ServiceStatus(BaseModel):
    """Status returned by a service probe."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "ready"]


class ModuleHealth(BaseModel):
    """Health of one in-process Engine and its configured adapter boundary."""

    model_config = ConfigDict(extra="forbid")

    module: Literal["knowledge", "reasoning", "investigation", "reproduction"]
    status: Literal["ok", "disabled"]
    adapter: str
