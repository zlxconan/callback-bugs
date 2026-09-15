from pathlib import Path

import pytest

from ops_agent.contracts import IncidentState, RuntimeStage, RuntimeTask, TaskKind, TaskStatus
from ops_agent.skills import CanonicalSkill, SkillCatalog

SKILLS_ROOT = Path(__file__).parents[3] / "skills"


@pytest.fixture
def hypothesis_task(fake_incident_state: IncidentState) -> RuntimeTask:
    state = fake_incident_state
    return RuntimeTask(
        schema_version=state.schema_version,
        incident_id=state.incident_id,
        request_id=state.request_id,
        timestamp=state.timestamp,
        source="local-agent-test",
        task_id="TASK-LOCAL-HYPOTHESIS",
        kind=TaskKind.REASONING,
        status=TaskStatus.QUEUED,
        attempt=1,
        max_attempts=3,
        stage=RuntimeStage.HYPOTHESIS,
    )


@pytest.fixture
def hypothesis_skills() -> tuple[CanonicalSkill, ...]:
    return (SkillCatalog(SKILLS_ROOT).get("hypothesis-generation"),)
