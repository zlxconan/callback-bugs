"""Deterministic runtime support ports."""

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class ClockPort(Protocol):
    """Clock boundary used to make deadlines and audit timestamps deterministic."""

    async def now(self) -> datetime: ...
