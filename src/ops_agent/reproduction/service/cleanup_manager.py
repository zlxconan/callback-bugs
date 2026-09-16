"""Idempotent cleanup coordination for prepared experiment environments."""

import asyncio
from typing import cast

from pydantic import JsonValue

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
)
from ops_agent.ports import FaultInjectionToolPort


class CleanupManager:
    """Rollback experiment-scoped fault state without masking primary failures."""

    def __init__(self, fault: FaultInjectionToolPort, *, timeout_seconds: float) -> None:
        self._fault = fault
        self._timeout_seconds = timeout_seconds
        self._requests: dict[str, ExperimentExecutionRequest] = {}
        self._cleaned: set[str] = set()
        self._failures: list[str] = []
        self.attempt_count = 0

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(self._failures)

    def register(self, request: ExperimentExecutionRequest) -> None:
        environment_ref = request.environment.environment_ref
        self._cleaned.discard(environment_ref)
        self._requests[environment_ref] = request

    async def cleanup(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        environment_ref = request.environment_ref
        if environment_ref in self._cleaned or environment_ref not in self._requests:
            return self._result(
                request, cleaned=True, observations=["Environment already cleaned."]
            )

        self.attempt_count += 1
        try:
            async with asyncio.timeout(self._timeout_seconds):
                result = await self._fault.rollback(request)
        except TimeoutError:
            message = f"cleanup timed out for {environment_ref}"
            self._failures.append(message)
            return self._result(request, cleaned=False, observations=[message])
        except Exception as error:
            message = str(error)
            self._failures.append(message)
            return self._result(request, cleaned=False, observations=[message])

        if result.cleaned:
            self._cleaned.add(environment_ref)
            self._requests.pop(environment_ref, None)
        else:
            self._failures.extend(result.observations or ["cleanup returned cleaned=false"])
        return result

    async def cleanup_execution(self, request: ExperimentExecutionRequest) -> CleanupResult:
        cleanup_request = EnvironmentCleanupRequest(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="real-reproduction-cleanup",
            experiment_id=request.plan.experiment_id,
            environment_ref=request.environment.environment_ref,
        )
        return await self.cleanup(cleanup_request)

    @staticmethod
    def _result(
        request: EnvironmentCleanupRequest,
        *,
        cleaned: bool,
        observations: list[str],
    ) -> CleanupResult:
        return CleanupResult(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="real-reproduction-cleanup",
            metadata={
                "cleanup_errors": cast(JsonValue, [] if cleaned else observations),
            },
            experiment_id=request.experiment_id,
            environment_ref=request.environment_ref,
            cleaned=cleaned,
            observations=observations,
        )
