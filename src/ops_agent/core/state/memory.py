"""Deterministic in-memory implementation of the state repository port."""

from ops_agent.contracts import AuditEvent, IncidentQuery, IncidentState


class InMemoryStateRepository:
    """Process-local repository for tests, examples, and Fake E2E runs."""

    def __init__(self) -> None:
        self._states: dict[str, IncidentState] = {}
        self._events: dict[str, list[AuditEvent]] = {}

    async def create(self, state: IncidentState) -> IncidentState:
        if state.incident_id in self._states:
            raise ValueError(f"incident already exists: {state.incident_id}")
        self._states[state.incident_id] = state.model_copy(deep=True)
        self._events[state.incident_id] = []
        return state.model_copy(deep=True)

    async def get(self, query: IncidentQuery) -> IncidentState | None:
        state = self._states.get(query.incident_id)
        return state.model_copy(deep=True) if state is not None else None

    async def save(self, state: IncidentState) -> IncidentState:
        if state.incident_id not in self._states:
            raise KeyError(f"incident does not exist: {state.incident_id}")
        self._states[state.incident_id] = state.model_copy(deep=True)
        return state.model_copy(deep=True)

    async def list_events(self, query: IncidentQuery) -> tuple[AuditEvent, ...]:
        return tuple(
            event.model_copy(deep=True) for event in self._events.get(query.incident_id, [])
        )

    async def append_event(self, event: AuditEvent) -> AuditEvent:
        if event.incident_id not in self._states:
            raise KeyError(f"incident does not exist: {event.incident_id}")
        self._events.setdefault(event.incident_id, []).append(event.model_copy(deep=True))
        return event.model_copy(deep=True)
