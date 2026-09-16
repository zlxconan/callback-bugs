"""Tool-port orchestration for one bounded reproduction experiment."""

import asyncio
from collections.abc import Awaitable

from pydantic import JsonValue

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    PreparedEnvironment,
)
from ops_agent.ports import ApiToolPort, BrowserToolPort, FaultInjectionToolPort, ShellToolPort
from ops_agent.reproduction.domain import ReproductionConfig, ReproductionTimeoutError
from ops_agent.reproduction.domain.environment_policy import ReproductionEnvironmentPolicy
from ops_agent.reproduction.service.cleanup_manager import CleanupManager


class ExperimentRunner:
    """Prepare, execute and clean one experiment through typed Tool Ports."""

    def __init__(
        self,
        *,
        browser: BrowserToolPort,
        api: ApiToolPort,
        shell: ShellToolPort,
        fault: FaultInjectionToolPort,
        config: ReproductionConfig,
        cleanup_manager: CleanupManager,
    ) -> None:
        self._browser = browser
        self._api = api
        self._shell = shell
        self._fault = fault
        self._config = config
        self._policy = ReproductionEnvironmentPolicy(config)
        self._cleanup = cleanup_manager
        self._requests: dict[str, ExperimentExecutionRequest] = {}

    async def prepare(self, plan: ExperimentPlan) -> PreparedEnvironment:
        self._policy.validate(plan)
        environment = PreparedEnvironment(
            **plan.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
            source="real-reproduction-engine",
            metadata={"environment_kind": plan.environment["kind"]},
            experiment_id=plan.experiment_id,
            environment_ref=(
                f"ENV-{plan.incident_id.removeprefix('INC-')}-"
                f"{plan.experiment_id.removeprefix('EXP-')}"
            ),
            ready=True,
            expires_at=None,
        )
        request = ExperimentExecutionRequest(
            **plan.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
            source="real-reproduction-engine",
            plan=plan,
            environment=environment,
        )
        self._cleanup.register(request)
        self._requests[plan.experiment_id] = request
        try:
            prepared = await self._invoke("api prepare", self._api.execute(request))
            self._require_success(prepared, "api prepare")
        except Exception:
            await self._cleanup.cleanup_execution(request)
            raise
        return environment

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self._validate_request(request)
        try:
            fault_result = await self._invoke("fault injection", self._fault.apply(request))
            self._require_success(fault_result, "fault injection")
            browser_result = await self._invoke("browser execution", self._browser.execute(request))
            self._require_success(browser_result, "browser execution")
            api_result = await self._invoke("api evidence collection", self._api.execute(request))
            self._require_success(api_result, "api evidence collection")
            return self._aggregate(request, (fault_result, browser_result, api_result))
        except Exception:
            await self._cleanup.cleanup_execution(request)
            raise

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        return await self._cleanup.cleanup(request)

    async def cleanup_experiment(self, experiment_id: str) -> CleanupResult | None:
        request = self._requests.get(experiment_id)
        if request is None:
            return None
        return await self._cleanup.cleanup_execution(request)

    async def _invoke(
        self,
        operation: str,
        awaitable: Awaitable[ExperimentResult],
    ) -> ExperimentResult:
        try:
            async with asyncio.timeout(self._config.tool_timeout_seconds):
                return await awaitable
        except TimeoutError as error:
            raise ReproductionTimeoutError(f"{operation} timed out") from error

    @staticmethod
    def _require_success(result: ExperimentResult, operation: str) -> None:
        if result.status is not ExperimentStatus.SUCCEEDED:
            raise RuntimeError(f"{operation} failed with status {result.status.value}")

    @staticmethod
    def _validate_request(request: ExperimentExecutionRequest) -> None:
        if request.plan.experiment_id != request.environment.experiment_id:
            raise RuntimeError("experiment plan and environment IDs do not match")
        if not request.environment.ready:
            raise RuntimeError("experiment environment is not ready")

    @staticmethod
    def _aggregate(
        request: ExperimentExecutionRequest,
        results: tuple[ExperimentResult, ...],
    ) -> ExperimentResult:
        outputs: dict[str, JsonValue] = {"environment_ref": request.environment.environment_ref}
        observations: list[str] = []
        evidence_ids: list[str] = []
        for result in results:
            outputs.update(result.outputs)
            observations.extend(result.observations)
            for evidence_id in result.evidence_ids:
                if evidence_id not in evidence_ids:
                    evidence_ids.append(evidence_id)
        database_count = outputs.get("database_record_count")
        if isinstance(database_count, int):
            outputs["orders_created"] = database_count
        return ExperimentResult(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="real-reproduction-engine",
            metadata={"tool_sequence": ["fault", "browser", "api"]},
            experiment_id=request.plan.experiment_id,
            status=ExperimentStatus.SUCCEEDED,
            started_at=request.timestamp,
            completed_at=request.timestamp,
            observations=observations,
            evidence_ids=sorted(evidence_ids),
            outputs=outputs,
        )
