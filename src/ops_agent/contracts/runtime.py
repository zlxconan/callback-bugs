"""Runtime task and aggregate incident-state contracts."""

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from ops_agent.contracts.analysis import RootCauseAssessment, VerificationResult
from ops_agent.contracts.base import ContractBase, EvidenceId, TaskId
from ops_agent.contracts.contexts import (
    KnowledgeContext,
    ProblemContext,
    ProductContext,
    TroubleshootingContext,
)
from ops_agent.contracts.enums import IncidentLifecycleStatus, TaskKind, TaskStatus
from ops_agent.contracts.errors import ErrorResponse
from ops_agent.contracts.evidence import Evidence
from ops_agent.contracts.experiments import ExperimentPlan, ExperimentResult
from ops_agent.contracts.hypotheses import HypothesisSet


class IncidentState(ContractBase):
    """Serializable authoritative snapshot owned by the core runtime."""

    status: IncidentLifecycleStatus
    revision: int = Field(ge=0)
    problem: ProblemContext
    product: ProductContext | None = None
    knowledge: KnowledgeContext | None = None
    troubleshooting: TroubleshootingContext | None = None
    hypotheses: HypothesisSet | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    experiment_plans: list[ExperimentPlan] = Field(default_factory=list)
    experiment_results: list[ExperimentResult] = Field(default_factory=list)
    verification_results: list[VerificationResult] = Field(default_factory=list)
    root_cause_assessment: RootCauseAssessment | None = None


class RuntimeTask(ContractBase):
    """One runtime-owned unit of work addressed to a port."""

    task_id: TaskId
    kind: TaskKind
    status: TaskStatus
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    depends_on: list[TaskId] = Field(default_factory=list)
    attempt: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    deadline: AwareDatetime | None = None


class TaskResult(ContractBase):
    """Terminal result returned for a runtime task."""

    task_id: TaskId
    status: TaskStatus
    output: dict[str, JsonValue] = Field(default_factory=dict)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    error: ErrorResponse | None = None
    started_at: AwareDatetime
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def result_must_be_terminal_and_time_ordered(self) -> "TaskResult":
        terminal_statuses = {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMED_OUT,
        }
        if self.status not in terminal_statuses:
            raise ValueError("TaskResult status must be terminal")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        if self.status is TaskStatus.FAILED and self.error is None:
            raise ValueError("failed TaskResult requires an error")
        return self
