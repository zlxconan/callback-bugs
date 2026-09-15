"""Small-model Reasoning Owner for exactly one RuntimeTask per invocation."""

import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ops_agent.contracts import (
    ErrorCategory,
    ErrorResponse,
    IncidentState,
    LLMRequest,
    RuntimeStage,
    RuntimeTask,
    TaskOutput,
    TaskResult,
    TaskStatus,
)
from ops_agent.ports import LLMProviderPort
from ops_agent.skills import CanonicalSkill

from .validator import StructuredOutputValidationError, StructuredTaskOutputValidator


class LocalAgentConfig(BaseModel):
    """Bounded retry policy for one small-model task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_validation_attempts: int = Field(default=2, ge=1, le=10)


class FallbackReasoningOwner(Protocol):
    """Deterministic escape hatch used only after model attempts are exhausted."""

    async def reason(
        self,
        task: RuntimeTask,
        state: IncidentState,
        skills: tuple[CanonicalSkill, ...],
    ) -> TaskResult: ...


class LocalSmallModelAgent:
    """Convert one RuntimeTask into one validated, typed TaskResult."""

    def __init__(
        self,
        *,
        provider: LLMProviderPort,
        validator: StructuredTaskOutputValidator,
        config: LocalAgentConfig,
        fallback: FallbackReasoningOwner | None = None,
    ) -> None:
        self._provider = provider
        self._validator = validator
        self._config = config
        self._fallback = fallback
        self.retry_count = 0
        self.fallback_count = 0
        self.validated_output_count = 0

    async def reason(
        self,
        task: RuntimeTask,
        state: IncidentState,
        skills: tuple[CanonicalSkill, ...],
    ) -> TaskResult:
        """Run Structured Output -> Validator -> Retry -> Fallback."""
        last_error: Exception | None = None
        for attempt in range(1, self._config.max_validation_attempts + 1):
            try:
                request = self._request(task, state, skills, attempt)
                response = await self._provider.generate(request)
                output = self._validator.validate(response.content, task=task, state=state)
            except Exception as error:  # Provider and validation failures share retry policy.
                last_error = error
                if attempt < self._config.max_validation_attempts:
                    self.retry_count += 1
                continue

            self.validated_output_count += 1
            return self._successful_result(task, output)

        if self._fallback is not None:
            self.fallback_count += 1
            return await self._fallback.reason(task, state, skills)
        return self._failed_result(task, last_error)

    def _request(
        self,
        task: RuntimeTask,
        state: IncidentState,
        skills: tuple[CanonicalSkill, ...],
        attempt: int,
    ) -> LLMRequest:
        return LLMRequest(
            schema_version=task.schema_version,
            incident_id=task.incident_id,
            request_id=task.request_id,
            timestamp=task.timestamp,
            source="local-small-model-agent",
            metadata={"stage": task.stage.value if task.stage is not None else "unknown"},
            task=task,
            state=state,
            state_summary=self._state_summary(task, state),
            skill_names=[skill.name for skill in skills],
            skill_instructions=[skill.instructions for skill in skills],
            required_output_field=self._validator.required_field(task),
            output_schema=TaskOutput.model_json_schema(mode="validation"),
            attempt=attempt,
        )

    @staticmethod
    def _state_summary(task: RuntimeTask, state: IncidentState) -> str:
        """Expose only stage-relevant state in the actual provider prompt."""
        common: dict[str, object] = {"problem": state.problem.model_dump(mode="json")}
        stage_fields: dict[RuntimeStage, tuple[str, ...]] = {
            RuntimeStage.NORMALIZE: (),
            RuntimeStage.KNOWLEDGE_LOOKUP: (),
            RuntimeStage.HYPOTHESIS: (
                "product",
                "knowledge",
                "troubleshooting",
                "evidence",
            ),
            RuntimeStage.EVIDENCE_PLAN: ("hypotheses", "evidence"),
            RuntimeStage.INVESTIGATE: ("latest_evidence_plan",),
            RuntimeStage.ROOT_CAUSE_ASSESSMENT: (
                "hypotheses",
                "evidence",
                "verification_results",
            ),
            RuntimeStage.EXPERIMENT_PLAN: ("product", "hypotheses", "evidence"),
            RuntimeStage.REPRODUCE: ("experiment_plans",),
            RuntimeStage.VERIFY: (
                "experiment_plans",
                "experiment_results",
                "evidence",
            ),
            RuntimeStage.REFLECT: (
                "hypotheses",
                "evidence",
                "experiment_results",
                "reflection_count",
            ),
            RuntimeStage.RCA: (
                "root_cause_assessment",
                "evidence",
                "experiment_results",
                "verification_results",
            ),
        }
        if task.stage is None or task.stage not in stage_fields:
            raise StructuredOutputValidationError(f"Unsupported RuntimeTask stage: {task.stage}")
        state_data = state.model_dump(mode="json")
        for field in stage_fields[task.stage]:
            common[field] = state_data[field]
        return json.dumps(common, ensure_ascii=False)

    @staticmethod
    def _successful_result(task: RuntimeTask, output: TaskOutput) -> TaskResult:
        return TaskResult(
            schema_version=task.schema_version,
            incident_id=task.incident_id,
            request_id=task.request_id,
            timestamp=task.timestamp,
            source="local-small-model-agent",
            metadata={"validated": True},
            task_id=task.task_id,
            status=TaskStatus.SUCCEEDED,
            typed_output=output,
            started_at=task.timestamp,
            completed_at=task.timestamp,
        )

    @staticmethod
    def _failed_result(task: RuntimeTask, error: Exception | None) -> TaskResult:
        message = str(error) if error is not None else "LLM output validation failed"
        response = ErrorResponse(
            schema_version=task.schema_version,
            incident_id=task.incident_id,
            request_id=task.request_id,
            timestamp=task.timestamp,
            source="local-small-model-agent",
            metadata={},
            code="LOCAL_AGENT_OUTPUT_INVALID",
            message=message,
            category=ErrorCategory.VALIDATION,
            retryable=False,
            details={"stage": task.stage.value if task.stage is not None else "unknown"},
        )
        return TaskResult(
            schema_version=task.schema_version,
            incident_id=task.incident_id,
            request_id=task.request_id,
            timestamp=task.timestamp,
            source="local-small-model-agent",
            metadata={"validated": False},
            task_id=task.task_id,
            status=TaskStatus.FAILED,
            typed_output=None,
            error=response,
            started_at=task.timestamp,
            completed_at=task.timestamp,
        )
