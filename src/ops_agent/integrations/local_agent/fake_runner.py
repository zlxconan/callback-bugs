"""Port-driven task runner used exclusively for deterministic Fake E2E."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from ops_agent.contracts import (
    EnvironmentCleanupRequest,
    ErrorCategory,
    ErrorResponse,
    EvidenceChainLink,
    EvidencePlanningRequest,
    EvidenceRelationship,
    ExperimentExecutionRequest,
    ExperimentPlanningRequest,
    ExperimentVerificationRequest,
    HypothesisGenerationRequest,
    IncidentQuery,
    IncidentState,
    KnowledgeLookupResult,
    KnowledgeQuery,
    RCAReport,
    ReflectionRequest,
    RemediationRecommendation,
    RootCauseVerificationRequest,
    RuntimeStage,
    RuntimeTask,
    StartIncidentRequest,
    TaskOutput,
    TaskResult,
    TaskStatus,
)
from ops_agent.ports import (
    InvestigationPort,
    KnowledgePort,
    ReasoningPort,
    ReproductionPort,
    RuntimePort,
)


class FixedClock:
    """ClockPort implementation that always returns one timezone-aware value."""

    def __init__(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self._value = value

    async def now(self) -> datetime:
        return self._value


class FakeIncidentOutcome(BaseModel):
    """Serializable output of one Fake incident run."""

    model_config = ConfigDict(extra="forbid")

    query: IncidentQuery
    stage_history: list[RuntimeStage]
    final_state: IncidentState

    @property
    def report(self) -> RCAReport | None:
        """Expose the final report without duplicating it in serialized artifacts."""
        return self.final_state.rca_report


class FakeTaskReasoner:
    """Complete one RuntimeTask through Engine ports without access to Runtime state APIs."""

    def __init__(
        self,
        *,
        knowledge: KnowledgePort,
        reasoning: ReasoningPort,
        investigation: InvestigationPort,
        reproduction: ReproductionPort,
    ) -> None:
        self._knowledge = knowledge
        self._reasoning = reasoning
        self._investigation = investigation
        self._reproduction = reproduction

    async def reason(self, task: RuntimeTask, state: IncidentState) -> TaskResult:
        """Complete exactly one RuntimeTask without submitting or changing state."""
        try:
            output = await self._dispatch(task, state)
            return self._successful_result(task, output)
        except RuntimeError as error:
            return self._failed_result(task, str(error))

    async def _dispatch(self, task: RuntimeTask, state: IncidentState) -> TaskOutput:
        stage = task.stage
        if stage is RuntimeStage.NORMALIZE:
            return TaskOutput(problem=state.problem)
        if stage is RuntimeStage.KNOWLEDGE_LOOKUP:
            product = await self._knowledge.resolve_product(state.problem)
            query = KnowledgeQuery(
                **self._base(task),
                problem=state.problem,
                product=product,
                query="订单创建接口的客户端重试与幂等行为",
            )
            knowledge = await self._knowledge.query_product_knowledge(query)
            troubleshooting = await self._knowledge.query_troubleshooting(query)
            return TaskOutput(
                knowledge_lookup=KnowledgeLookupResult(
                    product=product,
                    knowledge=knowledge,
                    troubleshooting=troubleshooting,
                )
            )
        if stage is RuntimeStage.HYPOTHESIS:
            if state.product is None or state.knowledge is None:
                raise RuntimeError("knowledge stage outputs are missing")
            hypothesis_request = HypothesisGenerationRequest(
                **self._base(task),
                problem=state.problem,
                product=state.product,
                knowledge=state.knowledge,
                troubleshooting=state.troubleshooting,
                evidence=state.evidence,
            )
            return TaskOutput(
                hypotheses=await self._reasoning.generate_hypotheses(hypothesis_request)
            )
        if stage is RuntimeStage.EVIDENCE_PLAN:
            if state.hypotheses is None:
                raise RuntimeError("hypotheses are missing")
            evidence_request = EvidencePlanningRequest(
                **self._base(task),
                problem=state.problem,
                hypotheses=state.hypotheses,
                available_evidence=state.evidence,
            )
            return TaskOutput(evidence_plan=await self._reasoning.plan_evidence(evidence_request))
        if stage is RuntimeStage.INVESTIGATE:
            if state.latest_evidence_plan is None:
                raise RuntimeError("evidence plan is missing")
            return TaskOutput(
                evidence_batch=await self._investigation.collect_batch(state.latest_evidence_plan)
            )
        if stage is RuntimeStage.ROOT_CAUSE_ASSESSMENT:
            if state.hypotheses is None:
                raise RuntimeError("hypotheses are missing")
            assessment_request = RootCauseVerificationRequest(
                **self._base(task),
                hypotheses=state.hypotheses,
                evidence=state.evidence,
                verification_results=state.verification_results,
            )
            assessment = await self._reasoning.verify_root_cause(assessment_request)
            return TaskOutput(root_cause_assessment=assessment)
        if stage is RuntimeStage.EXPERIMENT_PLAN:
            if state.product is None or state.hypotheses is None:
                raise RuntimeError("experiment planning context is missing")
            primary_id = state.hypotheses.prioritized_hypothesis_ids[0]
            primary = next(
                item for item in state.hypotheses.hypotheses if item.hypothesis_id == primary_id
            )
            plan_request = ExperimentPlanningRequest(
                **self._base(task),
                problem=state.problem,
                product=state.product,
                hypothesis=primary,
                evidence=state.evidence,
            )
            return TaskOutput(experiment_plan=await self._reasoning.plan_experiment(plan_request))
        if stage is RuntimeStage.REPRODUCE:
            if not state.experiment_plans:
                raise RuntimeError("experiment plan is missing")
            plan = state.experiment_plans[-1]
            environment = await self._reproduction.prepare(plan)
            execution_request = ExperimentExecutionRequest(
                **self._base(task),
                plan=plan,
                environment=environment,
            )
            return TaskOutput(experiment_result=await self._reproduction.execute(execution_request))
        if stage is RuntimeStage.VERIFY:
            if not state.experiment_plans or not state.experiment_results:
                raise RuntimeError("experiment verification context is missing")
            plan = state.experiment_plans[-1]
            result = state.experiment_results[-1]
            verification_request = ExperimentVerificationRequest(
                **self._base(task),
                plan=plan,
                result=result,
                evidence=state.evidence,
            )
            verification = await self._reproduction.verify(verification_request)
            await self._reproduction.cleanup(
                EnvironmentCleanupRequest(
                    **self._base(task),
                    experiment_id=plan.experiment_id,
                    environment_ref="FAKE-ENV-DUPLICATE-ORDER",
                )
            )
            return TaskOutput(verification_result=verification)
        if stage is RuntimeStage.REFLECT:
            if state.hypotheses is None:
                raise RuntimeError("reflection hypotheses are missing")
            reflection_request = ReflectionRequest(
                **self._base(task),
                hypotheses=state.hypotheses,
                evidence=state.evidence,
                experiment_results=state.experiment_results,
                iteration=state.reflection_count,
            )
            return TaskOutput(reflection_result=await self._reasoning.reflect(reflection_request))
        if stage is RuntimeStage.RCA:
            return TaskOutput(rca_report=self._build_report(task, state))
        raise RuntimeError(f"Fake runner cannot execute stage: {stage}")

    @staticmethod
    def _build_report(task: RuntimeTask, state: IncidentState) -> RCAReport:
        assessment = state.root_cause_assessment
        if assessment is None:
            raise RuntimeError("root cause assessment is missing")
        evidence_chain = [
            EvidenceChainLink(
                evidence_id=evidence_id,
                relationship=EvidenceRelationship.SUPPORTS,
                target_id=cause.hypothesis_ids[0],
            )
            for cause in assessment.root_causes
            for evidence_id in cause.evidence_ids
        ]
        return RCAReport(
            **FakeTaskReasoner._base(task),
            report_id="RCA-DUPLICATE-ORDER-001",
            title="首次响应超时与客户端重试导致重复订单",
            executive_summary="首次创建已成功，但响应延迟触发客户端重试；创建接口缺少幂等保护，重试再次创建订单。",
            confirmed_facts=assessment.confirmed_facts,
            inferences=assessment.inferences,
            root_causes=assessment.root_causes,
            minimal_reproduction_conditions=[
                "创建接口使用相同业务标识",
                "首次请求后端成功但响应延迟超过客户端超时",
                "客户端在超时后自动重试",
                "服务端未实施幂等去重",
            ],
            remediation_recommendations=[
                RemediationRecommendation(
                    action="以业务标识或 Idempotency-Key 实现原子幂等去重。",
                    rationale="保证超时重试只返回首次创建结果，不产生第二个订单。",
                    priority=1,
                ),
                RemediationRecommendation(
                    action="记录并返回可查询的创建请求结果。",
                    rationale="客户端超时后可先查询结果，再决定是否重试。",
                    priority=2,
                ),
            ],
            unverified_items=assessment.unverified_items,
            evidence_chain=evidence_chain,
        )

    @staticmethod
    def _successful_result(task: RuntimeTask, output: TaskOutput) -> TaskResult:
        return TaskResult(
            **FakeTaskReasoner._base(task),
            task_id=task.task_id,
            status=TaskStatus.SUCCEEDED,
            output={},
            typed_output=output,
            evidence_ids=[],
            error=None,
            started_at=task.timestamp,
            completed_at=task.timestamp,
        )

    @staticmethod
    def _failed_result(task: RuntimeTask, message: str) -> TaskResult:
        error = ErrorResponse(
            **FakeTaskReasoner._base(task),
            code="FAKE_ENGINE_FAILURE",
            message=message,
            category=ErrorCategory.TRANSIENT,
            retryable=True,
            details={"fake": True},
        )
        return TaskResult(
            **FakeTaskReasoner._base(task),
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            output={},
            typed_output=None,
            evidence_ids=[],
            error=error,
            started_at=task.timestamp,
            completed_at=task.timestamp,
        )

    @staticmethod
    def _base(task: RuntimeTask) -> dict[str, Any]:
        return {
            "schema_version": task.schema_version,
            "incident_id": task.incident_id,
            "request_id": task.request_id,
            "timestamp": task.timestamp,
            "source": "fake-runner",
            "metadata": {"fake": True},
        }

    @staticmethod
    def _record_stage(history: list[RuntimeStage], state: IncidentState) -> None:
        if state.runtime_stage is not None and (
            not history or history[-1] is not state.runtime_stage
        ):
            history.append(state.runtime_stage)


class FakeIncidentRunner:
    """Legacy Fake E2E loop composed from RuntimePort and a stateless task reasoner."""

    def __init__(
        self,
        *,
        runtime: RuntimePort,
        knowledge: KnowledgePort,
        reasoning: ReasoningPort,
        investigation: InvestigationPort,
        reproduction: ReproductionPort,
    ) -> None:
        self._runtime = runtime
        self._reasoner = FakeTaskReasoner(
            knowledge=knowledge,
            reasoning=reasoning,
            investigation=investigation,
            reproduction=reproduction,
        )

    async def reason(self, task: RuntimeTask, state: IncidentState) -> TaskResult:
        return await self._reasoner.reason(task, state)

    async def run(
        self,
        command: StartIncidentRequest,
        *,
        max_tasks: int = 50,
    ) -> FakeIncidentOutcome:
        state = await self._runtime.start_incident(command)
        incident_query = IncidentQuery(
            schema_version=command.schema_version,
            incident_id=command.incident_id,
            request_id=command.request_id,
            timestamp=command.timestamp,
            source="fake-runner",
            metadata={"fake": True},
        )
        history: list[RuntimeStage] = []
        FakeTaskReasoner._record_stage(history, state)

        for _ in range(max_tasks):
            task = await self._runtime.get_next_task(incident_query)
            state = await self._runtime.get_state(incident_query)
            FakeTaskReasoner._record_stage(history, state)

            if state.runtime_stage in {
                RuntimeStage.COMPLETED,
                RuntimeStage.FAILED,
                RuntimeStage.WAITING_HUMAN,
            }:
                return FakeIncidentOutcome(
                    query=incident_query,
                    stage_history=history,
                    final_state=state,
                )
            if task is None:
                continue

            result = await self.reason(task, state)
            state = await self._runtime.submit_task_result(result)
            FakeTaskReasoner._record_stage(history, state)

        raise RuntimeError(f"Fake incident exceeded task limit: {max_tasks}")
