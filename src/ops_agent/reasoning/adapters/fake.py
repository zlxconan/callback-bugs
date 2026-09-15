"""Deterministic ReasoningPort implementation for the MVP Fake case."""

from typing import Any

from ops_agent.contracts import (
    EvidenceBackedClaim,
    EvidencePlan,
    EvidencePlanningRequest,
    EvidenceRequest,
    EvidenceType,
    ExperimentPlan,
    ExperimentPlanningRequest,
    ExperimentStatus,
    ExperimentStep,
    Hypothesis,
    HypothesisGenerationRequest,
    HypothesisSet,
    HypothesisStatus,
    NextAction,
    ReflectionRequest,
    ReflectionResult,
    RootCause,
    RootCauseAssessment,
    RootCauseStatus,
    RootCauseVerificationRequest,
)


class FakeReasoningEngine:
    """Produce fixed hypotheses, plans, reflection, and assessment."""

    async def generate_hypotheses(
        self,
        request: HypothesisGenerationRequest,
    ) -> HypothesisSet:
        common = self._common(request)
        hypotheses = [
            Hypothesis(
                **common,
                hypothesis_id="H-1",
                fact=["客户端在首次超时后执行了重试。"],
                inference="首次请求已成功，但响应延迟触发重试并导致再次创建。",
                assumption=["两次请求使用同一业务标识。"],
                confidence=0.7,
                supporting_evidence=[],
                contradicting_evidence=[],
                missing_evidence=["REQ-E1", "REQ-E2", "REQ-E3", "REQ-E4"],
                status=HypothesisStatus.TESTING,
            ),
            Hypothesis(
                **common,
                hypothesis_id="H-2",
                fact=["最终存在两个订单。"],
                inference="前端重复点击可能发起两次创建。",
                assumption=["用户在超时窗口内再次点击。"],
                confidence=0.2,
                supporting_evidence=[],
                contradicting_evidence=[],
                missing_evidence=["REQ-E1"],
                status=HypothesisStatus.PROPOSED,
            ),
            Hypothesis(
                **common,
                hypothesis_id="H-3",
                fact=["最终存在两个订单。"],
                inference="消息队列重复消费可能创建两个订单。",
                assumption=["创建链路包含异步消费。"],
                confidence=0.1,
                supporting_evidence=[],
                contradicting_evidence=[],
                missing_evidence=["REQ-E2", "REQ-E4"],
                status=HypothesisStatus.PROPOSED,
            ),
        ]
        return HypothesisSet(
            **common,
            hypotheses=hypotheses,
            prioritized_hypothesis_ids=["H-1", "H-2", "H-3"],
            selection_rationale="超时重试与非幂等风险最符合问题描述。",
        )

    async def plan_evidence(self, request: EvidencePlanningRequest) -> EvidencePlan:
        common = self._common(request)
        specifications = [
            ("REQ-E1", EvidenceType.TRACE, "确认同一业务标识是否存在两次请求。", "request-count"),
            ("REQ-E2", EvidenceType.LOG, "确认第一次请求后端是否实际成功。", "first-result"),
            ("REQ-E3", EvidenceType.TRACE, "确认首次响应是否超过客户端超时。", "response-delay"),
            ("REQ-E4", EvidenceType.EVENT, "确认第二次请求是否再次创建成功。", "second-result"),
        ]
        requests = [
            EvidenceRequest(
                schema_version=request.schema_version,
                incident_id=request.incident_id,
                request_id=request_id,
                timestamp=request.timestamp,
                source="fake-reasoning",
                metadata={"fake": True},
                hypothesis_ids=["H-1"],
                evidence_type=evidence_type,
                description=description,
                query=query,
                acquisition_method="fake-investigation.collect",
                priority=index,
                required=True,
                time_range=None,
            )
            for index, (request_id, evidence_type, description, query) in enumerate(
                specifications, start=1
            )
        ]
        return EvidencePlan(
            **common,
            objective="验证首次成功、响应延迟、客户端重试和二次创建之间的因果链。",
            requests=requests,
            completion_criteria=["四项固定证据均已获取。"],
        )

    async def reflect(self, request: ReflectionRequest) -> ReflectionResult:
        experiment_failed = bool(
            request.experiment_results
            and request.experiment_results[-1].status is ExperimentStatus.FAILED
        )
        return ReflectionResult(
            **self._common(request),
            summary=(
                "实验执行失败，重新规划实验。"
                if experiment_failed
                else "证据不足，重新规划并采集证据。"
            ),
            retained_hypothesis_ids=["H-1", "H-2", "H-3"],
            rejected_hypothesis_ids=[],
            new_hypotheses=[],
            missing_evidence=[] if experiment_failed else ["REQ-E1", "REQ-E2", "REQ-E3", "REQ-E4"],
            next_action=(
                NextAction.PLAN_EXPERIMENT if experiment_failed else NextAction.COLLECT_EVIDENCE
            ),
            should_continue=True,
        )

    async def verify_root_cause(
        self,
        request: RootCauseVerificationRequest,
    ) -> RootCauseAssessment:
        evidence_ids = [item.evidence_id for item in request.evidence]
        return RootCauseAssessment(
            **self._common(request),
            status=RootCauseStatus.CONFIRMED,
            confirmed_facts=[
                EvidenceBackedClaim(
                    statement="同一业务标识存在两次创建请求。",
                    evidence_ids=["E-1"],
                ),
                EvidenceBackedClaim(
                    statement="第一次请求后端成功但响应延迟，第二次请求也创建成功。",
                    evidence_ids=["E-2", "E-3", "E-4"],
                ),
            ],
            inferences=[
                EvidenceBackedClaim(
                    statement="客户端重试与服务端缺少幂等保护共同导致重复订单。",
                    evidence_ids=evidence_ids,
                )
            ],
            root_causes=[
                RootCause(
                    description="创建订单接口未实施幂等去重；首次成功响应延迟触发客户端重试，第二次请求再次创建订单。",
                    confidence=0.98,
                    hypothesis_ids=["H-1"],
                    evidence_ids=evidence_ids,
                )
            ],
            unverified_items=["真实生产网络延迟来源尚未验证。", "消息队列链路未接入真实数据验证。"],
            overall_confidence=0.98,
        )

    async def plan_experiment(self, request: ExperimentPlanningRequest) -> ExperimentPlan:
        return ExperimentPlan(
            **self._common(request),
            experiment_id="EXP-1",
            title="模拟首次响应延迟触发客户端重试",
            objective="验证非幂等创建接口在首次成功但响应超时时产生重复订单。",
            hypothesis_ids=["H-1"],
            environment={"kind": "fake", "external_systems": False},
            steps=[
                ExperimentStep(
                    step_number=1,
                    action="使用固定业务标识提交创建订单请求。",
                    expected_outcome="后端创建第一个订单。",
                ),
                ExperimentStep(
                    step_number=2,
                    action="将首次响应延迟到客户端超时之后。",
                    expected_outcome="客户端触发一次自动重试。",
                ),
                ExperimentStep(
                    step_number=3,
                    action="允许重试请求再次进入非幂等创建逻辑。",
                    expected_outcome="相同业务标识产生第二个订单。",
                ),
            ],
            success_criteria=["相同业务标识最终对应两个订单。", "H-1 的因果链被复现。"],
            rollback_steps=["清理 Fake 内存环境。"],
            risk_level="none",
            requires_approval=False,
        )

    @staticmethod
    def _common(request: object) -> dict[str, Any]:
        contract = request
        if not isinstance(
            contract,
            (
                HypothesisGenerationRequest,
                EvidencePlanningRequest,
                ReflectionRequest,
                RootCauseVerificationRequest,
                ExperimentPlanningRequest,
            ),
        ):
            raise TypeError("unsupported fake reasoning request")
        return {
            "schema_version": contract.schema_version,
            "incident_id": contract.incident_id,
            "request_id": contract.request_id,
            "timestamp": contract.timestamp,
            "source": "fake-reasoning",
            "metadata": {"fake": True},
        }
