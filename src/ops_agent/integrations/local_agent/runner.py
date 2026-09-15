"""Runtime next/reason/submit loop for a Local Small Model Agent."""

from pydantic import BaseModel, ConfigDict

from ops_agent.contracts import (
    IncidentQuery,
    IncidentState,
    RCAReport,
    RuntimeStage,
    StartIncidentRequest,
)
from ops_agent.ports import RuntimePort
from ops_agent.skills import RuntimeTaskSkillRouter, SkillCatalog

from .agent import LocalSmallModelAgent


class LocalAgentOutcome(BaseModel):
    """Serializable outcome without duplicating Runtime-owned state."""

    model_config = ConfigDict(extra="forbid")

    query: IncidentQuery
    stage_history: list[RuntimeStage]
    loaded_skills: list[str]
    final_state: IncidentState

    @property
    def report(self) -> RCAReport | None:
        return self.final_state.rca_report


class LocalAgentRunner:
    """Drive Core Runtime while never writing IncidentState directly."""

    def __init__(
        self,
        *,
        runtime: RuntimePort,
        agent: LocalSmallModelAgent,
        skill_catalog: SkillCatalog,
        max_iterations: int = 50,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be positive")
        self._runtime = runtime
        self._agent = agent
        self._skill_router = RuntimeTaskSkillRouter(skill_catalog)
        self._max_iterations = max_iterations

    async def run(self, command: StartIncidentRequest) -> LocalAgentOutcome:
        state = await self._runtime.start_incident(command)
        query = IncidentQuery(
            schema_version=command.schema_version,
            incident_id=command.incident_id,
            request_id=command.request_id,
            timestamp=command.timestamp,
            source="local-agent-runner",
            metadata={"reasoning_owner": "local-small-model"},
        )
        history: list[RuntimeStage] = []
        loaded_skills: list[str] = []
        self._record_stage(history, state)

        for _ in range(self._max_iterations):
            task = await self._runtime.get_next_task(query)
            state = await self._runtime.get_state(query)
            self._record_stage(history, state)
            if state.runtime_stage in {
                RuntimeStage.COMPLETED,
                RuntimeStage.FAILED,
                RuntimeStage.WAITING_HUMAN,
            }:
                return LocalAgentOutcome(
                    query=query,
                    stage_history=history,
                    loaded_skills=loaded_skills,
                    final_state=state,
                )
            if task is None:
                continue

            skills = self._skill_router.resolve(task)
            loaded_skills.extend(skill.name for skill in skills)
            result = await self._agent.reason(task, state, skills)
            state = await self._runtime.submit_task_result(result)
            self._record_stage(history, state)

        raise RuntimeError(f"Local Agent exceeded max iterations: {self._max_iterations}")

    @staticmethod
    def _record_stage(history: list[RuntimeStage], state: IncidentState) -> None:
        if state.runtime_stage is not None and (
            not history or history[-1] is not state.runtime_stage
        ):
            history.append(state.runtime_stage)
