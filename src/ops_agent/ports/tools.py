"""Low-level capabilities implemented by adapters or MCP clients."""

from typing import Protocol, runtime_checkable

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    Evidence,
    EvidenceRequest,
    ExperimentExecutionRequest,
    ExperimentResult,
)


@runtime_checkable
class TraceToolPort(Protocol):
    async def collect(self, request: EvidenceRequest) -> Evidence: ...


@runtime_checkable
class LogToolPort(Protocol):
    async def collect(self, request: EvidenceRequest) -> Evidence: ...


@runtime_checkable
class MetricToolPort(Protocol):
    async def collect(self, request: EvidenceRequest) -> Evidence: ...


@runtime_checkable
class K8sToolPort(Protocol):
    async def collect(self, request: EvidenceRequest) -> Evidence: ...


@runtime_checkable
class ChangeToolPort(Protocol):
    async def collect(self, request: EvidenceRequest) -> Evidence: ...


@runtime_checkable
class TopologyToolPort(Protocol):
    async def collect(self, request: EvidenceRequest) -> Evidence: ...


@runtime_checkable
class CodeGraphToolPort(Protocol):
    async def collect(self, request: EvidenceRequest) -> Evidence: ...


@runtime_checkable
class BrowserToolPort(Protocol):
    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult: ...


@runtime_checkable
class ApiToolPort(Protocol):
    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult: ...


@runtime_checkable
class ShellToolPort(Protocol):
    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult: ...


@runtime_checkable
class FaultInjectionToolPort(Protocol):
    async def apply(self, request: ExperimentExecutionRequest) -> ExperimentResult: ...

    async def rollback(self, request: EnvironmentCleanupRequest) -> CleanupResult: ...
