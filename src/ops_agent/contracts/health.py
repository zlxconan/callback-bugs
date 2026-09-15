"""Public contracts for service health endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ServiceStatus(BaseModel):
    """Status returned by a service probe."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "ready"]
