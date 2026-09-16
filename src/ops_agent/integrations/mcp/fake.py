"""Deterministic low-level Tool Port fakes for MCP and Engine contract tests."""

import asyncio

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    Evidence,
    EvidenceAcquisitionStatus,
    EvidenceRequest,
    ExperimentExecutionRequest,
    ExperimentResult,
    ExperimentStatus,
    RawReference,
)


class FakeEvidenceTool:
    """One Fake compatible with every collect-shaped evidence Tool Port."""

    def __init__(self, source: str = "fake-evidence-tool") -> None:
        self._source = source

    async def collect(self, request: EvidenceRequest) -> Evidence:
        evidence_id = f"E-MCP-{self._source.upper().replace('_', '-')}"
        return Evidence(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source=self._source,
            metadata={"fake": True},
            evidence_id=evidence_id,
            evidence_type=request.evidence_type,
            raw_reference=RawReference(uri=f"fake://mcp/{self._source}/{request.query}"),
            structured_value={"query": request.query, "fake": True},
            observed_at=request.timestamp,
            supports_hypotheses=request.hypothesis_ids,
            contradicts_hypotheses=[],
            confidence=1.0,
            acquisition_status=EvidenceAcquisitionStatus.ACQUIRED,
        )


class FakeExecutionTool:
    """Side-effect-free Fake for browser, API, Shell, and fault Tool Ports."""

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        return self._result(request, "execute")

    async def apply(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        return self._result(request, "fault-inject")

    async def rollback(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        return CleanupResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="fake-execution-tool",
            metadata={"fake": True},
            experiment_id=request.experiment_id,
            environment_ref=request.environment_ref,
            cleaned=True,
            observations=["Fake rollback completed."],
        )

    @staticmethod
    def _result(request: ExperimentExecutionRequest, action: str) -> ExperimentResult:
        return ExperimentResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="fake-execution-tool",
            metadata={"fake": True},
            experiment_id=request.plan.experiment_id,
            status=ExperimentStatus.SUCCEEDED,
            started_at=request.timestamp,
            completed_at=request.timestamp,
            observations=[f"Fake MCP action completed: {action}."],
            evidence_ids=[],
            outputs={"action": action, "fake": True},
        )


class FakeBrowserTool:
    """BrowserToolPort fake for the timeout/retry duplicate-create scenario."""

    def __init__(
        self,
        *,
        fail: bool = False,
        delay_seconds: float = 0.0,
    ) -> None:
        self._fail = fail
        self._delay_seconds = delay_seconds
        self.execute_calls = 0

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self.execute_calls += 1
        if self._delay_seconds:
            await asyncio.sleep(self._delay_seconds)
        if self._fail:
            raise RuntimeError("configured Fake browser failure")
        return _scenario_result(
            request,
            source="fake-browser-tool",
            observations=[
                "The first create request completed on the backend.",
                "The client timed out and retried once.",
            ],
            evidence_ids=["E-1", "E-2"],
            outputs={
                "business_id": "BIZ-001",
                "request_count": 2,
                "first_backend_status": "success",
                "retry_detected": True,
                "request_ids": ["HTTP-REQ-1", "HTTP-REQ-2"],
                "trace_id": "TRACE-001",
                "page_events": ["submit", "timeout", "retry", "success"],
            },
        )


class FakeApiTool:
    """ApiToolPort fake that resets, prepares and then inspects the test database."""

    def __init__(
        self,
        *,
        fail_on_calls: set[int] | None = None,
        database_record_count: int = 2,
    ) -> None:
        self._fail_on_calls = fail_on_calls or set()
        self._database_record_count = database_record_count
        self.execute_calls = 0

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self.execute_calls += 1
        if self.execute_calls in self._fail_on_calls:
            raise RuntimeError("configured Fake API failure")
        if self.execute_calls == 1:
            return _scenario_result(
                request,
                source="fake-api-tool",
                observations=["Test database reset and account data prepared."],
                evidence_ids=[],
                outputs={"database_reset": True, "account_prepared": True},
            )
        return _scenario_result(
            request,
            source="fake-api-tool",
            observations=["Test database contains the observed order records."],
            evidence_ids=["E-4"],
            outputs={
                "database_record_count": self._database_record_count,
                "order_ids": [f"ORDER-{index + 1}" for index in range(self._database_record_count)],
            },
        )


class FakeShellTool:
    """ShellToolPort fake retained as an injected but unused MVP extension point."""

    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self.execute_calls += 1
        return _scenario_result(
            request,
            source="fake-shell-tool",
            observations=["No shell action was required."],
            evidence_ids=[],
            outputs={"shell_action": "none"},
        )


class FakeFaultInjectionTool:
    """FaultInjectionToolPort fake with observable apply and idempotent rollback calls."""

    def __init__(
        self,
        *,
        fail_apply: bool = False,
        fail_rollback: bool = False,
    ) -> None:
        self._fail_apply = fail_apply
        self._fail_rollback = fail_rollback
        self.apply_calls = 0
        self.rollback_calls = 0

    async def apply(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self.apply_calls += 1
        if self._fail_apply:
            raise RuntimeError("configured Fake fault injection failure")
        return _scenario_result(
            request,
            source="fake-fault-injection-tool",
            observations=["The first response was delayed beyond the client timeout."],
            evidence_ids=["E-3"],
            outputs={"first_response_delay_ms": 80, "client_timeout_ms": 20},
        )

    async def rollback(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        self.rollback_calls += 1
        if self._fail_rollback:
            raise RuntimeError("configured Fake rollback failure")
        return CleanupResult(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="fake-fault-injection-tool",
            metadata={"fake": True},
            experiment_id=request.experiment_id,
            environment_ref=request.environment_ref,
            cleaned=True,
            observations=["Fake fault injection rolled back."],
        )


def _scenario_result(
    request: ExperimentExecutionRequest,
    *,
    source: str,
    observations: list[str],
    evidence_ids: list[str],
    outputs: dict[str, object],
) -> ExperimentResult:
    return ExperimentResult.model_validate(
        {
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            "source": source,
            "metadata": {"fake": True},
            "experiment_id": request.plan.experiment_id,
            "status": ExperimentStatus.SUCCEEDED,
            "started_at": request.timestamp,
            "completed_at": request.timestamp,
            "observations": observations,
            "evidence_ids": evidence_ids,
            "outputs": outputs,
        }
    )
