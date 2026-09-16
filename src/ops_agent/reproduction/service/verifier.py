"""Deterministic verification rules for the timeout/retry duplicate-create case."""

from collections.abc import Callable
from typing import Any, cast

from pydantic import JsonValue

from ops_agent.contracts import (
    ExperimentVerificationRequest,
    VerificationResult,
    VerificationStatus,
)


class DeterministicExperimentVerifier:
    """Evaluate explicit result fields; never delegate judgment to an LLM."""

    _CRITERIA: tuple[tuple[str, Callable[[dict[str, Any]], bool]], ...] = (
        ("same business_id request count >= 2", lambda value: value.get("request_count", 0) >= 2),
        (
            "first request backend_status == success",
            lambda value: value.get("first_backend_status") == "success",
        ),
        ("retry_detected == true", lambda value: value.get("retry_detected") is True),
        ("database record count == 2", lambda value: value.get("database_record_count") == 2),
    )

    def verify(self, request: ExperimentVerificationRequest) -> VerificationResult:
        values = dict(request.result.outputs)
        matched = [label for label, rule in self._CRITERIA if rule(values)]
        unmatched = [label for label, rule in self._CRITERIA if not rule(values)]
        confirmed = not unmatched
        conclusion = (
            f"all {len(matched)} criteria matched"
            if confirmed
            else f"{len(unmatched)} of {len(self._CRITERIA)} criteria unmatched"
        )
        return VerificationResult(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="deterministic-reproduction-verifier",
            metadata={
                "matched_criteria": cast(JsonValue, matched),
                "unmatched_criteria": cast(JsonValue, unmatched),
                "conclusion": "success" if confirmed else "failure",
            },
            status=VerificationStatus.CONFIRMED if confirmed else VerificationStatus.REJECTED,
            hypothesis_ids=request.plan.hypothesis_ids,
            experiment_ids=[request.plan.experiment_id],
            evidence_ids=request.result.evidence_ids,
            confirmed_claims=matched,
            rejected_claims=unmatched,
            unverified_claims=[],
            rationale=conclusion,
            confidence=len(matched) / len(self._CRITERIA),
        )
