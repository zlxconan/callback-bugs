"""Stateless External Agent loop for CodeBuddy-compatible Reasoning Owners."""

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ops_agent.contracts import (
    IncidentQuery,
    IncidentState,
    RCAReport,
    RuntimeStage,
    RuntimeTask,
    StartIncidentRequest,
    TaskResult,
)
from ops_agent.ports import RuntimePort
from ops_agent.skills import CanonicalSkill, SkillCatalog


class CodeBuddyAdapterConfig(BaseModel):
    """Transport choice and bounded loop settings for the host adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_transport: Literal["mcp", "api"] = "mcp"
    skills_target: Literal["codebuddy"] = "codebuddy"
    max_iterations: int = Field(default=50, ge=1, le=1000)


class ReasoningOwner(Protocol):
    """Agent-owned reasoning for one task; no Runtime mutation capability is provided."""

    async def reason(
        self,
        task: RuntimeTask,
        state: IncidentState,
        skills: tuple[CanonicalSkill, ...],
    ) -> TaskResult: ...


class CodeBuddyRunOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: IncidentQuery
    stage_history: list[RuntimeStage]
    loaded_skills: list[str]
    final_state: IncidentState

    @property
    def report(self) -> RCAReport | None:
        return self.final_state.rca_report


class RuntimeTaskSkillRouter:
    """Explicit Runtime Stage to Canonical Skill mapping."""

    _MAPPING: dict[RuntimeStage, tuple[str, ...]] = {
        RuntimeStage.NORMALIZE: ("incident-analysis",),
        RuntimeStage.KNOWLEDGE_LOOKUP: ("product-knowledge", "troubleshooting"),
        RuntimeStage.HYPOTHESIS: ("hypothesis-generation",),
        RuntimeStage.EVIDENCE_PLAN: ("evidence-planning",),
        RuntimeStage.INVESTIGATE: ("incident-analysis",),
        RuntimeStage.ROOT_CAUSE_ASSESSMENT: ("incident-analysis",),
        RuntimeStage.EXPERIMENT_PLAN: ("reproduction-planning",),
        RuntimeStage.REPRODUCE: ("incident-analysis",),
        RuntimeStage.VERIFY: ("incident-analysis",),
        RuntimeStage.REFLECT: ("reflection",),
        RuntimeStage.RCA: ("rca-report",),
        RuntimeStage.WAITING_HUMAN: ("incident-analysis",),
    }

    def __init__(self, catalog: SkillCatalog) -> None:
        self._catalog = catalog

    def names_for(self, stage: RuntimeStage) -> tuple[str, ...]:
        try:
            return self._MAPPING[stage]
        except KeyError as error:
            raise ValueError(f"No Canonical Skill mapping for Runtime Stage: {stage}") from error

    def resolve(self, task: RuntimeTask) -> tuple[CanonicalSkill, ...]:
        if task.stage is None:
            raise ValueError(f"RuntimeTask has no Stage: {task.task_id}")
        return tuple(self._catalog.get(name) for name in self.names_for(task.stage))


class CodeBuddyAdapter:
    """Run next/reason/submit while Core Runtime remains the sole state owner."""

    def __init__(
        self,
        *,
        runtime: RuntimePort,
        skill_router: RuntimeTaskSkillRouter,
        reasoning_owner: ReasoningOwner,
        config: CodeBuddyAdapterConfig,
    ) -> None:
        self._runtime = runtime
        self._skill_router = skill_router
        self._reasoning_owner = reasoning_owner
        self._config = config

    async def run(self, command: StartIncidentRequest) -> CodeBuddyRunOutcome:
        state = await self._runtime.start_incident(command)
        query = IncidentQuery(
            schema_version=command.schema_version,
            incident_id=command.incident_id,
            request_id=command.request_id,
            timestamp=command.timestamp,
            source="codebuddy-adapter",
            metadata={"runtime_transport": self._config.runtime_transport},
        )
        history: list[RuntimeStage] = []
        loaded_skills: list[str] = []
        self._record_stage(history, state)

        for _ in range(self._config.max_iterations):
            task = await self._runtime.get_next_task(query)
            state = await self._runtime.get_state(query)
            self._record_stage(history, state)
            if state.runtime_stage in {
                RuntimeStage.COMPLETED,
                RuntimeStage.FAILED,
                RuntimeStage.WAITING_HUMAN,
            }:
                return CodeBuddyRunOutcome(
                    query=query,
                    stage_history=history,
                    loaded_skills=loaded_skills,
                    final_state=state,
                )
            if task is None:
                continue

            skills = self._skill_router.resolve(task)
            loaded_skills.extend(skill.name for skill in skills)
            result = await self._reasoning_owner.reason(task, state, skills)
            state = await self._runtime.submit_task_result(result)
            self._record_stage(history, state)

        raise RuntimeError(
            f"CodeBuddy Adapter exceeded max iterations: {self._config.max_iterations}"
        )

    @staticmethod
    def _record_stage(history: list[RuntimeStage], state: IncidentState) -> None:
        if state.runtime_stage is not None and (
            not history or history[-1] is not state.runtime_stage
        ):
            history.append(state.runtime_stage)
