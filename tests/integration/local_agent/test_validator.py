import json

import pytest

from ops_agent.contracts import IncidentState, RuntimeTask, TaskOutput
from ops_agent.integrations.local_agent import (
    StructuredOutputValidationError,
    StructuredTaskOutputValidator,
)


def hypotheses_json(state: IncidentState) -> dict[str, object]:
    assert state.hypotheses is not None
    return {"hypotheses": state.hypotheses.model_dump(mode="json")}


@pytest.mark.parametrize(
    "raw",
    [
        "not-json",
        '{"hypotheses": {}}',
    ],
)
def test_rejects_invalid_json_and_missing_fields(
    raw: str,
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
) -> None:
    validator = StructuredTaskOutputValidator(max_hypotheses=3)

    with pytest.raises(StructuredOutputValidationError):
        validator.validate(raw, task=hypothesis_task, state=fake_incident_state)


def test_rejects_wrong_enum(
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
) -> None:
    payload = hypotheses_json(fake_incident_state)
    hypothesis_set = payload["hypotheses"]
    assert isinstance(hypothesis_set, dict)
    hypotheses = hypothesis_set["hypotheses"]
    assert isinstance(hypotheses, list) and isinstance(hypotheses[0], dict)
    hypotheses[0]["status"] = "not-a-valid-enum"

    with pytest.raises(StructuredOutputValidationError):
        StructuredTaskOutputValidator(max_hypotheses=3).validate(
            json.dumps(payload), task=hypothesis_task, state=fake_incident_state
        )


def test_rejects_fabricated_evidence_id(
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
) -> None:
    payload = hypotheses_json(fake_incident_state)
    hypothesis_set = payload["hypotheses"]
    assert isinstance(hypothesis_set, dict)
    hypotheses = hypothesis_set["hypotheses"]
    assert isinstance(hypotheses, list) and isinstance(hypotheses[0], dict)
    hypotheses[0]["supporting_evidence"] = ["E-FABRICATED"]

    with pytest.raises(StructuredOutputValidationError, match="unknown Evidence IDs"):
        StructuredTaskOutputValidator(max_hypotheses=3).validate(
            json.dumps(payload), task=hypothesis_task, state=fake_incident_state
        )


def test_rejects_hypothesis_count_above_limit(
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
) -> None:
    payload = hypotheses_json(fake_incident_state)
    hypothesis_set = payload["hypotheses"]
    assert isinstance(hypothesis_set, dict)
    hypotheses = hypothesis_set["hypotheses"]
    priorities = hypothesis_set["prioritized_hypothesis_ids"]
    assert isinstance(hypotheses, list) and isinstance(hypotheses[0], dict)
    assert isinstance(priorities, list)
    extra = {**hypotheses[0], "hypothesis_id": "H-4"}
    hypotheses.append(extra)
    priorities.append("H-4")

    with pytest.raises(StructuredOutputValidationError, match="at most 3"):
        StructuredTaskOutputValidator(max_hypotheses=3).validate(
            json.dumps(payload), task=hypothesis_task, state=fake_incident_state
        )


def test_accepts_valid_stage_specific_output(
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
) -> None:
    output = StructuredTaskOutputValidator(max_hypotheses=3).validate(
        json.dumps(hypotheses_json(fake_incident_state)),
        task=hypothesis_task,
        state=fake_incident_state,
    )

    assert isinstance(output, TaskOutput)
    assert output.hypotheses is not None
