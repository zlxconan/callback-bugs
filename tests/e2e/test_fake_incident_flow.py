from datetime import UTC, datetime
from pathlib import Path

import pytest

from ops_agent.contracts import (
    IncidentSeverity,
    ProblemContext,
    RuntimeStage,
    StartIncidentRequest,
    VerificationStatus,
)
from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent.fake_runner import (
    FakeIncidentOutcome,
    FakeIncidentRunner,
    FixedClock,
)
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.ports import (
    InvestigationPort,
    KnowledgePort,
    ReasoningPort,
    ReproductionPort,
    StateRepositoryPort,
)
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.adapters import FakeReproductionEngine

NOW = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)
INCIDENT_EXAMPLE = (
    Path(__file__).parents[2] / "examples" / "incidents" / "duplicate-order-timeout-retry.json"
)


def incident_request() -> StartIncidentRequest:
    problem = ProblemContext(
        schema_version="1.0",
        incident_id="INC-DUPLICATE-ORDER-001",
        request_id="REQ-DUPLICATE-ORDER-001",
        timestamp=NOW,
        source="fake-e2e",
        metadata={"case": "duplicate-order-after-timeout"},
        title="创建订单时首次响应超时，客户端重试后产生重复订单",
        description="同一业务标识最终对应两个订单。",
        symptoms=["首次请求响应超时", "客户端自动重试", "最终产生重复订单"],
        severity=IncidentSeverity.HIGH,
        observed_at=NOW,
        affected_services=["order-api"],
        environment={"name": "fake", "external_systems": False},
    )
    return StartIncidentRequest(
        schema_version="1.0",
        incident_id=problem.incident_id,
        request_id=problem.request_id,
        timestamp=NOW,
        source="fake-e2e",
        metadata={},
        problem=problem,
    )


def build_runner(
    *,
    investigation_failures: int = 0,
    reproduction_failures: int = 0,
    empty_investigation_batches: int = 0,
    max_attempts: int = 3,
) -> tuple[FakeIncidentRunner, InMemoryStateRepository]:
    repository = InMemoryStateRepository()
    clock = FixedClock(NOW)
    runtime = CoreRuntime(
        repository=repository,
        clock=clock,
        config=RuntimeConfig(
            max_attempts=max_attempts,
            task_timeout_seconds=30,
            max_reflection_loops=3,
        ),
    )
    knowledge = FakeKnowledgeEngine()
    reasoning = FakeReasoningEngine()
    investigation = FakeInvestigationEngine(
        fail_times=investigation_failures,
        empty_batch_times=empty_investigation_batches,
    )
    reproduction = FakeReproductionEngine(fail_times=reproduction_failures)

    assert isinstance(repository, StateRepositoryPort)
    assert isinstance(knowledge, KnowledgePort)
    assert isinstance(reasoning, ReasoningPort)
    assert isinstance(investigation, InvestigationPort)
    assert isinstance(reproduction, ReproductionPort)

    return (
        FakeIncidentRunner(
            runtime=runtime,
            knowledge=knowledge,
            reasoning=reasoning,
            investigation=investigation,
            reproduction=reproduction,
        ),
        repository,
    )


@pytest.mark.asyncio
async def test_fixed_duplicate_order_case_completes_through_runtime() -> None:
    runner, repository = build_runner()

    outcome = await runner.run(incident_request())

    assert outcome.final_state.runtime_stage is RuntimeStage.COMPLETED
    assert outcome.stage_history == [
        RuntimeStage.CREATED,
        RuntimeStage.NORMALIZE,
        RuntimeStage.KNOWLEDGE_LOOKUP,
        RuntimeStage.HYPOTHESIS,
        RuntimeStage.EVIDENCE_PLAN,
        RuntimeStage.INVESTIGATE,
        RuntimeStage.ROOT_CAUSE_ASSESSMENT,
        RuntimeStage.EXPERIMENT_PLAN,
        RuntimeStage.REPRODUCE,
        RuntimeStage.VERIFY,
        RuntimeStage.RCA,
        RuntimeStage.PERSIST,
        RuntimeStage.COMPLETED,
    ]
    state = outcome.final_state
    assert state.knowledge is not None
    assert "当前版本支持客户端重试。" in state.knowledge.facts
    assert "创建接口非幂等，存在重复创建风险。" in state.knowledge.facts
    assert state.hypotheses is not None
    assert [item.hypothesis_id for item in state.hypotheses.hypotheses] == [
        "H-1",
        "H-2",
        "H-3",
    ]
    assert state.latest_evidence_plan is not None
    assert len(state.evidence) == 4
    assert state.experiment_plans
    assert state.experiment_results[0].outputs["orders_created"] == 2
    assert state.verification_results[0].status is VerificationStatus.CONFIRMED
    assert state.verification_results[0].hypothesis_ids == ["H-1"]
    assert outcome.report is not None
    assert outcome.report.root_causes
    assert outcome.report.evidence_chain
    assert outcome.report.minimal_reproduction_conditions == [
        "创建接口使用相同业务标识",
        "首次请求后端成功但响应延迟超过客户端超时",
        "客户端在超时后自动重试",
        "服务端未实施幂等去重",
    ]
    assert outcome.report.remediation_recommendations
    assert outcome.report.unverified_items
    assert await repository.get(outcome.query) == state


@pytest.mark.asyncio
async def test_fake_investigation_failure_reaches_failed_via_runtime_retry() -> None:
    runner, _ = build_runner(investigation_failures=3, max_attempts=2)

    outcome = await runner.run(incident_request())

    assert outcome.final_state.runtime_stage is RuntimeStage.FAILED
    assert outcome.final_state.last_error is not None
    assert outcome.final_state.last_error.code == "FAKE_ENGINE_FAILURE"
    assert outcome.stage_history.count(RuntimeStage.INVESTIGATE) == 1


@pytest.mark.asyncio
async def test_fake_reproduction_failure_reaches_failed_via_runtime_retry() -> None:
    runner, _ = build_runner(reproduction_failures=3, max_attempts=2)

    outcome = await runner.run(incident_request())

    assert outcome.final_state.runtime_stage is RuntimeStage.FAILED
    assert outcome.final_state.last_error is not None
    assert outcome.final_state.last_error.code == "FAKE_ENGINE_FAILURE"
    assert RuntimeStage.REPRODUCE in outcome.stage_history


@pytest.mark.asyncio
async def test_insufficient_evidence_reflects_then_reenters_and_completes() -> None:
    runner, _ = build_runner(empty_investigation_batches=1)

    outcome = await runner.run(incident_request())

    assert outcome.final_state.runtime_stage is RuntimeStage.COMPLETED
    assert RuntimeStage.REFLECT in outcome.stage_history
    assert outcome.stage_history.count(RuntimeStage.EVIDENCE_PLAN) == 2
    assert outcome.stage_history.count(RuntimeStage.INVESTIGATE) == 2
    assert outcome.final_state.reflection_count == 1


@pytest.mark.asyncio
async def test_saved_incident_flow_matches_runtime_output() -> None:
    runner, _ = build_runner()
    actual = await runner.run(incident_request())

    saved = FakeIncidentOutcome.model_validate_json(INCIDENT_EXAMPLE.read_text(encoding="utf-8"))

    assert saved == actual
