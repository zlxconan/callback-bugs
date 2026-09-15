from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from ops_agent.contracts import (
    AuditEvent,
    ErrorCategory,
    ErrorResponse,
    Evidence,
    EvidenceBatch,
    EvidencePlan,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    HumanDecision,
    HypothesisSet,
    IncidentQuery,
    IncidentState,
    KnowledgeContext,
    KnowledgeLookupResult,
    NextAction,
    ProblemContext,
    ProductContext,
    RCAReport,
    ReflectionResult,
    RootCauseAssessment,
    RuntimeStage,
    RuntimeTask,
    StartIncidentRequest,
    TaskOutput,
    TaskResult,
    TaskStatus,
    TroubleshootingContext,
    VerificationResult,
    VerificationStatus,
)
from ops_agent.core.runtime import (
    STATE_TRANSITIONS,
    CoreRuntime,
    InvalidStateTransition,
    RuntimeConfig,
    TerminalIncidentError,
    transition_stage,
)

T = TypeVar("T", bound=BaseModel)
EXAMPLES = Path(__file__).parents[2] / "examples" / "contracts"
NOW = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)


def load_example(model: type[T], filename: str) -> T:
    return model.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


class ManualClock:
    def __init__(self, current: datetime = NOW) -> None:
        self.current = current

    async def now(self) -> datetime:
        return self.current

    def advance(self, *, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


class FakeStateRepository:
    def __init__(self) -> None:
        self.states: dict[str, IncidentState] = {}
        self.events: dict[str, list[AuditEvent]] = {}

    async def create(self, state: IncidentState) -> IncidentState:
        self.states[state.incident_id] = state.model_copy(deep=True)
        self.events[state.incident_id] = []
        return state.model_copy(deep=True)

    async def get(self, query: IncidentQuery) -> IncidentState | None:
        state = self.states.get(query.incident_id)
        return state.model_copy(deep=True) if state else None

    async def save(self, state: IncidentState) -> IncidentState:
        self.states[state.incident_id] = state.model_copy(deep=True)
        return state.model_copy(deep=True)

    async def list_events(self, query: IncidentQuery) -> tuple[AuditEvent, ...]:
        return tuple(self.events.get(query.incident_id, []))

    async def append_event(self, event: AuditEvent) -> AuditEvent:
        self.events.setdefault(event.incident_id, []).append(event.model_copy(deep=True))
        return event.model_copy(deep=True)


def common(source: str = "test") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "incident_id": "INC-1001",
        "request_id": "REQ-1001",
        "timestamp": NOW,
        "source": source,
        "metadata": {},
    }


async def started_runtime(
    *,
    max_attempts: int = 3,
    task_timeout_seconds: float = 30.0,
    max_reflection_loops: int = 2,
) -> tuple[CoreRuntime, FakeStateRepository, ManualClock, IncidentState]:
    repository = FakeStateRepository()
    clock = ManualClock()
    runtime = CoreRuntime(
        repository=repository,
        clock=clock,
        config=RuntimeConfig(
            max_attempts=max_attempts,
            task_timeout_seconds=task_timeout_seconds,
            max_reflection_loops=max_reflection_loops,
        ),
    )
    problem = load_example(ProblemContext, "problem-context.json")
    state = await runtime.start_incident(StartIncidentRequest(**common(), problem=problem))
    return runtime, repository, clock, state


def query(source: str = "test") -> IncidentQuery:
    return IncidentQuery(**common(source))


def successful_result(task: RuntimeTask, output: TaskOutput) -> TaskResult:
    return TaskResult(
        schema_version="1.0",
        incident_id=task.incident_id,
        request_id=task.request_id,
        timestamp=NOW,
        source="fake-agent",
        metadata={},
        task_id=task.task_id,
        status=TaskStatus.SUCCEEDED,
        output={},
        typed_output=output,
        evidence_ids=[],
        error=None,
        started_at=NOW,
        completed_at=NOW,
    )


def failed_result(task: RuntimeTask, *, retryable: bool) -> TaskResult:
    error = ErrorResponse(
        schema_version="1.0",
        incident_id=task.incident_id,
        request_id=task.request_id,
        timestamp=NOW,
        source="fake-agent",
        metadata={},
        code="ENGINE_FAILURE",
        message="The delegated engine failed.",
        category=ErrorCategory.TRANSIENT if retryable else ErrorCategory.TERMINAL,
        retryable=retryable,
        details={},
    )
    return TaskResult(
        schema_version="1.0",
        incident_id=task.incident_id,
        request_id=task.request_id,
        timestamp=NOW,
        source="fake-agent",
        metadata={},
        task_id=task.task_id,
        status=TaskStatus.FAILED,
        output={},
        typed_output=None,
        evidence_ids=[],
        error=error,
        started_at=NOW,
        completed_at=NOW,
    )


async def submit_for_stage(
    runtime: CoreRuntime,
    expected_stage: RuntimeStage,
    output: TaskOutput,
) -> IncidentState:
    task = await runtime.get_next_task(query())
    assert task is not None
    assert task.stage is expected_stage
    return await runtime.submit_task_result(successful_result(task, output))


async def advance_to_investigation(runtime: CoreRuntime) -> None:
    problem = load_example(ProblemContext, "problem-context.json")
    product = load_example(ProductContext, "product-context.json")
    knowledge = load_example(KnowledgeContext, "knowledge-context.json")
    troubleshooting = load_example(TroubleshootingContext, "troubleshooting-context.json")
    hypotheses = load_example(HypothesisSet, "hypothesis-set.json")
    evidence_plan = load_example(EvidencePlan, "evidence-plan.json")

    await submit_for_stage(runtime, RuntimeStage.NORMALIZE, TaskOutput(problem=problem))
    await submit_for_stage(
        runtime,
        RuntimeStage.KNOWLEDGE_LOOKUP,
        TaskOutput(
            knowledge_lookup=KnowledgeLookupResult(
                product=product,
                knowledge=knowledge,
                troubleshooting=troubleshooting,
            )
        ),
    )
    await submit_for_stage(
        runtime,
        RuntimeStage.HYPOTHESIS,
        TaskOutput(hypotheses=hypotheses),
    )
    await submit_for_stage(
        runtime,
        RuntimeStage.EVIDENCE_PLAN,
        TaskOutput(evidence_plan=evidence_plan),
    )


async def advance_to_experiment_plan(runtime: CoreRuntime) -> None:
    await advance_to_investigation(runtime)
    evidence = load_example(Evidence, "evidence.json")
    assessment = load_example(RootCauseAssessment, "root-cause-assessment.json")
    await submit_for_stage(
        runtime,
        RuntimeStage.INVESTIGATE,
        TaskOutput(evidence_batch=EvidenceBatch(**common(), evidence=[evidence])),
    )
    await submit_for_stage(
        runtime,
        RuntimeStage.ROOT_CAUSE_ASSESSMENT,
        TaskOutput(root_cause_assessment=assessment),
    )


@pytest.mark.asyncio
async def test_normal_complete_external_agent_flow() -> None:
    runtime, repository, _, state = await started_runtime()
    assert state.runtime_stage is RuntimeStage.CREATED

    await advance_to_experiment_plan(runtime)
    experiment_plan = load_example(ExperimentPlan, "experiment-plan.json")
    experiment_result = load_example(ExperimentResult, "experiment-result.json")
    verification = load_example(VerificationResult, "verification-result.json")
    report = load_example(RCAReport, "rca-report.json")

    await submit_for_stage(
        runtime,
        RuntimeStage.EXPERIMENT_PLAN,
        TaskOutput(experiment_plan=experiment_plan),
    )
    await submit_for_stage(
        runtime,
        RuntimeStage.REPRODUCE,
        TaskOutput(experiment_result=experiment_result),
    )
    await submit_for_stage(
        runtime,
        RuntimeStage.VERIFY,
        TaskOutput(verification_result=verification),
    )
    state = await submit_for_stage(
        runtime,
        RuntimeStage.RCA,
        TaskOutput(rca_report=report),
    )
    assert state.runtime_stage is RuntimeStage.PERSIST

    assert await runtime.get_next_task(query()) is None
    completed = await runtime.get_state(query())
    assert completed.runtime_stage is RuntimeStage.COMPLETED
    assert completed.rca_report == report

    events = await repository.list_events(query())
    event_types = [event.event_type for event in events]
    assert event_types[0] == "incident.created"
    assert "task.created" in event_types
    assert "task.accepted" in event_types
    assert "incident.completed" in event_types


def test_transition_table_is_explicit_and_rejects_illegal_jump() -> None:
    assert STATE_TRANSITIONS[RuntimeStage.CREATED] == frozenset(
        {RuntimeStage.NORMALIZE, RuntimeStage.FAILED}
    )
    assert transition_stage(RuntimeStage.CREATED, RuntimeStage.NORMALIZE) is RuntimeStage.NORMALIZE

    with pytest.raises(InvalidStateTransition):
        transition_stage(RuntimeStage.CREATED, RuntimeStage.VERIFY)


@pytest.mark.asyncio
async def test_non_retryable_engine_failure_routes_to_failed() -> None:
    runtime, _, _, _ = await started_runtime()
    task = await runtime.get_next_task(query())
    assert task is not None

    state = await runtime.submit_task_result(failed_result(task, retryable=False))

    assert state.runtime_stage is RuntimeStage.FAILED
    assert state.last_error is not None
    assert await runtime.get_next_task(query()) is None


@pytest.mark.asyncio
async def test_retryable_failure_creates_next_attempt() -> None:
    runtime, _, _, _ = await started_runtime(max_attempts=2)
    first = await runtime.get_next_task(query())
    assert first is not None

    state = await runtime.submit_task_result(failed_result(first, retryable=True))
    second = await runtime.get_next_task(query())

    assert state.runtime_stage is RuntimeStage.NORMALIZE
    assert second is not None
    assert second.attempt == 2
    assert second.task_id != first.task_id


@pytest.mark.asyncio
async def test_retry_limit_routes_to_failed() -> None:
    runtime, _, _, _ = await started_runtime(max_attempts=2)
    first = await runtime.get_next_task(query())
    assert first is not None
    await runtime.submit_task_result(failed_result(first, retryable=True))
    second = await runtime.get_next_task(query())
    assert second is not None

    state = await runtime.submit_task_result(failed_result(second, retryable=True))

    assert state.runtime_stage is RuntimeStage.FAILED
    assert state.pending_task is None


@pytest.mark.asyncio
async def test_timeout_routes_through_failure_policy() -> None:
    runtime, repository, clock, _ = await started_runtime(
        max_attempts=1,
        task_timeout_seconds=5,
    )
    task = await runtime.get_next_task(query())
    assert task is not None
    clock.advance(seconds=6)

    assert await runtime.get_next_task(query()) is None
    state = await runtime.get_state(query())
    events = await repository.list_events(query())

    assert state.runtime_stage is RuntimeStage.FAILED
    assert state.last_error is not None
    assert state.last_error.category is ErrorCategory.TIMEOUT
    assert any(event.event_type == "task.timed_out" for event in events)


@pytest.mark.asyncio
async def test_late_submission_uses_runtime_clock_not_caller_timestamp() -> None:
    runtime, _, clock, _ = await started_runtime(
        max_attempts=1,
        task_timeout_seconds=5,
    )
    task = await runtime.get_next_task(query())
    assert task is not None
    clock.advance(seconds=6)

    result = successful_result(
        task,
        TaskOutput(problem=load_example(ProblemContext, "problem-context.json")),
    )
    state = await runtime.submit_task_result(result)

    assert state.runtime_stage is RuntimeStage.FAILED
    assert state.last_error is not None
    assert state.last_error.code == "TASK_TIMEOUT"


@pytest.mark.asyncio
async def test_insufficient_evidence_routes_to_reflection() -> None:
    runtime, _, _, _ = await started_runtime()
    await advance_to_investigation(runtime)

    state = await submit_for_stage(
        runtime,
        RuntimeStage.INVESTIGATE,
        TaskOutput(evidence_batch=EvidenceBatch(**common(), evidence=[])),
    )

    assert state.runtime_stage is RuntimeStage.REFLECT


@pytest.mark.asyncio
async def test_reflection_routes_using_structured_next_action() -> None:
    runtime, _, _, _ = await started_runtime()
    await advance_to_investigation(runtime)
    await submit_for_stage(
        runtime,
        RuntimeStage.INVESTIGATE,
        TaskOutput(evidence_batch=EvidenceBatch(**common(), evidence=[])),
    )
    reflection = load_example(ReflectionResult, "reflection-result.json").model_copy(
        update={"next_action": NextAction.COLLECT_EVIDENCE}
    )

    state = await submit_for_stage(
        runtime,
        RuntimeStage.REFLECT,
        TaskOutput(reflection_result=reflection),
    )

    assert state.runtime_stage is RuntimeStage.EVIDENCE_PLAN
    assert state.reflection_count == 1


@pytest.mark.asyncio
async def test_reflection_limit_requires_human_intervention() -> None:
    runtime, _, _, _ = await started_runtime(max_reflection_loops=1)
    await advance_to_investigation(runtime)
    await submit_for_stage(
        runtime,
        RuntimeStage.INVESTIGATE,
        TaskOutput(evidence_batch=EvidenceBatch(**common(), evidence=[])),
    )
    reflection = load_example(ReflectionResult, "reflection-result.json").model_copy(
        update={"next_action": NextAction.COLLECT_EVIDENCE, "should_continue": True}
    )

    state = await submit_for_stage(
        runtime,
        RuntimeStage.REFLECT,
        TaskOutput(reflection_result=reflection),
    )

    assert state.runtime_stage is RuntimeStage.WAITING_HUMAN


@pytest.mark.asyncio
async def test_failed_experiment_routes_to_reflection() -> None:
    runtime, _, _, _ = await started_runtime()
    await advance_to_experiment_plan(runtime)
    plan = load_example(ExperimentPlan, "experiment-plan.json")
    await submit_for_stage(
        runtime,
        RuntimeStage.EXPERIMENT_PLAN,
        TaskOutput(experiment_plan=plan),
    )
    failed_experiment = load_example(ExperimentResult, "experiment-result.json").model_copy(
        update={"status": ExperimentStatus.FAILED}
    )

    state = await submit_for_stage(
        runtime,
        RuntimeStage.REPRODUCE,
        TaskOutput(experiment_result=failed_experiment),
    )

    assert state.runtime_stage is RuntimeStage.REFLECT


@pytest.mark.asyncio
async def test_experiment_requiring_approval_waits_for_human() -> None:
    runtime, _, _, _ = await started_runtime()
    await advance_to_experiment_plan(runtime)
    plan = load_example(ExperimentPlan, "experiment-plan.json").model_copy(
        update={"requires_approval": True}
    )

    state = await submit_for_stage(
        runtime,
        RuntimeStage.EXPERIMENT_PLAN,
        TaskOutput(experiment_plan=plan),
    )
    assert state.runtime_stage is RuntimeStage.WAITING_HUMAN

    approval_task = await runtime.get_next_task(query())
    assert approval_task is not None
    decision = HumanDecision(approved=True, decided_by="on-call", reason="Isolated environment")
    state = await runtime.submit_task_result(
        successful_result(approval_task, TaskOutput(human_decision=decision))
    )

    assert state.runtime_stage is RuntimeStage.REPRODUCE


@pytest.mark.asyncio
async def test_inconclusive_verification_routes_to_reflection() -> None:
    runtime, _, _, _ = await started_runtime()
    await advance_to_experiment_plan(runtime)
    plan = load_example(ExperimentPlan, "experiment-plan.json")
    result = load_example(ExperimentResult, "experiment-result.json")
    await submit_for_stage(
        runtime,
        RuntimeStage.EXPERIMENT_PLAN,
        TaskOutput(experiment_plan=plan),
    )
    await submit_for_stage(
        runtime,
        RuntimeStage.REPRODUCE,
        TaskOutput(experiment_result=result),
    )
    verification = load_example(VerificationResult, "verification-result.json").model_copy(
        update={"status": VerificationStatus.INCONCLUSIVE}
    )

    state = await submit_for_stage(
        runtime,
        RuntimeStage.VERIFY,
        TaskOutput(verification_result=verification),
    )

    assert state.runtime_stage is RuntimeStage.REFLECT


@pytest.mark.asyncio
async def test_completed_incident_cannot_accept_more_execution() -> None:
    runtime, _, _, _ = await started_runtime()
    await advance_to_experiment_plan(runtime)
    plan = load_example(ExperimentPlan, "experiment-plan.json")
    result = load_example(ExperimentResult, "experiment-result.json")
    verification = load_example(VerificationResult, "verification-result.json")
    report = load_example(RCAReport, "rca-report.json")
    await submit_for_stage(runtime, RuntimeStage.EXPERIMENT_PLAN, TaskOutput(experiment_plan=plan))
    await submit_for_stage(runtime, RuntimeStage.REPRODUCE, TaskOutput(experiment_result=result))
    await submit_for_stage(
        runtime, RuntimeStage.VERIFY, TaskOutput(verification_result=verification)
    )
    await submit_for_stage(runtime, RuntimeStage.RCA, TaskOutput(rca_report=report))
    await runtime.get_next_task(query())

    assert await runtime.get_next_task(query()) is None
    stale_task = RuntimeTask.model_validate_json(
        (EXAMPLES / "runtime-task.json").read_text(encoding="utf-8")
    )
    stale_result = successful_result(
        stale_task, TaskOutput(problem=load_example(ProblemContext, "problem-context.json"))
    )
    with pytest.raises(TerminalIncidentError):
        await runtime.submit_task_result(stale_result)
