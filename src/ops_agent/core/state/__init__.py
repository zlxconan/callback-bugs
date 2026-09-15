"""Core state persistence boundary."""

from ops_agent.core.state.memory import InMemoryStateRepository
from ops_agent.ports import StateRepositoryPort

__all__ = ["InMemoryStateRepository", "StateRepositoryPort"]
