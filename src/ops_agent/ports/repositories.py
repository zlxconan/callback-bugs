"""Persistence ports owned by the core runtime."""

from typing import Protocol, runtime_checkable

from ops_agent.contracts import AuditEvent, IncidentQuery, IncidentState


@runtime_checkable
class StateRepositoryPort(Protocol):
    """Persistence boundary for state snapshots and audit events."""

    async def create(self, state: IncidentState) -> IncidentState: ...

    async def get(self, query: IncidentQuery) -> IncidentState | None: ...

    async def save(self, state: IncidentState) -> IncidentState: ...

    async def list_events(self, query: IncidentQuery) -> tuple[AuditEvent, ...]: ...
