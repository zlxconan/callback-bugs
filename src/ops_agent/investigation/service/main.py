"""In-process Investigation service entry point."""

from collections.abc import Awaitable
from typing import TypeVar

from ops_agent.contracts import Evidence, EvidenceBatch, EvidencePlan, EvidenceRequest, ModuleHealth
from ops_agent.investigation.domain import (
    InvestigationConfig,
    InvestigationDependencyError,
    InvestigationDisabledError,
    InvestigationError,
)
from ops_agent.investigation.ports import InvestigationPort

T = TypeVar("T")


class InvestigationService:
    """Stable application boundary delegating work to an Investigation adapter."""

    def __init__(self, adapter: InvestigationPort, config: InvestigationConfig) -> None:
        self._adapter = adapter
        self._config = config

    async def health(self) -> ModuleHealth:
        return ModuleHealth(
            module="investigation",
            status="ok" if self._config.enabled else "disabled",
            adapter=self._config.adapter_name,
        )

    async def collect(self, request: EvidenceRequest) -> Evidence:
        self._ensure_enabled()
        return await self._execute(self._adapter.collect(request))

    async def collect_batch(self, plan: EvidencePlan) -> EvidenceBatch:
        self._ensure_enabled()
        return await self._execute(self._adapter.collect_batch(plan))

    def _ensure_enabled(self) -> None:
        if not self._config.enabled:
            raise InvestigationDisabledError("Investigation module is disabled")

    @staticmethod
    async def _execute(operation: Awaitable[T]) -> T:
        try:
            return await operation
        except InvestigationError:
            raise
        except Exception as error:
            raise InvestigationDependencyError(str(error)) from error
