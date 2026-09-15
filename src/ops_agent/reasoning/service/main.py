"""In-process Reasoning service entry point."""

from collections.abc import Awaitable
from typing import TypeVar

from ops_agent.contracts import (
    EvidencePlan,
    EvidencePlanningRequest,
    ExperimentPlan,
    ExperimentPlanningRequest,
    HypothesisGenerationRequest,
    HypothesisSet,
    ModuleHealth,
    ReflectionRequest,
    ReflectionResult,
    RootCauseAssessment,
    RootCauseVerificationRequest,
)
from ops_agent.reasoning.domain import (
    ReasoningConfig,
    ReasoningDependencyError,
    ReasoningDisabledError,
    ReasoningError,
)
from ops_agent.reasoning.ports import ReasoningPort

T = TypeVar("T")


class ReasoningService:
    """Stable application boundary delegating work to a Reasoning adapter."""

    def __init__(self, adapter: ReasoningPort, config: ReasoningConfig) -> None:
        self._adapter = adapter
        self._config = config

    async def health(self) -> ModuleHealth:
        return ModuleHealth(
            module="reasoning",
            status="ok" if self._config.enabled else "disabled",
            adapter=self._config.adapter_name,
        )

    async def generate_hypotheses(self, request: HypothesisGenerationRequest) -> HypothesisSet:
        self._ensure_enabled()
        return await self._execute(self._adapter.generate_hypotheses(request))

    async def plan_evidence(self, request: EvidencePlanningRequest) -> EvidencePlan:
        self._ensure_enabled()
        return await self._execute(self._adapter.plan_evidence(request))

    async def reflect(self, request: ReflectionRequest) -> ReflectionResult:
        self._ensure_enabled()
        return await self._execute(self._adapter.reflect(request))

    async def verify_root_cause(self, request: RootCauseVerificationRequest) -> RootCauseAssessment:
        self._ensure_enabled()
        return await self._execute(self._adapter.verify_root_cause(request))

    async def plan_experiment(self, request: ExperimentPlanningRequest) -> ExperimentPlan:
        self._ensure_enabled()
        return await self._execute(self._adapter.plan_experiment(request))

    def _ensure_enabled(self) -> None:
        if not self._config.enabled:
            raise ReasoningDisabledError("Reasoning module is disabled")

    @staticmethod
    async def _execute(operation: Awaitable[T]) -> T:
        try:
            return await operation
        except ReasoningError:
            raise
        except Exception as error:
            raise ReasoningDependencyError(str(error)) from error
