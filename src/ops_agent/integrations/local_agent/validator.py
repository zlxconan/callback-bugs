"""Stage-aware validation between raw model JSON and Runtime TaskResult."""

from pydantic import ValidationError

from ops_agent.contracts import EvidenceType, IncidentState, RuntimeStage, RuntimeTask, TaskOutput


class StructuredOutputValidationError(ValueError):
    """Model output is not safe to submit to Runtime."""


class StructuredTaskOutputValidator:
    """Validate schema, stage shape, bounded choices, and reference integrity."""

    _OUTPUT_FIELDS: dict[RuntimeStage, str] = {
        RuntimeStage.NORMALIZE: "problem",
        RuntimeStage.KNOWLEDGE_LOOKUP: "knowledge_lookup",
        RuntimeStage.HYPOTHESIS: "hypotheses",
        RuntimeStage.EVIDENCE_PLAN: "evidence_plan",
        RuntimeStage.INVESTIGATE: "evidence_batch",
        RuntimeStage.ROOT_CAUSE_ASSESSMENT: "root_cause_assessment",
        RuntimeStage.EXPERIMENT_PLAN: "experiment_plan",
        RuntimeStage.REPRODUCE: "experiment_result",
        RuntimeStage.VERIFY: "verification_result",
        RuntimeStage.REFLECT: "reflection_result",
        RuntimeStage.RCA: "rca_report",
    }

    def __init__(
        self,
        *,
        max_hypotheses: int = 5,
        allowed_evidence_types: frozenset[EvidenceType] | None = None,
    ) -> None:
        if max_hypotheses < 1:
            raise ValueError("max_hypotheses must be positive")
        self._max_hypotheses = max_hypotheses
        self._allowed_evidence_types = allowed_evidence_types or frozenset(EvidenceType)

    def required_field(self, task: RuntimeTask) -> str:
        if task.stage is None or task.stage not in self._OUTPUT_FIELDS:
            raise StructuredOutputValidationError(f"Unsupported RuntimeTask stage: {task.stage}")
        return self._OUTPUT_FIELDS[task.stage]

    def validate(
        self,
        raw_json: str,
        *,
        task: RuntimeTask,
        state: IncidentState,
    ) -> TaskOutput:
        try:
            output = TaskOutput.model_validate_json(raw_json)
        except ValidationError as error:
            raise StructuredOutputValidationError(str(error)) from error

        required = self.required_field(task)
        if getattr(output, required) is None:
            raise StructuredOutputValidationError(
                f"Stage {task.stage} requires TaskOutput.{required}"
            )
        value = getattr(output, required)
        if getattr(value, "incident_id", task.incident_id) != task.incident_id:
            raise StructuredOutputValidationError("output incident_id does not match RuntimeTask")

        self._validate_hypotheses(output, state)
        self._validate_evidence_plan(output, state)
        self._validate_evidence_references(output, state)
        return output

    def _validate_hypotheses(self, output: TaskOutput, state: IncidentState) -> None:
        if output.hypotheses is None:
            return
        hypotheses = output.hypotheses.hypotheses
        if len(hypotheses) > self._max_hypotheses:
            raise StructuredOutputValidationError(
                f"model may return at most {self._max_hypotheses} hypotheses"
            )
        known_evidence = {item.evidence_id for item in state.evidence}
        referenced = {
            evidence_id
            for hypothesis in hypotheses
            for evidence_id in (
                *hypothesis.supporting_evidence,
                *hypothesis.contradicting_evidence,
            )
        }
        unknown = referenced - known_evidence
        if unknown:
            raise StructuredOutputValidationError(
                f"hypotheses reference unknown Evidence IDs: {sorted(unknown)}"
            )

    def _validate_evidence_plan(self, output: TaskOutput, state: IncidentState) -> None:
        if output.evidence_plan is None:
            return
        known_hypotheses = (
            {item.hypothesis_id for item in state.hypotheses.hypotheses}
            if state.hypotheses is not None
            else set()
        )
        for request in output.evidence_plan.requests:
            if request.evidence_type not in self._allowed_evidence_types:
                raise StructuredOutputValidationError(
                    f"Evidence type is not allowed: {request.evidence_type}"
                )
            unknown = set(request.hypothesis_ids) - known_hypotheses
            if unknown:
                raise StructuredOutputValidationError(
                    f"EvidenceRequest references unknown Hypothesis IDs: {sorted(unknown)}"
                )

    @staticmethod
    def _validate_evidence_references(output: TaskOutput, state: IncidentState) -> None:
        known = {item.evidence_id for item in state.evidence}
        references: set[str] = set()
        if output.root_cause_assessment is not None:
            references.update(
                evidence_id
                for claim in output.root_cause_assessment.confirmed_facts
                for evidence_id in claim.evidence_ids
            )
            references.update(
                evidence_id
                for cause in output.root_cause_assessment.root_causes
                for evidence_id in cause.evidence_ids
            )
        if output.experiment_result is not None:
            references.update(output.experiment_result.evidence_ids)
        if output.verification_result is not None:
            references.update(output.verification_result.evidence_ids)
        if output.rca_report is not None:
            references.update(link.evidence_id for link in output.rca_report.evidence_chain)
            references.update(
                evidence_id
                for cause in output.rca_report.root_causes
                for evidence_id in cause.evidence_ids
            )
        unknown = references - known
        if unknown:
            raise StructuredOutputValidationError(
                f"output references unknown Evidence IDs: {sorted(unknown)}"
            )
