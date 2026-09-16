"""Real ReproductionPort orchestration over replaceable Tool Ports."""

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentResult,
    ExperimentVerificationRequest,
    PreparedEnvironment,
    VerificationResult,
)
from ops_agent.ports import ApiToolPort, BrowserToolPort, FaultInjectionToolPort, ShellToolPort
from ops_agent.reproduction.domain import ReproductionConfig
from ops_agent.reproduction.service.cleanup_manager import CleanupManager
from ops_agent.reproduction.service.experiment_runner import ExperimentRunner
from ops_agent.reproduction.service.verifier import DeterministicExperimentVerifier


class RealReproductionEngine:
    """Coordinate an approved experiment without depending on concrete tool SDKs."""

    def __init__(
        self,
        *,
        browser: BrowserToolPort,
        api: ApiToolPort,
        shell: ShellToolPort,
        fault: FaultInjectionToolPort,
        config: ReproductionConfig | None = None,
    ) -> None:
        resolved_config = config or ReproductionConfig(adapter_name="real")
        self.cleanup_manager = CleanupManager(
            fault,
            timeout_seconds=resolved_config.tool_timeout_seconds,
        )
        self._runner = ExperimentRunner(
            browser=browser,
            api=api,
            shell=shell,
            fault=fault,
            config=resolved_config,
            cleanup_manager=self.cleanup_manager,
        )
        self._verifier = DeterministicExperimentVerifier()

    async def prepare(self, plan: ExperimentPlan) -> PreparedEnvironment:
        return await self._runner.prepare(plan)

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        return await self._runner.execute(request)

    async def verify(self, request: ExperimentVerificationRequest) -> VerificationResult:
        try:
            return self._verifier.verify(request)
        finally:
            await self._runner.cleanup_experiment(request.plan.experiment_id)

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        return await self._runner.cleanup(request)
