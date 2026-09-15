"""Fake External Agent implementing one-task-at-a-time reasoning."""

from ops_agent.contracts import IncidentState, RuntimeTask, TaskResult
from ops_agent.integrations.local_agent import FakeTaskReasoner
from ops_agent.skills import CanonicalSkill


class FakeExternalAgent:
    """Deterministic Reasoning Owner; it cannot submit results or mutate state."""

    def __init__(self, task_executor: FakeTaskReasoner) -> None:
        self._task_executor = task_executor
        self.reason_count = 0
        self.loaded_skills: list[str] = []

    async def reason(
        self,
        task: RuntimeTask,
        state: IncidentState,
        skills: tuple[CanonicalSkill, ...],
    ) -> TaskResult:
        self.reason_count += 1
        self.loaded_skills.extend(skill.name for skill in skills)
        return await self._task_executor.reason(task, state)
