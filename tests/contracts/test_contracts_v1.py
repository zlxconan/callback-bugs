from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from ops_agent.contracts import (
    AuditEvent,
    ErrorCategory,
    ErrorResponse,
    Evidence,
    EvidenceAcquisitionStatus,
    EvidenceBackedClaim,
    EvidenceChainLink,
    EvidencePlan,
    EvidenceRelationship,
    EvidenceRequest,
    EvidenceType,
    ExperimentPlan,
    ExperimentResult,
    ExperimentStatus,
    ExperimentStep,
    Hypothesis,
    HypothesisSet,
    HypothesisStatus,
    IncidentLifecycleStatus,
    IncidentSeverity,
    IncidentState,
    KnowledgeContext,
    NextAction,
    ProblemContext,
    ProductContext,
    RawReference,
    RCAReport,
    ReflectionResult,
    RemediationRecommendation,
    RootCause,
    RootCauseAssessment,
    RootCauseStatus,
    RuntimeTask,
    TaskKind,
    TaskResult,
    TaskStatus,
    TroubleshootingContext,
    VerificationResult,
    VerificationStatus,
)

NOW = datetime(2026, 9, 15, 6, 0, tzinfo=UTC)
COMMON: dict[str, Any] = {
    "schema_version": "1.0",
    "incident_id": "INC-1001",
    "request_id": "REQ-1001",
    "timestamp": NOW,
    "source": "contract-test",
    "metadata": {"tenant": "demo"},
}


def problem_context() -> ProblemContext:
    return ProblemContext(
        **COMMON,
        title="Checkout requests time out",
        description="Requests exceed the expected latency budget.",
        symptoms=["HTTP 504"],
        severity=IncidentSeverity.HIGH,
        observed_at=NOW,
        affected_services=["checkout-api"],
        environment={"cluster": "prod-a"},
    )


def product_context() -> ProductContext:
    return ProductContext(
        **COMMON,
        product_name="Commerce Platform",
        product_version="2026.09.1",
        component="checkout-api",
        deployment_environment="production",
        expected_behavior="Requests complete within 500 ms.",
        configuration={"timeout_ms": 500},
    )


def hypothesis() -> Hypothesis:
    return Hypothesis(
        **COMMON,
        hypothesis_id="H-1001",
        fact=["Timeouts started after a deployment."],
        inference="The new connection pool configuration may be exhausted.",
        assumption=["Traffic shape did not materially change."],
        confidence=0.7,
        supporting_evidence=["E-1001"],
        contradicting_evidence=[],
        missing_evidence=["REQ-1002"],
        status=HypothesisStatus.TESTING,
    )


def evidence() -> Evidence:
    return Evidence(
        **COMMON,
        evidence_id="E-1001",
        evidence_type=EvidenceType.METRIC,
        raw_reference=RawReference(
            uri="metrics://prod-a/checkout/pool_waiters",
            digest="sha256:abc123",
            media_type="application/json",
        ),
        structured_value={"pool_waiters": 42},
        observed_at=NOW,
        supports_hypotheses=["H-1001"],
        contradicts_hypotheses=[],
        confidence=0.95,
        acquisition_status=EvidenceAcquisitionStatus.ACQUIRED,
    )


def experiment_plan() -> ExperimentPlan:
    return ExperimentPlan(
        **COMMON,
        experiment_id="EXP-1001",
        title="Reproduce connection pool exhaustion",
        objective="Verify that the new pool limit produces the timeout pattern.",
        hypothesis_ids=["H-1001"],
        environment={"kind": "isolated", "version": "2026.09.1"},
        steps=[
            ExperimentStep(
                step_number=1,
                action="Apply the candidate pool limit and replay load.",
                expected_outcome="Pool waiters rise before HTTP 504 responses.",
            )
        ],
        success_criteria=["HTTP 504 and pool waiter signals correlate."],
        rollback_steps=["Destroy the isolated environment."],
        risk_level="low",
        requires_approval=False,
    )


def root_cause() -> RootCause:
    return RootCause(
        description="The deployed pool limit is too low for normal concurrency.",
        confidence=0.98,
        hypothesis_ids=["H-1001"],
        evidence_ids=["E-1001"],
    )


def test_all_required_core_contracts_are_pydantic_models() -> None:
    models: list[type[BaseModel]] = [
        ProblemContext,
        ProductContext,
        KnowledgeContext,
        TroubleshootingContext,
        Hypothesis,
        HypothesisSet,
        EvidenceRequest,
        EvidencePlan,
        Evidence,
        ExperimentPlan,
        ExperimentResult,
        VerificationResult,
        ReflectionResult,
        RootCauseAssessment,
        IncidentState,
        RuntimeTask,
        TaskResult,
        RCAReport,
        ErrorResponse,
        AuditEvent,
    ]

    assert len(models) == 20
    assert all(issubclass(model, BaseModel) for model in models)
    assert all("schema_version" in model.model_json_schema()["properties"] for model in models)


def test_required_fields_and_unknown_fields_are_rejected() -> None:
    data = problem_context().model_dump()
    del data["incident_id"]

    with pytest.raises(ValidationError):
        ProblemContext.model_validate(data)

    data = problem_context().model_dump()
    data["unexpected"] = True
    with pytest.raises(ValidationError):
        ProblemContext.model_validate(data)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, 10])
def test_invalid_confidence_is_rejected(confidence: float) -> None:
    data = hypothesis().model_dump()
    data["confidence"] = confidence

    with pytest.raises(ValidationError):
        Hypothesis.model_validate(data)


@pytest.mark.parametrize(
    ("model", "field", "bad_value"),
    [
        (ProblemContext, "incident_id", "1001"),
        (ProblemContext, "request_id", "request-1001"),
        (Hypothesis, "hypothesis_id", "hyp-1001"),
        (Evidence, "evidence_id", "evidence-1001"),
        (ExperimentPlan, "experiment_id", "experiment-1001"),
    ],
)
def test_id_formats_are_enforced(
    model: type[BaseModel],
    field: str,
    bad_value: str,
) -> None:
    samples: dict[type[BaseModel], BaseModel] = {
        ProblemContext: problem_context(),
        Hypothesis: hypothesis(),
        Evidence: evidence(),
        ExperimentPlan: experiment_plan(),
    }
    data = samples[model].model_dump()
    data[field] = bad_value

    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_enums_reject_unknown_values() -> None:
    data = hypothesis().model_dump()
    data["status"] = "maybe"

    with pytest.raises(ValidationError):
        Hypothesis.model_validate(data)


def test_json_round_trip_preserves_contract() -> None:
    original = evidence()

    restored = Evidence.model_validate_json(original.model_dump_json())

    assert restored == original
    assert restored.model_dump(mode="json")["timestamp"] == "2026-09-15T06:00:00Z"


def test_schema_version_is_frozen_to_v1() -> None:
    assert hypothesis().schema_version == "1.0"
    data = hypothesis().model_dump()
    data["schema_version"] = "2.0"

    with pytest.raises(ValidationError):
        Hypothesis.model_validate(data)


def test_evidence_references_hypotheses_without_overlap() -> None:
    item = evidence()

    assert item.raw_reference.uri.startswith("metrics://")
    assert item.supports_hypotheses == ["H-1001"]

    data = item.model_dump()
    data["contradicts_hypotheses"] = ["H-1001"]
    with pytest.raises(ValidationError):
        Evidence.model_validate(data)


def test_hypothesis_set_references_only_contained_hypotheses() -> None:
    item = hypothesis()
    hypothesis_set = HypothesisSet(
        **COMMON,
        hypotheses=[item],
        prioritized_hypothesis_ids=["H-1001"],
        selection_rationale="Most consistent with available evidence.",
    )

    assert hypothesis_set.hypotheses[0].missing_evidence == ["REQ-1002"]

    data = hypothesis_set.model_dump()
    data["prioritized_hypothesis_ids"] = ["H-9999"]
    with pytest.raises(ValidationError):
        HypothesisSet.model_validate(data)


def test_evidence_plan_contains_typed_requests() -> None:
    request = EvidenceRequest(
        **COMMON,
        hypothesis_ids=["H-1001"],
        evidence_type=EvidenceType.LOG,
        description="Collect connection pool timeout logs.",
        query="service=checkout-api level=error",
        acquisition_method="logs.search",
        priority=1,
        required=True,
    )
    plan = EvidencePlan(
        **COMMON,
        objective="Confirm or falsify pool exhaustion.",
        requests=[request],
        completion_criteria=["Required evidence request has a terminal status."],
    )

    assert plan.requests[0].request_id == "REQ-1001"


def test_experiment_plan_is_structured_and_serializable() -> None:
    plan = experiment_plan()

    schema = ExperimentPlan.model_json_schema()

    assert plan.steps[0].step_number == 1
    assert plan.hypothesis_ids == ["H-1001"]
    assert "steps" in schema["required"]


def test_rca_report_keeps_claim_categories_separate() -> None:
    report = RCAReport(
        **COMMON,
        report_id="RCA-1001",
        title="Checkout timeout RCA",
        executive_summary="A low connection pool limit caused request timeouts.",
        confirmed_facts=[
            EvidenceBackedClaim(statement="Pool waiters reached 42.", evidence_ids=["E-1001"])
        ],
        inferences=[
            EvidenceBackedClaim(
                statement="The deployment introduced the limiting configuration.",
                evidence_ids=["E-1001"],
            )
        ],
        root_causes=[root_cause()],
        remediation_recommendations=[
            RemediationRecommendation(
                action="Restore the reviewed connection pool limit.",
                rationale="Removes the reproduced bottleneck.",
                priority=1,
            )
        ],
        unverified_items=["Behavior under peak seasonal load remains unverified."],
        evidence_chain=[
            EvidenceChainLink(
                evidence_id="E-1001",
                relationship=EvidenceRelationship.SUPPORTS,
                target_id="H-1001",
            )
        ],
    )

    dumped = report.model_dump(mode="json")

    assert dumped["confirmed_facts"] != dumped["inferences"]
    assert dumped["root_causes"][0]["evidence_ids"] == ["E-1001"]
    assert dumped["unverified_items"]
    assert dumped["evidence_chain"][0]["target_id"] == "H-1001"


def test_remaining_contracts_validate_normal_models() -> None:
    knowledge = KnowledgeContext(
        **COMMON,
        query="Expected checkout timeout behavior",
        facts=["Version 2026.09.1 defaults to a pool limit of 10."],
        references=[RawReference(uri="obsidian://products/checkout/2026.09.1")],
        skill_ids=["troubleshooting.checkout-timeout.v1"],
        limitations=[],
    )
    troubleshooting = TroubleshootingContext(
        **COMMON,
        actions_taken=["Restarted one canary pod."],
        observed_results=["Timeout rate was unchanged."],
        known_workarounds=["Restore the prior pool limit."],
        constraints=["Do not inject faults into production."],
    )
    experiment_result = ExperimentResult(
        **COMMON,
        experiment_id="EXP-1001",
        status=ExperimentStatus.SUCCEEDED,
        started_at=NOW,
        completed_at=NOW,
        observations=["Timeout pattern reproduced."],
        evidence_ids=["E-1001"],
        outputs={"timeout_rate": 0.12},
    )
    verification = VerificationResult(
        **COMMON,
        status=VerificationStatus.CONFIRMED,
        hypothesis_ids=["H-1001"],
        experiment_ids=["EXP-1001"],
        evidence_ids=["E-1001"],
        confirmed_claims=["Pool limit causes the observed timeout pattern."],
        rejected_claims=[],
        unverified_claims=[],
        rationale="The isolated experiment reproduced both signals.",
        confidence=0.98,
    )
    reflection = ReflectionResult(
        **COMMON,
        summary="Evidence is sufficient for an RCA.",
        retained_hypothesis_ids=["H-1001"],
        rejected_hypothesis_ids=[],
        new_hypotheses=[],
        missing_evidence=[],
        next_action=NextAction.ASSESS_ROOT_CAUSE,
        should_continue=True,
    )
    assessment = RootCauseAssessment(
        **COMMON,
        status=RootCauseStatus.CONFIRMED,
        confirmed_facts=[
            EvidenceBackedClaim(statement="Pool waiters increased.", evidence_ids=["E-1001"])
        ],
        inferences=[],
        root_causes=[root_cause()],
        unverified_items=[],
        overall_confidence=0.98,
    )
    state = IncidentState(
        **COMMON,
        status=IncidentLifecycleStatus.VERIFYING,
        revision=3,
        problem=problem_context(),
        product=product_context(),
        knowledge=knowledge,
        troubleshooting=troubleshooting,
        hypotheses=HypothesisSet(
            **COMMON,
            hypotheses=[hypothesis()],
            prioritized_hypothesis_ids=["H-1001"],
            selection_rationale="Highest confidence.",
        ),
        evidence=[evidence()],
        experiment_plans=[experiment_plan()],
        experiment_results=[experiment_result],
        verification_results=[verification],
        root_cause_assessment=assessment,
    )
    task = RuntimeTask(
        **COMMON,
        task_id="TASK-1001",
        kind=TaskKind.INVESTIGATION,
        status=TaskStatus.QUEUED,
        payload={"evidence_request_id": "REQ-1001"},
        depends_on=[],
        attempt=0,
        max_attempts=3,
    )
    task_result = TaskResult(
        **COMMON,
        task_id="TASK-1001",
        status=TaskStatus.SUCCEEDED,
        output={"collected": True},
        evidence_ids=["E-1001"],
        error=None,
        started_at=NOW,
        completed_at=NOW,
    )
    error = ErrorResponse(
        **COMMON,
        code="UPSTREAM_TIMEOUT",
        message="The log backend timed out.",
        category=ErrorCategory.TIMEOUT,
        retryable=True,
        details={"backend": "logs"},
    )
    audit = AuditEvent(
        **COMMON,
        audit_event_id="AUD-1001",
        event_type="task.completed",
        actor="runtime",
        action="complete_task",
        outcome="succeeded",
        target_ref="TASK-1001",
        details={"evidence_ids": ["E-1001"]},
    )

    assert state.revision == 3
    assert task.max_attempts == 3
    assert task_result.status is TaskStatus.SUCCEEDED
    assert error.retryable is True
    assert audit.audit_event_id == "AUD-1001"
    assert reflection.next_action is NextAction.ASSESS_ROOT_CAUSE
