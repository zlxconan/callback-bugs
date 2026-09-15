"""In-process Reproduction service entry point."""

from collections.abc import Awaitable
from typing import TypeVar

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentResult,
    ExperimentVerificationRequest,
    ModuleHealth,
    PreparedEnvironment,
    VerificationResult,
)
from ops_agent.reproduction.domain import (
    ReproductionConfig,
    ReproductionDependencyError,
    ReproductionDisabledError,
    ReproductionError,
)
from ops_agent.reproduction.ports import ReproductionPort

T = TypeVar("T")


class ReproductionService:
    """Stable application boundary delegating work to a Reproduction adapter."""

    def __init__(self, adapter: ReproductionPort, config: ReproductionConfig) -> None:
        self._adapter = adapter
        self._config = config

    async def health(self) -> ModuleHealth:
        return ModuleHealth(
            module="reproduction",
            status="ok" if self._config.enabled else "disabled",
            adapter=self._config.adapter_name,
        )

    async def prepare(self, plan: ExperimentPlan) -> PreparedEnvironment:
        self._ensure_enabled()
        return await self._execute(self._adapter.prepare(plan))

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self._ensure_enabled()
        return await self._execute(self._adapter.execute(request))

    async def verify(self, request: ExperimentVerificationRequest) -> VerificationResult:
        self._ensure_enabled()
        return await self._execute(self._adapter.verify(request))

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        self._ensure_enabled()
        return await self._execute(self._adapter.cleanup(request))

    def _ensure_enabled(self) -> None:
        if not self._config.enabled:
            raise ReproductionDisabledError("Reproduction module is disabled")

    @staticmethod
    async def _execute(operation: Awaitable[T]) -> T:
        try:
            return await operation
        except ReproductionError:
            raise
        except Exception as error:
            raise ReproductionDependencyError(str(error)) from error
