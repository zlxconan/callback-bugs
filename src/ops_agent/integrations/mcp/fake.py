"""Deterministic low-level Tool Port fakes for MCP contract tests."""

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
