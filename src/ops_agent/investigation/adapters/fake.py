"""Deterministic InvestigationPort implementation for the MVP Fake case."""

from pydantic import JsonValue

from ops_agent.contracts import (
    Evidence,
    EvidenceAcquisitionStatus,
    EvidenceBatch,
    EvidencePlan,
    EvidenceRequest,
    EvidenceType,
    RawReference,
)


class FakeInvestigationEngine:
    """Return the fixed four-item request/success/delay/success evidence chain."""

    def __init__(self, *, fail_times: int = 0, empty_batch_times: int = 0) -> None:
        self._remaining_failures = fail_times
        self._remaining_empty_batches = empty_batch_times

    async def collect(self, request: EvidenceRequest) -> Evidence:
        self._maybe_fail()
        return self._evidence_for(request)

    async def collect_batch(self, plan: EvidencePlan) -> EvidenceBatch:
        self._maybe_fail()
        if self._remaining_empty_batches > 0:
            self._remaining_empty_batches -= 1
            evidence: list[Evidence] = []
        else:
            evidence = [self._evidence_for(request) for request in plan.requests]
        return EvidenceBatch(
            schema_version=plan.schema_version,
            incident_id=plan.incident_id,
            request_id=plan.request_id,
            timestamp=plan.timestamp,
            source="fake-investigation",
            metadata={"fake": True},
            evidence=evidence,
        )

    def _maybe_fail(self) -> None:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("configured Fake Investigation failure")

    @staticmethod
    def _evidence_for(request: EvidenceRequest) -> Evidence:
        values: dict[
            str,
            tuple[str, EvidenceType, str, dict[str, JsonValue], list[str], list[str]],
        ] = {
            "request-count": (
                "E-1",
                EvidenceType.TRACE,
                "fake://trace/business/BIZ-001/requests",
                {"business_id": "BIZ-001", "request_count": 2},
                ["H-1"],
                [],
            ),
            "first-result": (
                "E-2",
                EvidenceType.LOG,
                "fake://logs/request/first",
                {"request": 1, "backend_result": "created", "order_id": "ORDER-1"},
                ["H-1"],
                ["H-3"],
            ),
            "response-delay": (
                "E-3",
                EvidenceType.TRACE,
                "fake://trace/request/first/response",
                {"response_delay_ms": 3000, "client_timeout_ms": 1000},
                ["H-1"],
                ["H-2"],
            ),
            "second-result": (
                "E-4",
                EvidenceType.EVENT,
                "fake://events/request/second",
                {"request": 2, "backend_result": "created", "order_id": "ORDER-2"},
                ["H-1"],
                ["H-3"],
            ),
        }
        evidence_id, evidence_type, uri, value, supports, contradicts = values[request.query]
        return Evidence(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="fake-investigation",
            metadata={"fake": True},
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            raw_reference=RawReference(
                uri=uri,
                digest=f"sha256:fake-{evidence_id.lower()}",
                media_type="application/json",
            ),
            structured_value=value,
            observed_at=request.timestamp,
            supports_hypotheses=supports,
            contradicts_hypotheses=contradicts,
            confidence=1.0,
            acquisition_status=EvidenceAcquisitionStatus.ACQUIRED,
        )
