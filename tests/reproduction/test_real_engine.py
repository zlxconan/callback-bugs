from __future__ import annotations

from dataclasses import dataclass

import pytest

from ops_agent.contracts import (
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentPlan,
    ExperimentVerificationRequest,
    IncidentState,
    PreparedEnvironment,
    VerificationStatus,
)
from ops_agent.integrations.mcp.fake import (
    FakeApiTool,
    FakeBrowserTool,
    FakeFaultInjectionTool,
    FakeShellTool,
)
from ops_agent.ports import ReproductionPort
from ops_agent.reproduction.domain import (
    ReproductionConfig,
    ReproductionPolicyError,
    ReproductionTimeoutError,
)
from ops_agent.reproduction.service import RealReproductionEngine


@dataclass
class EngineFixture:
    engine: RealReproductionEngine
    browser: FakeBrowserTool
    api: FakeApiTool
    fault: FakeFaultInjectionTool
    shell: FakeShellTool


def build_engine(
    *,
    browser: FakeBrowserTool | None = None,
    api: FakeApiTool | None = None,
    fault: FakeFaultInjectionTool | None = None,
    timeout: float = 1.0,
) -> EngineFixture:
    browser = browser or FakeBrowserTool()
    api = api or FakeApiTool()
    fault = fault or FakeFaultInjectionTool()
    shell = FakeShellTool()
    engine = RealReproductionEngine(
        browser=browser,
        api=api,
        shell=shell,
        fault=fault,
        config=ReproductionConfig(tool_timeout_seconds=timeout),
    )
    return EngineFixture(engine, browser, api, fault, shell)


def execution_request(
    plan: ExperimentPlan,
    environment: PreparedEnvironment,
) -> ExperimentExecutionRequest:
    return ExperimentExecutionRequest(
        **plan.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="real-reproduction-test",
        plan=plan,
        environment=environment,
    )


def cleanup_request(request: ExperimentExecutionRequest) -> EnvironmentCleanupRequest:
    return EnvironmentCleanupRequest(
        **request.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="real-reproduction-test",
        experiment_id=request.plan.experiment_id,
        environment_ref=request.environment.environment_ref,
    )


@pytest.mark.asyncio
async def test_complete_lifecycle_is_deterministic_and_implements_port(
    fake_incident_state: IncidentState,
) -> None:
    state = fake_incident_state
    plan = state.experiment_plans[0]
    fixture = build_engine()

    environment = await fixture.engine.prepare(plan)
    request = execution_request(plan, environment)
    result = await fixture.engine.execute(request)
    verification = await fixture.engine.verify(
        ExperimentVerificationRequest(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="real-reproduction-test",
            plan=plan,
            result=result,
            evidence=state.evidence,
        )
    )
    second_cleanup = await fixture.engine.cleanup(cleanup_request(request))

    assert isinstance(fixture.engine, ReproductionPort)
    assert environment.ready
    assert result.outputs["orders_created"] == 2
    assert verification.status is VerificationStatus.CONFIRMED
    assert len(verification.confirmed_claims) == 4
    assert verification.rejected_claims == []
    assert verification.evidence_ids == ["E-1", "E-2", "E-3", "E-4"]
    assert "all 4 criteria matched" in verification.rationale
    assert second_cleanup.cleaned
    assert fixture.fault.rollback_calls == 1
    assert fixture.api.execute_calls == 2


@pytest.mark.asyncio
async def test_prepare_failure_runs_cleanup(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine(api=FakeApiTool(fail_on_calls={1}))

    with pytest.raises(RuntimeError, match="configured Fake API failure"):
        await fixture.engine.prepare(plan)

    assert fixture.fault.rollback_calls == 1
    assert fixture.engine.cleanup_manager.attempt_count == 1


@pytest.mark.asyncio
async def test_prepare_can_retry_after_failed_attempt(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine(api=FakeApiTool(fail_on_calls={1}))

    with pytest.raises(RuntimeError):
        await fixture.engine.prepare(plan)
    environment = await fixture.engine.prepare(plan)
    request = execution_request(plan, environment)
    await fixture.engine.execute(request)
    await fixture.engine.cleanup(cleanup_request(request))

    assert fixture.fault.rollback_calls == 2


@pytest.mark.asyncio
async def test_fault_injection_failure_runs_cleanup(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine(fault=FakeFaultInjectionTool(fail_apply=True))
    environment = await fixture.engine.prepare(plan)

    with pytest.raises(RuntimeError, match="configured Fake fault injection failure"):
        await fixture.engine.execute(execution_request(plan, environment))

    assert fixture.fault.rollback_calls == 1


@pytest.mark.asyncio
async def test_browser_failure_runs_cleanup(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine(browser=FakeBrowserTool(fail=True))
    environment = await fixture.engine.prepare(plan)

    with pytest.raises(RuntimeError, match="configured Fake browser failure"):
        await fixture.engine.execute(execution_request(plan, environment))

    assert fixture.fault.rollback_calls == 1


@pytest.mark.asyncio
async def test_execute_api_failure_runs_cleanup(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine(api=FakeApiTool(fail_on_calls={2}))
    environment = await fixture.engine.prepare(plan)

    with pytest.raises(RuntimeError, match="configured Fake API failure"):
        await fixture.engine.execute(execution_request(plan, environment))

    assert fixture.fault.rollback_calls == 1


@pytest.mark.asyncio
async def test_failed_verification_is_structured_and_runs_cleanup(
    fake_incident_state: IncidentState,
) -> None:
    state = fake_incident_state
    plan = state.experiment_plans[0]
    fixture = build_engine(api=FakeApiTool(database_record_count=1))
    environment = await fixture.engine.prepare(plan)
    request = execution_request(plan, environment)
    result = await fixture.engine.execute(request)

    verification = await fixture.engine.verify(
        ExperimentVerificationRequest(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="real-reproduction-test",
            plan=plan,
            result=result,
            evidence=state.evidence,
        )
    )

    assert verification.status is VerificationStatus.REJECTED
    assert verification.confirmed_claims
    assert verification.rejected_claims == ["database record count == 2"]
    assert "1 of 4 criteria unmatched" in verification.rationale
    assert fixture.fault.rollback_calls == 1


@pytest.mark.asyncio
async def test_verifier_exception_still_runs_cleanup(fake_incident_state: IncidentState) -> None:
    state = fake_incident_state
    plan = state.experiment_plans[0]
    fixture = build_engine()
    environment = await fixture.engine.prepare(plan)
    request = execution_request(plan, environment)
    result = (await fixture.engine.execute(request)).model_copy(update={"evidence_ids": []})

    with pytest.raises(ValueError):
        await fixture.engine.verify(
            ExperimentVerificationRequest(
                **request.model_dump(
                    include={"schema_version", "incident_id", "request_id", "timestamp"}
                ),
                source="real-reproduction-test",
                plan=plan,
                result=result,
                evidence=state.evidence,
            )
        )

    assert fixture.fault.rollback_calls == 1


@pytest.mark.asyncio
async def test_cleanup_is_idempotent(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine()
    environment = await fixture.engine.prepare(plan)
    request = execution_request(plan, environment)

    first = await fixture.engine.cleanup(cleanup_request(request))
    second = await fixture.engine.cleanup(cleanup_request(request))

    assert first.cleaned and second.cleaned
    assert fixture.fault.rollback_calls == 1
    assert "already cleaned" in second.observations[0]


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_mask_original_error(
    fake_incident_state: IncidentState,
) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine(fault=FakeFaultInjectionTool(fail_apply=True, fail_rollback=True))
    environment = await fixture.engine.prepare(plan)

    with pytest.raises(RuntimeError, match="configured Fake fault injection failure"):
        await fixture.engine.execute(execution_request(plan, environment))

    assert fixture.engine.cleanup_manager.failures
    assert "configured Fake rollback failure" in fixture.engine.cleanup_manager.failures[-1]


@pytest.mark.asyncio
async def test_tool_timeout_runs_cleanup(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine(browser=FakeBrowserTool(delay_seconds=0.05), timeout=0.001)
    environment = await fixture.engine.prepare(plan)

    with pytest.raises(ReproductionTimeoutError):
        await fixture.engine.execute(execution_request(plan, environment))

    assert fixture.fault.rollback_calls == 1


@pytest.mark.asyncio
async def test_production_environment_is_rejected_before_side_effects(
    fake_incident_state: IncidentState,
) -> None:
    plan = fake_incident_state.experiment_plans[0].model_copy(
        update={"environment": {"kind": "production", "external_systems": True}}
    )
    fixture = build_engine()

    with pytest.raises(ReproductionPolicyError, match="production"):
        await fixture.engine.prepare(plan)

    assert fixture.api.execute_calls == 0
    assert fixture.fault.apply_calls == 0
    assert fixture.browser.execute_calls == 0


@pytest.mark.asyncio
async def test_experiment_result_contract_round_trip(fake_incident_state: IncidentState) -> None:
    plan = fake_incident_state.experiment_plans[0]
    fixture = build_engine()
    environment = await fixture.engine.prepare(plan)
    result = await fixture.engine.execute(execution_request(plan, environment))

    assert result == type(result).model_validate_json(result.model_dump_json())
    assert result.experiment_id == plan.experiment_id
    assert result.status == "succeeded"
