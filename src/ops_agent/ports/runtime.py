"""Runtime orchestration port."""

from typing import Protocol, runtime_checkable

from ops_agent.contracts import (
    FinishIncidentRequest,
    IncidentQuery,
    IncidentState,
    RCAReport,
    RuntimeTask,
    StartIncidentRequest,
    TaskResult,
)


@runtime_checkable
class RuntimePort(Protocol):
    """Public command/query boundary for the sole workflow orchestrator."""

    async def start_incident(self, command: StartIncidentRequest) -> IncidentState: ...

    async def get_next_task(self, query: IncidentQuery) -> RuntimeTask | None: ...

    async def submit_task_result(self, result: TaskResult) -> IncidentState: ...

    async def get_state(self, query: IncidentQuery) -> IncidentState: ...

    async def finish_incident(self, command: FinishIncidentRequest) -> RCAReport: ...
