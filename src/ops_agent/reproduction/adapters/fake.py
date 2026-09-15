"""Deterministic ReproductionPort implementation for the MVP Fake case."""

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    ExperimentVerificationRequest,
    PreparedEnvironment,
    VerificationResult,
    VerificationStatus,
)


class FakeReproductionEngine:
    """Simulate delayed first response, one retry, and two created orders."""

    def __init__(self, *, fail_times: int = 0) -> None:
        self._remaining_failures = fail_times

    async def prepare(self, plan: ExperimentPlan) -> PreparedEnvironment:
        return PreparedEnvironment(
            schema_version=plan.schema_version,
            incident_id=plan.incident_id,
            request_id=plan.request_id,
            timestamp=plan.timestamp,
            source="fake-reproduction",
            metadata={"fake": True},
            experiment_id=plan.experiment_id,
            environment_ref="FAKE-ENV-DUPLICATE-ORDER",
            ready=True,
            expires_at=None,
        )

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("configured Fake Reproduction failure")
        return ExperimentResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="fake-reproduction",
            metadata={"fake": True},
            experiment_id=request.plan.experiment_id,
            status=ExperimentStatus.SUCCEEDED,
            started_at=request.timestamp,
            completed_at=request.timestamp,
            observations=[
                "首次请求创建 ORDER-1。",
                "首次响应延迟超过客户端超时。",
                "客户端以相同业务标识重试。",
                "重试请求创建 ORDER-2。",
            ],
            evidence_ids=["E-1", "E-2", "E-3", "E-4"],
            outputs={
                "business_id": "BIZ-001",
                "client_retries": 1,
                "orders_created": 2,
                "order_ids": ["ORDER-1", "ORDER-2"],
            },
        )

    async def verify(self, request: ExperimentVerificationRequest) -> VerificationResult:
        orders_created = request.result.outputs.get("orders_created")
        confirmed = orders_created == 2
        return VerificationResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="fake-reproduction",
            metadata={"fake": True},
            status=(VerificationStatus.CONFIRMED if confirmed else VerificationStatus.REJECTED),
            hypothesis_ids=["H-1"],
            experiment_ids=[request.plan.experiment_id],
            evidence_ids=["E-1", "E-2", "E-3", "E-4"],
            confirmed_claims=(
                ["同一业务标识出现两个订单。", "H-1 被固定实验验证。"] if confirmed else []
            ),
            rejected_claims=[] if confirmed else ["H-1 未被固定实验验证。"],
            unverified_claims=["真实生产延迟来源未验证。"],
            rationale="Fake 输出显示首次成功、响应超时、客户端重试和二次创建。",
            confidence=1.0 if confirmed else 0.0,
        )

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        return CleanupResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="fake-reproduction",
            metadata={"fake": True},
            experiment_id=request.experiment_id,
            environment_ref=request.environment_ref,
            cleaned=True,
            observations=["Fake 内存环境已清理。"],
        )
