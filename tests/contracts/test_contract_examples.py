from pathlib import Path

import pytest

from ops_agent.contracts import (
    AuditEvent,
    ContractBase,
    ErrorResponse,
    Evidence,
    EvidencePlan,
    EvidenceRequest,
    ExperimentPlan,
    ExperimentResult,
    Hypothesis,
    HypothesisSet,
    IncidentState,
    KnowledgeContext,
    ProblemContext,
    ProductContext,
    RCAReport,
    ReflectionResult,
    RootCauseAssessment,
    RuntimeTask,
    TaskResult,
    TroubleshootingContext,
    VerificationResult,
)

EXAMPLES_ROOT = Path(__file__).parents[2] / "examples" / "contracts"
EXAMPLES: list[tuple[str, type[ContractBase]]] = [
    ("problem-context.json", ProblemContext),
    ("product-context.json", ProductContext),
    ("knowledge-context.json", KnowledgeContext),
    ("troubleshooting-context.json", TroubleshootingContext),
    ("hypothesis.json", Hypothesis),
    ("hypothesis-set.json", HypothesisSet),
    ("evidence-request.json", EvidenceRequest),
    ("evidence-plan.json", EvidencePlan),
    ("evidence.json", Evidence),
    ("experiment-plan.json", ExperimentPlan),
    ("experiment-result.json", ExperimentResult),
    ("verification-result.json", VerificationResult),
    ("reflection-result.json", ReflectionResult),
    ("root-cause-assessment.json", RootCauseAssessment),
    ("incident-state.json", IncidentState),
    ("runtime-task.json", RuntimeTask),
    ("task-result.json", TaskResult),
    ("rca-report.json", RCAReport),
    ("error-response.json", ErrorResponse),
    ("audit-event.json", AuditEvent),
]


@pytest.mark.parametrize(("filename", "model"), EXAMPLES)
def test_contract_example_validates_and_round_trips(
    filename: str,
    model: type[ContractBase],
) -> None:
    raw_json = (EXAMPLES_ROOT / filename).read_text(encoding="utf-8")

    value = model.model_validate_json(raw_json)
    restored = model.model_validate(value.model_dump(mode="json"))

    assert restored == value
    assert value.schema_version == "1.0"


def test_every_core_contract_has_one_example() -> None:
    assert len(EXAMPLES) == 20
    assert {path.name for path in EXAMPLES_ROOT.glob("*.json")} == {
        filename for filename, _ in EXAMPLES
    }
