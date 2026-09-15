"""Minimal real Knowledge, Investigation, and Reproduction Port adapters."""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from pydantic import JsonValue

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    Evidence,
    EvidenceAcquisitionStatus,
    EvidenceBackedClaim,
    EvidenceBatch,
    EvidencePlan,
    EvidencePlanningRequest,
    EvidenceRequest,
    EvidenceType,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentPlanningRequest,
    ExperimentResult,
    ExperimentStatus,
    ExperimentStep,
    ExperimentVerificationRequest,
    KnowledgeContext,
    KnowledgeQuery,
    PreparedEnvironment,
    ProblemContext,
    ProductContext,
    RawReference,
    RootCause,
    RootCauseAssessment,
    RootCauseStatus,
    RootCauseVerificationRequest,
    TroubleshootingContext,
    VerificationResult,
    VerificationStatus,
)
from ops_agent.reasoning.adapters import FakeReasoningEngine

from .api.environment import ScenarioObservation, TimeoutRetryEnvironment


class FixtureKnowledgeEngine:
    """Read versioned product behavior from a repository-owned JSON fixture."""

    def __init__(self, fixture_path: Path) -> None:
        self._fixture_path = fixture_path
        self._data: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))

    async def resolve_product(self, problem: ProblemContext) -> ProductContext:
        return ProductContext.model_validate(
            {
                **self._base(problem),
                "product_name": self._data["product_name"],
                "product_version": self._data["product_version"],
                "component": self._data["component"],
                "deployment_environment": "isolated-mvp",
                "expected_behavior": self._data["expected_behavior"],
                "configuration": self._data["configuration"],
            }
        )

    async def query_product_knowledge(self, query: KnowledgeQuery) -> KnowledgeContext:
        return KnowledgeContext.model_validate(
            {
                **self._base(query),
                "query": query.query,
                "facts": self._data["facts"],
                "references": [self._reference()],
                "skill_ids": ["product-knowledge"],
                "limitations": ["仅适用于 timeout-retry-duplicate-create MVP fixture。"],
            }
        )

    async def query_troubleshooting(self, query: KnowledgeQuery) -> TroubleshootingContext:
        return TroubleshootingContext.model_validate(
            {
                **self._base(query),
                "actions_taken": [
                    "按 Troubleshooting Skill 检查请求、日志、响应延迟和数据库记录。"
                ],
                "observed_results": [],
                "known_workarounds": self._data["known_workarounds"],
                "constraints": ["隔离测试后端", "不访问生产系统", "不人工修改数据库"],
            }
        )

    def _reference(self) -> RawReference:
        content = self._fixture_path.read_bytes()
        return RawReference(
            uri=self._fixture_path.resolve().as_uri(),
            digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
            media_type="application/json",
        )

    @staticmethod
    def _base(contract: ProblemContext | KnowledgeQuery) -> dict[str, object]:
        return {
            "schema_version": contract.schema_version,
            "incident_id": contract.incident_id,
            "request_id": contract.request_id,
            "timestamp": contract.timestamp,
            "source": "mvp-fixture-knowledge",
            "metadata": {"fixture": True},
        }


class ArtifactInvestigationEngine:
    """Collect evidence from actual HTTP records, logs, SQLite, and page events."""

    def __init__(self, environment: TimeoutRetryEnvironment) -> None:
        self._environment = environment

    async def collect(self, request: EvidenceRequest) -> Evidence:
        return self._collect(request)

    async def collect_batch(self, plan: EvidencePlan) -> EvidenceBatch:
        return EvidenceBatch(
            schema_version=plan.schema_version,
            incident_id=plan.incident_id,
            request_id=plan.request_id,
            timestamp=plan.timestamp,
            source="mvp-artifact-investigation",
            metadata={"real_artifacts": True},
            evidence=[self._collect(request) for request in plan.requests],
        )

    def _collect(self, request: EvidenceRequest) -> Evidence:
        records = self._environment.request_records()
        order_ids = self._environment.order_ids(TimeoutRetryEnvironment.BUSINESS_ID)
        page = json.loads(self._environment.page_path.read_text(encoding="utf-8"))
        by_query: dict[str, tuple[str, EvidenceType, Path, JsonValue, list[str], list[str]]] = {
            "http-requests": (
                "E-HTTP-REQUESTS",
                EvidenceType.TRACE,
                self._environment.requests_path,
                cast(
                    dict[str, JsonValue],
                    {
                        "business_id": TimeoutRetryEnvironment.BUSINESS_ID,
                        "request_count": len(records),
                    },
                ),
                ["H-1"],
                [],
            ),
            "first-request-log": (
                "E-FIRST-LOG",
                EvidenceType.LOG,
                self._environment.logs_path,
                records[0],
                ["H-1"],
                ["H-3"],
            ),
            "response-delay": (
                "E-RESPONSE-DELAY",
                EvidenceType.TRACE,
                self._environment.requests_path,
                cast(
                    dict[str, JsonValue],
                    {
                        "trace_id": records[0]["trace_id"],
                        "request_id": records[0]["request_id"],
                        "response_delay_ms": records[0]["response_delay_ms"],
                        "client_timeout_ms": records[0]["client_timeout_ms"],
                    },
                ),
                ["H-1"],
                ["H-2"],
            ),
            "second-request-log": (
                "E-SECOND-LOG",
                EvidenceType.LOG,
                self._environment.logs_path,
                records[1],
                ["H-1"],
                ["H-3"],
            ),
            "database-orders": (
                "E-DATABASE",
                EvidenceType.EVENT,
                self._environment.database_path,
                cast(
                    dict[str, JsonValue],
                    {
                        "business_id": TimeoutRetryEnvironment.BUSINESS_ID,
                        "order_count": len(order_ids),
                        "order_ids": order_ids,
                    },
                ),
                ["H-1"],
                [],
            ),
            "page-events": (
                "E-PAGE",
                EvidenceType.EVENT,
                self._environment.page_path,
                cast(
                    dict[str, JsonValue],
                    {"events": page["events"], "retry_count": page["retry_count"]},
                ),
                ["H-1"],
                ["H-2"],
            ),
        }
        try:
            evidence_id, evidence_type, path, value, supports, contradicts = by_query[request.query]
        except KeyError as error:
            raise RuntimeError(f"unsupported MVP evidence query: {request.query}") from error
        content = path.read_bytes()
        return Evidence(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="mvp-artifact-investigation",
            metadata={"real_artifact": True},
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            raw_reference=RawReference(
                uri=path.resolve().as_uri(),
                digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
                media_type=(
                    "application/vnd.sqlite3" if path.suffix == ".sqlite3" else "application/json"
                ),
            ),
            structured_value=value,
            observed_at=request.timestamp,
            supports_hypotheses=supports,
            contradicts_hypotheses=contradicts,
            confidence=1.0,
            acquisition_status=EvidenceAcquisitionStatus.ACQUIRED,
        )


class MvpRuleReasoningEngine(FakeReasoningEngine):
    """Fixed, inspectable rules for evidence and reproduction planning in this case."""

    async def plan_evidence(self, request: EvidencePlanningRequest) -> EvidencePlan:
        specifications = [
            ("REQ-MVP-1", EvidenceType.TRACE, "确认自动重试产生两个 HTTP 请求。", "http-requests"),
            ("REQ-MVP-2", EvidenceType.LOG, "确认首次请求已经创建订单。", "first-request-log"),
            ("REQ-MVP-3", EvidenceType.TRACE, "比较首次响应延迟和客户端超时。", "response-delay"),
            ("REQ-MVP-4", EvidenceType.LOG, "确认重试请求再次创建订单。", "second-request-log"),
            ("REQ-MVP-5", EvidenceType.EVENT, "查询同一业务标识的数据库记录。", "database-orders"),
            (
                "REQ-MVP-6",
                EvidenceType.EVENT,
                "检查页面提交、超时、重试和成功行为。",
                "page-events",
            ),
        ]
        evidence_requests = [
            EvidenceRequest(
                schema_version=request.schema_version,
                incident_id=request.incident_id,
                request_id=request_id,
                timestamp=request.timestamp,
                source="mvp-rule-reasoning",
                metadata={"rule": "timeout-retry-duplicate-create"},
                hypothesis_ids=["H-1"],
                evidence_type=evidence_type,
                description=description,
                query=query,
                acquisition_method="mvp-artifact-investigation.collect",
                priority=min(index, 5),
                required=True,
                time_range=None,
            )
            for index, (request_id, evidence_type, description, query) in enumerate(
                specifications, start=1
            )
        ]
        return EvidencePlan(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="mvp-rule-reasoning",
            metadata={"rule": "timeout-retry-duplicate-create"},
            objective="用 HTTP、日志、延迟、SQLite 和页面行为验证 H-1。",
            requests=evidence_requests,
            completion_criteria=["六类证据均成功采集。"],
        )

    async def plan_experiment(self, request: ExperimentPlanningRequest) -> ExperimentPlan:
        return ExperimentPlan(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="mvp-rule-reasoning",
            metadata={"rule": "timeout-retry-duplicate-create"},
            experiment_id="EXP-MVP-1",
            title="提交成功后延迟首次响应并触发一次自动重试",
            objective="验证非幂等接口在首次成功但响应超时时产生重复订单。",
            hypothesis_ids=[request.hypothesis.hypothesis_id],
            environment={
                "backend": "fastapi-asgi",
                "database": "sqlite",
                "client": "httpx-controlled-retry",
            },
            steps=[
                ExperimentStep(
                    step_number=1,
                    action="初始化空 SQLite 数据库并加载订单页面。",
                    expected_outcome="orders 表为空，页面进入 idle。",
                ),
                ExperimentStep(
                    step_number=2,
                    action="首次请求提交后延迟响应 80ms，客户端 20ms 超时。",
                    expected_outcome="首次订单已落库但客户端观察到超时。",
                ),
                ExperimentStep(
                    step_number=3,
                    action="客户端用同一 business_id 自动重试一次。",
                    expected_outcome="第二个订单被非幂等接口创建。",
                ),
            ],
            success_criteria=["同一 business_id 存在两个订单和两个 request_id。"],
            rollback_steps=["关闭 HTTP client；测试目录由调用方清理。"],
            risk_level="isolated",
            requires_approval=False,
        )

    async def verify_root_cause(
        self,
        request: RootCauseVerificationRequest,
    ) -> RootCauseAssessment:
        evidence_ids = [item.evidence_id for item in request.evidence]
        return RootCauseAssessment(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="mvp-rule-reasoning",
            metadata={"rule": "timeout-retry-duplicate-create"},
            status=RootCauseStatus.CONFIRMED,
            confirmed_facts=[
                EvidenceBackedClaim(
                    statement="同一 business_id 存在两个 HTTP 创建请求。",
                    evidence_ids=["E-HTTP-REQUESTS"],
                ),
                EvidenceBackedClaim(
                    statement="首次请求已创建订单，但响应延迟超过客户端超时。",
                    evidence_ids=["E-FIRST-LOG", "E-RESPONSE-DELAY"],
                ),
                EvidenceBackedClaim(
                    statement="重试请求再次创建订单，SQLite 最终存在两条记录。",
                    evidence_ids=["E-SECOND-LOG", "E-DATABASE", "E-PAGE"],
                ),
            ],
            inferences=[
                EvidenceBackedClaim(
                    statement="自动重试与创建接口缺少幂等保护共同导致重复订单。",
                    evidence_ids=evidence_ids,
                )
            ],
            root_causes=[
                RootCause(
                    description=(
                        "创建订单接口未实施幂等去重；首次成功响应延迟触发客户端重试，"
                        "第二次请求再次创建订单。"
                    ),
                    confidence=0.98,
                    hypothesis_ids=["H-1"],
                    evidence_ids=evidence_ids,
                )
            ],
            unverified_items=[
                "真实浏览器 JavaScript 行为未通过 Playwright 验证。",
                "生产环境真实网络延迟来源尚未验证。",
            ],
            overall_confidence=0.98,
        )


class HttpSqliteReproductionEngine:
    """Run and verify the delayed response against the isolated real backend."""

    def __init__(self, environment: TimeoutRetryEnvironment) -> None:
        self._environment = environment
        self._latest: ScenarioObservation | None = None

    async def prepare(self, plan: ExperimentPlan) -> PreparedEnvironment:
        await self._environment.reset()
        return PreparedEnvironment(
            schema_version=plan.schema_version,
            incident_id=plan.incident_id,
            request_id=plan.request_id,
            timestamp=plan.timestamp,
            source="mvp-http-sqlite-reproduction",
            metadata={"fault": "post-commit-response-delay"},
            experiment_id=plan.experiment_id,
            environment_ref=str(self._environment.output_dir),
            ready=True,
            expires_at=None,
        )

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self._latest = await self._environment.run_scenario()
        return ExperimentResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="mvp-http-sqlite-reproduction",
            metadata={"real_http": True, "real_sqlite": True},
            experiment_id=request.plan.experiment_id,
            status=ExperimentStatus.SUCCEEDED,
            started_at=request.timestamp,
            completed_at=request.timestamp,
            observations=[
                "首次 POST /orders 已提交 SQLite 后，响应被延迟到客户端超时之后。",
                "客户端使用相同 business_id 和 trace_id 自动重试。",
                "两次请求使用不同 request_id，均创建了数据库记录。",
            ],
            evidence_ids=[
                "E-HTTP-REQUESTS",
                "E-FIRST-LOG",
                "E-RESPONSE-DELAY",
                "E-SECOND-LOG",
                "E-DATABASE",
                "E-PAGE",
            ],
            outputs=cast(
                dict[str, JsonValue],
                {
                    "business_id": self._latest.business_id,
                    "trace_id": self._latest.trace_id,
                    "request_ids": self._latest.request_ids,
                    "client_retries": self._latest.retry_count,
                    "orders_created": len(self._latest.order_ids),
                    "order_ids": self._latest.order_ids,
                    "page_events": self._latest.page_events,
                },
            ),
        )

    async def verify(self, request: ExperimentVerificationRequest) -> VerificationResult:
        order_ids = self._environment.order_ids(TimeoutRetryEnvironment.BUSINESS_ID)
        records = self._environment.request_records()
        confirmed = len(order_ids) == 2 and len(records) == 2
        return VerificationResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="mvp-http-sqlite-reproduction",
            metadata={"database_query": True},
            status=VerificationStatus.CONFIRMED if confirmed else VerificationStatus.REJECTED,
            hypothesis_ids=["H-1"],
            experiment_ids=[request.plan.experiment_id],
            evidence_ids=request.result.evidence_ids,
            confirmed_claims=(
                ["同一 business_id 在一次超时重试序列中产生两个订单。"] if confirmed else []
            ),
            rejected_claims=[] if confirmed else ["没有观察到两个订单。"],
            unverified_claims=["生产环境真实延迟来源未验证。"],
            rationale="SQLite 行数和 HTTP 请求记录同时验证重复创建。",
            confidence=1.0 if confirmed else 0.0,
        )

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        await self._environment.cleanup()
        return CleanupResult(
            schema_version=request.schema_version,
            incident_id=request.incident_id,
            request_id=request.request_id,
            timestamp=request.timestamp,
            source="mvp-http-sqlite-reproduction",
            metadata={},
            experiment_id=request.experiment_id,
            environment_ref=request.environment_ref,
            cleaned=True,
            observations=["HTTP client 已关闭；隔离证据目录保留用于 Case 沉淀。"],
        )
