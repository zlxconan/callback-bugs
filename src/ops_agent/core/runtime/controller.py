"""Deterministic incident workflow controller."""

from collections.abc import Callable
from datetime import timedelta

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ops_agent.contracts import (
    AuditEvent,
    ErrorCategory,
    ErrorResponse,
    EvidenceChainLink,
    EvidenceRelationship,
    ExperimentStatus,
    FinishIncidentRequest,
    IncidentLifecycleStatus,
    IncidentQuery,
    IncidentState,
    NextAction,
    RCAReport,
    RootCauseStatus,
    RuntimeStage,
    RuntimeTask,
    StartIncidentRequest,
    TaskKind,
    TaskOutput,
    TaskResult,
    TaskStatus,
    VerificationStatus,
)
from ops_agent.ports import ClockPort, StateRepositoryPort


class RuntimeConfig(BaseModel):
    """Deterministic execution limits for one runtime instance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=3, ge=1)
    task_timeout_seconds: float = Field(default=30.0, gt=0)
    max_reflection_loops: int = Field(default=2, ge=0)


class RuntimeError(Exception):
    """Base error for deterministic runtime control failures."""


class IncidentNotFoundError(RuntimeError):
    """Raised when a requested incident state does not exist."""


class InvalidStateTransition(RuntimeError):
    """Raised when a stage change is not present in the transition table."""


class TerminalIncidentError(RuntimeError):
    """Raised when new work is submitted to a terminal incident."""


class TaskResultMismatch(RuntimeError):
    """Raised when a result does not match the pending task or its stage."""


ACTIVE_STAGES = frozenset(
    {
        RuntimeStage.NORMALIZE,
        RuntimeStage.KNOWLEDGE_LOOKUP,
        RuntimeStage.HYPOTHESIS,
        RuntimeStage.EVIDENCE_PLAN,
        RuntimeStage.INVESTIGATE,
        RuntimeStage.ROOT_CAUSE_ASSESSMENT,
        RuntimeStage.EXPERIMENT_PLAN,
        RuntimeStage.REPRODUCE,
        RuntimeStage.VERIFY,
        RuntimeStage.REFLECT,
        RuntimeStage.RCA,
        RuntimeStage.WAITING_HUMAN,
    }
)

STATE_TRANSITIONS: dict[RuntimeStage, frozenset[RuntimeStage]] = {
    RuntimeStage.CREATED: frozenset({RuntimeStage.NORMALIZE, RuntimeStage.FAILED}),
    RuntimeStage.NORMALIZE: frozenset({RuntimeStage.KNOWLEDGE_LOOKUP, RuntimeStage.FAILED}),
    RuntimeStage.KNOWLEDGE_LOOKUP: frozenset({RuntimeStage.HYPOTHESIS, RuntimeStage.FAILED}),
    RuntimeStage.HYPOTHESIS: frozenset({RuntimeStage.EVIDENCE_PLAN, RuntimeStage.FAILED}),
    RuntimeStage.EVIDENCE_PLAN: frozenset({RuntimeStage.INVESTIGATE, RuntimeStage.FAILED}),
    RuntimeStage.INVESTIGATE: frozenset(
        {RuntimeStage.ROOT_CAUSE_ASSESSMENT, RuntimeStage.REFLECT, RuntimeStage.FAILED}
    ),
    RuntimeStage.ROOT_CAUSE_ASSESSMENT: frozenset(
        {
            RuntimeStage.EXPERIMENT_PLAN,
            RuntimeStage.REFLECT,
            RuntimeStage.RCA,
            RuntimeStage.WAITING_HUMAN,
            RuntimeStage.FAILED,
        }
    ),
    RuntimeStage.EXPERIMENT_PLAN: frozenset(
        {RuntimeStage.REPRODUCE, RuntimeStage.WAITING_HUMAN, RuntimeStage.FAILED}
    ),
    RuntimeStage.REPRODUCE: frozenset(
        {RuntimeStage.VERIFY, RuntimeStage.REFLECT, RuntimeStage.FAILED}
    ),
    RuntimeStage.VERIFY: frozenset({RuntimeStage.RCA, RuntimeStage.REFLECT, RuntimeStage.FAILED}),
    RuntimeStage.REFLECT: frozenset(
        {
            RuntimeStage.HYPOTHESIS,
            RuntimeStage.EVIDENCE_PLAN,
            RuntimeStage.ROOT_CAUSE_ASSESSMENT,
            RuntimeStage.EXPERIMENT_PLAN,
            RuntimeStage.RCA,
            RuntimeStage.WAITING_HUMAN,
            RuntimeStage.FAILED,
        }
    ),
    RuntimeStage.RCA: frozenset({RuntimeStage.PERSIST, RuntimeStage.FAILED}),
    RuntimeStage.PERSIST: frozenset({RuntimeStage.COMPLETED, RuntimeStage.FAILED}),
    RuntimeStage.WAITING_HUMAN: frozenset(
        {
            RuntimeStage.HYPOTHESIS,
            RuntimeStage.EVIDENCE_PLAN,
            RuntimeStage.ROOT_CAUSE_ASSESSMENT,
            RuntimeStage.EXPERIMENT_PLAN,
            RuntimeStage.REPRODUCE,
            RuntimeStage.RCA,
            RuntimeStage.FAILED,
        }
    ),
    RuntimeStage.COMPLETED: frozenset(),
    RuntimeStage.FAILED: frozenset(),
}

STAGE_TASK_KIND: dict[RuntimeStage, TaskKind] = {
    RuntimeStage.NORMALIZE: TaskKind.NORMALIZATION,
    RuntimeStage.KNOWLEDGE_LOOKUP: TaskKind.KNOWLEDGE,
    RuntimeStage.HYPOTHESIS: TaskKind.REASONING,
    RuntimeStage.EVIDENCE_PLAN: TaskKind.REASONING,
    RuntimeStage.INVESTIGATE: TaskKind.INVESTIGATION,
    RuntimeStage.ROOT_CAUSE_ASSESSMENT: TaskKind.REASONING,
    RuntimeStage.EXPERIMENT_PLAN: TaskKind.REASONING,
    RuntimeStage.REPRODUCE: TaskKind.REPRODUCTION,
    RuntimeStage.VERIFY: TaskKind.VERIFICATION,
    RuntimeStage.REFLECT: TaskKind.REFLECTION,
    RuntimeStage.RCA: TaskKind.REASONING,
    RuntimeStage.WAITING_HUMAN: TaskKind.HUMAN_APPROVAL,
}

STAGE_LIFECYCLE_STATUS: dict[RuntimeStage, IncidentLifecycleStatus] = {
    RuntimeStage.CREATED: IncidentLifecycleStatus.RECEIVED,
    RuntimeStage.NORMALIZE: IncidentLifecycleStatus.CONTEXTUALIZING,
    RuntimeStage.KNOWLEDGE_LOOKUP: IncidentLifecycleStatus.CONTEXTUALIZING,
    RuntimeStage.HYPOTHESIS: IncidentLifecycleStatus.PLANNING,
    RuntimeStage.EVIDENCE_PLAN: IncidentLifecycleStatus.PLANNING,
    RuntimeStage.INVESTIGATE: IncidentLifecycleStatus.INVESTIGATING,
    RuntimeStage.ROOT_CAUSE_ASSESSMENT: IncidentLifecycleStatus.VERIFYING,
    RuntimeStage.EXPERIMENT_PLAN: IncidentLifecycleStatus.REPRODUCTION_PLANNING,
    RuntimeStage.REPRODUCE: IncidentLifecycleStatus.REPRODUCING,
    RuntimeStage.VERIFY: IncidentLifecycleStatus.VERIFYING,
    RuntimeStage.REFLECT: IncidentLifecycleStatus.REFLECTING,
    RuntimeStage.RCA: IncidentLifecycleStatus.VERIFYING,
    RuntimeStage.PERSIST: IncidentLifecycleStatus.VERIFYING,
    RuntimeStage.WAITING_HUMAN: IncidentLifecycleStatus.WAITING_APPROVAL,
    RuntimeStage.COMPLETED: IncidentLifecycleStatus.RESOLVED,
    RuntimeStage.FAILED: IncidentLifecycleStatus.FAILED,
}


def transition_stage(current: RuntimeStage, target: RuntimeStage) -> RuntimeStage:
    """Validate one state transition using the sole transition table."""

    if target not in STATE_TRANSITIONS[current]:
        raise InvalidStateTransition(f"cannot transition from {current.value} to {target.value}")
    return target


ResultHandler = Callable[[IncidentState, TaskOutput], RuntimeStage]


class CoreRuntime:
    """Pure deterministic workflow controller for external or local task owners."""

    def __init__(
        self,
        repository: StateRepositoryPort,
        clock: ClockPort,
        config: RuntimeConfig | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._config = config or RuntimeConfig()
        self._result_handlers: dict[RuntimeStage, ResultHandler] = {
            RuntimeStage.NORMALIZE: self._apply_normalize,
            RuntimeStage.KNOWLEDGE_LOOKUP: self._apply_knowledge_lookup,
            RuntimeStage.HYPOTHESIS: self._apply_hypotheses,
            RuntimeStage.EVIDENCE_PLAN: self._apply_evidence_plan,
            RuntimeStage.INVESTIGATE: self._apply_investigation,
            RuntimeStage.ROOT_CAUSE_ASSESSMENT: self._apply_root_cause_assessment,
            RuntimeStage.EXPERIMENT_PLAN: self._apply_experiment_plan,
            RuntimeStage.REPRODUCE: self._apply_reproduction,
            RuntimeStage.VERIFY: self._apply_verification,
            RuntimeStage.REFLECT: self._apply_reflection,
            RuntimeStage.RCA: self._apply_rca,
            RuntimeStage.WAITING_HUMAN: self._apply_human_decision,
        }

    async def start_incident(self, command: StartIncidentRequest) -> IncidentState:
        now = await self._clock.now()
        state = IncidentState(
            schema_version=command.schema_version,
            incident_id=command.incident_id,
            request_id=command.request_id,
            timestamp=now,
            source="core-runtime",
            metadata=command.metadata,
            status=IncidentLifecycleStatus.RECEIVED,
            revision=0,
            problem=command.problem,
            product=command.product,
            troubleshooting=command.troubleshooting,
            runtime_stage=RuntimeStage.CREATED,
        )
        state = await self._repository.create(state)
        await self._audit(state, "incident.created", "start_incident", "succeeded")
        return state

    async def get_next_task(self, query: IncidentQuery) -> RuntimeTask | None:
        state = await self._load(query)
        stage = self._stage(state)
        if stage in {RuntimeStage.COMPLETED, RuntimeStage.FAILED}:
            return None

        now = await self._clock.now()
        if state.pending_task is not None:
            pending = state.pending_task
            if pending.deadline is not None and now > pending.deadline:
                state = await self._handle_timeout(state, pending)
                return state.pending_task
            return pending

        if stage is RuntimeStage.CREATED:
            state = await self._move(state, RuntimeStage.NORMALIZE)
            stage = RuntimeStage.NORMALIZE
        elif stage is RuntimeStage.PERSIST:
            await self._move(state, RuntimeStage.COMPLETED, event_type="incident.completed")
            return None

        if stage not in ACTIVE_STAGES:
            raise InvalidStateTransition(f"stage {stage.value} cannot produce a task")

        return await self._create_task(state, attempt=1)

    async def submit_task_result(self, result: TaskResult) -> IncidentState:
        state = await self._load(self._query_from_contract(result))
        stage = self._stage(state)
        if stage in {RuntimeStage.COMPLETED, RuntimeStage.FAILED}:
            raise TerminalIncidentError(f"incident is terminal: {stage.value}")

        task = state.pending_task
        if task is None or task.task_id != result.task_id:
            raise TaskResultMismatch("result does not match the pending task")
        if task.stage is not stage:
            raise TaskResultMismatch("pending task stage does not match incident stage")
        if result.incident_id != state.incident_id or result.request_id != task.request_id:
            raise TaskResultMismatch("result correlation does not match the pending task")

        if task.deadline is not None:
            now = await self._clock.now()
            if now > task.deadline or result.completed_at > task.deadline:
                return await self._handle_timeout(state, task)
        if result.status is not TaskStatus.SUCCEEDED:
            return await self._handle_failed_result(state, task, result)
        if result.typed_output is None:
            raise TaskResultMismatch("successful result requires typed_output")

        handler = self._result_handlers.get(stage)
        if handler is None:
            raise InvalidStateTransition(f"stage {stage.value} cannot accept a result")
        target = handler(state, result.typed_output)
        await self._audit(
            state,
            "task.accepted",
            "submit_task_result",
            "succeeded",
            {"task_id": task.task_id, "stage": stage.value},
        )
        return await self._move(state, target)

    async def get_state(self, query: IncidentQuery) -> IncidentState:
        return await self._load(query)

    async def finish_incident(self, command: FinishIncidentRequest) -> RCAReport:
        state = await self._load(self._query_from_contract(command))
        stage = self._stage(state)
        if stage in {RuntimeStage.COMPLETED, RuntimeStage.FAILED}:
            raise TerminalIncidentError(f"incident is terminal: {stage.value}")
        if stage is not RuntimeStage.RCA:
            raise InvalidStateTransition("finish_incident is only valid during RCA")

        links = [
            EvidenceChainLink(
                evidence_id=evidence_id,
                relationship=EvidenceRelationship.SUPPORTS,
                target_id=cause.hypothesis_ids[0],
            )
            for cause in command.assessment.root_causes
            for evidence_id in cause.evidence_ids
        ]
        now = await self._clock.now()
        report = RCAReport(
            schema_version=command.schema_version,
            incident_id=command.incident_id,
            request_id=command.request_id,
            timestamp=now,
            source="core-runtime",
            metadata=command.metadata,
            report_id=f"RCA-{self._incident_suffix(command.incident_id)}",
            title=command.report_title,
            executive_summary=command.executive_summary,
            confirmed_facts=command.assessment.confirmed_facts,
            inferences=command.assessment.inferences,
            root_causes=command.assessment.root_causes,
            minimal_reproduction_conditions=command.minimal_reproduction_conditions,
            remediation_recommendations=command.remediation_recommendations,
            unverified_items=command.assessment.unverified_items,
            evidence_chain=links,
        )
        state.root_cause_assessment = command.assessment
        state.rca_report = report
        state.pending_task = None
        state = await self._move(state, RuntimeStage.PERSIST)
        await self._move(state, RuntimeStage.COMPLETED, event_type="incident.completed")
        return report

    async def _load(self, query: IncidentQuery) -> IncidentState:
        state = await self._repository.get(query)
        if state is None:
            raise IncidentNotFoundError(query.incident_id)
        return state

    async def _create_task(self, state: IncidentState, attempt: int) -> RuntimeTask:
        stage = self._stage(state)
        now = await self._clock.now()
        task = RuntimeTask(
            schema_version=state.schema_version,
            incident_id=state.incident_id,
            request_id=state.request_id,
            timestamp=now,
            source="core-runtime",
            metadata={},
            task_id=(
                f"TASK-{self._incident_suffix(state.incident_id)}-"
                f"{stage.value}-{state.revision + 1}-{attempt}"
            ),
            kind=STAGE_TASK_KIND[stage],
            status=TaskStatus.QUEUED,
            payload={"stage": stage.value},
            depends_on=[],
            attempt=attempt,
            max_attempts=self._config.max_attempts,
            deadline=now + timedelta(seconds=self._config.task_timeout_seconds),
            stage=stage,
        )
        state.pending_task = task
        state.revision += 1
        state.timestamp = now
        await self._repository.save(state)
        await self._audit(
            state,
            "task.created",
            "get_next_task",
            "succeeded",
            {"task_id": task.task_id, "stage": stage.value, "attempt": attempt},
        )
        return task

    async def _handle_failed_result(
        self,
        state: IncidentState,
        task: RuntimeTask,
        result: TaskResult,
    ) -> IncidentState:
        error = result.error or await self._runtime_error(
            state,
            code="TASK_TERMINATED",
            message=f"Task ended with status {result.status.value}.",
            category=ErrorCategory.TERMINAL,
            retryable=False,
        )
        return await self._route_error(state, task, error, "task.failed")

    async def _handle_timeout(
        self,
        state: IncidentState,
        task: RuntimeTask,
    ) -> IncidentState:
        error = await self._runtime_error(
            state,
            code="TASK_TIMEOUT",
            message=f"Task {task.task_id} exceeded its deadline.",
            category=ErrorCategory.TIMEOUT,
            retryable=True,
        )
        return await self._route_error(state, task, error, "task.timed_out")

    async def _route_error(
        self,
        state: IncidentState,
        task: RuntimeTask,
        error: ErrorResponse,
        event_type: str,
    ) -> IncidentState:
        state.last_error = error
        await self._audit(
            state,
            event_type,
            "route_error",
            "failed",
            {"task_id": task.task_id, "code": error.code, "attempt": task.attempt},
        )
        if error.retryable and task.attempt < self._config.max_attempts:
            state.pending_task = None
            await self._repository.save(state)
            retry_task = await self._create_task(state, attempt=task.attempt + 1)
            await self._audit(
                state,
                "task.retry_scheduled",
                "route_error",
                "succeeded",
                {"task_id": retry_task.task_id, "attempt": retry_task.attempt},
            )
            return state
        return await self._move(state, RuntimeStage.FAILED, event_type="incident.failed")

    async def _move(
        self,
        state: IncidentState,
        target: RuntimeStage,
        *,
        event_type: str = "stage.transition",
    ) -> IncidentState:
        current = self._stage(state)
        transition_stage(current, target)
        now = await self._clock.now()
        state.runtime_stage = target
        state.status = STAGE_LIFECYCLE_STATUS[target]
        state.pending_task = None
        state.revision += 1
        state.timestamp = now
        state.source = "core-runtime"
        state = await self._repository.save(state)
        await self._audit(
            state,
            event_type,
            "transition_stage",
            "succeeded",
            {"from": current.value, "to": target.value},
        )
        return state

    async def _audit(
        self,
        state: IncidentState,
        event_type: str,
        action: str,
        outcome: str,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        now = await self._clock.now()
        query = self._query_from_contract(state)
        events = await self._repository.list_events(query)
        event = AuditEvent(
            schema_version=state.schema_version,
            incident_id=state.incident_id,
            request_id=state.request_id,
            timestamp=now,
            source="core-runtime",
            metadata={},
            audit_event_id=(
                f"AUD-{self._incident_suffix(state.incident_id)}-{len(events) + 1:04d}"
            ),
            event_type=event_type,
            actor="core-runtime",
            action=action,
            outcome=outcome,
            target_ref=state.pending_task.task_id if state.pending_task else state.incident_id,
            details=details or {},
            previous_event_id=events[-1].audit_event_id if events else None,
        )
        await self._repository.append_event(event)

    async def _runtime_error(
        self,
        state: IncidentState,
        *,
        code: str,
        message: str,
        category: ErrorCategory,
        retryable: bool,
    ) -> ErrorResponse:
        return ErrorResponse(
            schema_version=state.schema_version,
            incident_id=state.incident_id,
            request_id=state.request_id,
            timestamp=await self._clock.now(),
            source="core-runtime",
            metadata={},
            code=code,
            message=message,
            category=category,
            retryable=retryable,
            details={},
        )

    @staticmethod
    def _stage(state: IncidentState) -> RuntimeStage:
        if state.runtime_stage is None:
            raise InvalidStateTransition("incident has no runtime_stage")
        return state.runtime_stage

    @staticmethod
    def _query_from_contract(
        contract: IncidentState | TaskResult | FinishIncidentRequest,
    ) -> IncidentQuery:
        return IncidentQuery(
            schema_version=contract.schema_version,
            incident_id=contract.incident_id,
            request_id=contract.request_id,
            timestamp=contract.timestamp,
            source="core-runtime",
            metadata={},
        )

    @staticmethod
    def _incident_suffix(incident_id: str) -> str:
        return incident_id.removeprefix("INC-")

    @staticmethod
    def _apply_normalize(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.problem is None:
            raise TaskResultMismatch("NORMALIZE requires problem output")
        state.problem = output.problem
        return RuntimeStage.KNOWLEDGE_LOOKUP

    @staticmethod
    def _apply_knowledge_lookup(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.knowledge_lookup is None:
            raise TaskResultMismatch("KNOWLEDGE_LOOKUP requires knowledge_lookup output")
        state.product = output.knowledge_lookup.product
        state.knowledge = output.knowledge_lookup.knowledge
        state.troubleshooting = output.knowledge_lookup.troubleshooting
        return RuntimeStage.HYPOTHESIS

    @staticmethod
    def _apply_hypotheses(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.hypotheses is None:
            raise TaskResultMismatch("HYPOTHESIS requires hypotheses output")
        state.hypotheses = output.hypotheses
        return RuntimeStage.EVIDENCE_PLAN

    @staticmethod
    def _apply_evidence_plan(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.evidence_plan is None:
            raise TaskResultMismatch("EVIDENCE_PLAN requires evidence_plan output")
        state.latest_evidence_plan = output.evidence_plan
        return RuntimeStage.INVESTIGATE

    @staticmethod
    def _apply_investigation(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.evidence_batch is None:
            raise TaskResultMismatch("INVESTIGATE requires evidence_batch output")
        state.evidence.extend(output.evidence_batch.evidence)
        if not output.evidence_batch.evidence:
            return RuntimeStage.REFLECT
        return RuntimeStage.ROOT_CAUSE_ASSESSMENT

    @staticmethod
    def _apply_root_cause_assessment(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.root_cause_assessment is None:
            raise TaskResultMismatch("ROOT_CAUSE_ASSESSMENT requires root_cause_assessment output")
        state.root_cause_assessment = output.root_cause_assessment
        if output.root_cause_assessment.status is RootCauseStatus.UNKNOWN:
            return RuntimeStage.REFLECT
        return RuntimeStage.EXPERIMENT_PLAN

    @staticmethod
    def _apply_experiment_plan(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.experiment_plan is None:
            raise TaskResultMismatch("EXPERIMENT_PLAN requires experiment_plan output")
        state.experiment_plans.append(output.experiment_plan)
        if output.experiment_plan.requires_approval:
            state.resume_stage = RuntimeStage.REPRODUCE
            return RuntimeStage.WAITING_HUMAN
        return RuntimeStage.REPRODUCE

    @staticmethod
    def _apply_reproduction(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.experiment_result is None:
            raise TaskResultMismatch("REPRODUCE requires experiment_result output")
        state.experiment_results.append(output.experiment_result)
        if output.experiment_result.status is not ExperimentStatus.SUCCEEDED:
            return RuntimeStage.REFLECT
        return RuntimeStage.VERIFY

    @staticmethod
    def _apply_verification(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.verification_result is None:
            raise TaskResultMismatch("VERIFY requires verification_result output")
        state.verification_results.append(output.verification_result)
        if output.verification_result.status is VerificationStatus.CONFIRMED:
            return RuntimeStage.RCA
        return RuntimeStage.REFLECT

    def _apply_reflection(self, state: IncidentState, output: TaskOutput) -> RuntimeStage:
        reflection = output.reflection_result
        if reflection is None:
            raise TaskResultMismatch("REFLECT requires reflection_result output")
        state.latest_reflection = reflection
        state.reflection_count += 1
        requested_stage = {
            NextAction.COLLECT_EVIDENCE: RuntimeStage.EVIDENCE_PLAN,
            NextAction.REVISE_HYPOTHESES: RuntimeStage.HYPOTHESIS,
            NextAction.PLAN_EXPERIMENT: RuntimeStage.EXPERIMENT_PLAN,
            NextAction.ASSESS_ROOT_CAUSE: RuntimeStage.ROOT_CAUSE_ASSESSMENT,
            NextAction.REQUEST_HUMAN_INPUT: RuntimeStage.WAITING_HUMAN,
            NextAction.STOP: RuntimeStage.RCA,
        }[reflection.next_action]
        if not reflection.should_continue:
            requested_stage = (
                RuntimeStage.RCA
                if state.root_cause_assessment is not None
                else RuntimeStage.WAITING_HUMAN
            )
        if state.reflection_count >= self._config.max_reflection_loops:
            state.resume_stage = requested_stage
            return RuntimeStage.WAITING_HUMAN
        return requested_stage

    @staticmethod
    def _apply_rca(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        if output.rca_report is None:
            raise TaskResultMismatch("RCA requires rca_report output")
        state.rca_report = output.rca_report
        return RuntimeStage.PERSIST

    @staticmethod
    def _apply_human_decision(state: IncidentState, output: TaskOutput) -> RuntimeStage:
        decision = output.human_decision
        if decision is None:
            raise TaskResultMismatch("WAITING_HUMAN requires human_decision output")
        if not decision.approved:
            return RuntimeStage.FAILED
        target = state.resume_stage
        state.resume_stage = None
        if target is None:
            raise TaskResultMismatch("approved decision has no resume_stage")
        return target
