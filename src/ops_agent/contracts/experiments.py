"""Reproduction experiment contracts."""

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from ops_agent.contracts.base import (
    ContractBase,
    EvidenceId,
    ExperimentId,
    HypothesisId,
    NonEmptyString,
    StrictModel,
)
from ops_agent.contracts.enums import ExperimentStatus


class ExperimentStep(StrictModel):
    """One deterministic action in a reproduction plan."""

    step_number: int = Field(ge=1)
    action: NonEmptyString
    expected_outcome: NonEmptyString


class ExperimentPlan(ContractBase):
    """A bounded and reversible plan for testing hypotheses."""

    experiment_id: ExperimentId
    title: NonEmptyString
    objective: NonEmptyString
    hypothesis_ids: list[HypothesisId] = Field(min_length=1)
    environment: dict[str, JsonValue]
    steps: list[ExperimentStep] = Field(min_length=1)
    success_criteria: list[NonEmptyString] = Field(min_length=1)
    rollback_steps: list[NonEmptyString] = Field(min_length=1)
    risk_level: NonEmptyString
    requires_approval: bool


class ExperimentResult(ContractBase):
    """Observed outcome of one experiment plan."""

    experiment_id: ExperimentId
    status: ExperimentStatus
    started_at: AwareDatetime
    completed_at: AwareDatetime | None = None
    observations: list[NonEmptyString] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    outputs: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def completion_must_not_precede_start(self) -> "ExperimentResult":
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must not precede started_at")
        return self
