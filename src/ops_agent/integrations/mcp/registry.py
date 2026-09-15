"""Transport-neutral MCP tool registry backed by existing Pydantic Contracts."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ValidationError

from ops_agent.contracts import ErrorCategory, ErrorResponse

McpHandler = Callable[[Any], Awaitable[Any]]


class McpPermissionRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class McpTool:
    """One MCP-visible operation with Contract identity and permission metadata."""

    name: str
    server: str
    purpose: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    port: str
    risk: McpPermissionRisk
    write: bool
    handler: McpHandler
    output_nullable: bool = False

    @property
    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()

    @property
    def output_schema(self) -> dict[str, Any]:
        schema = self.output_model.model_json_schema()
        if not self.output_nullable:
            return schema
        definitions = schema.pop("$defs", None)
        nullable_schema = {"anyOf": [schema, {"type": "null"}]}
        if definitions is not None:
            nullable_schema["$defs"] = definitions
        return nullable_schema


class McpInvocationError(RuntimeError):
    """MCP boundary failure carrying the system-wide ErrorResponse Contract."""

    def __init__(self, error: ErrorResponse) -> None:
        super().__init__(error.message)
        self.error = error


class McpToolRegistry:
    """Validate JSON at the edge, invoke a typed handler, and validate its result."""

    def __init__(self, server: str) -> None:
        self.server = server
        self._tools: dict[str, McpTool] = {}

    def register(self, tool: McpTool) -> None:
        if tool.server != self.server:
            raise ValueError(f"tool server mismatch: {tool.server}")
        if tool.name in self._tools:
            raise ValueError(f"duplicate MCP tool: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> McpTool:
        try:
            return self._tools[name]
        except KeyError as error:
            raise self._error({}, "MCP_TOOL_NOT_FOUND", f"Unknown MCP tool: {name}") from error

    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    async def call(self, name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        tool = self.get(name)
        try:
            value = tool.input_model.model_validate(payload)
        except ValidationError as error:
            raise self._error(
                payload,
                "MCP_INPUT_VALIDATION_ERROR",
                str(error),
                category=ErrorCategory.VALIDATION,
            ) from error

        try:
            result = await tool.handler(value)
            if result is None and tool.output_nullable:
                return None
            output = tool.output_model.model_validate(result)
        except McpInvocationError:
            raise
        except Exception as error:
            raise self._error(
                payload,
                "MCP_TOOL_EXECUTION_ERROR",
                str(error),
                category=ErrorCategory.DEPENDENCY,
                retryable=True,
            ) from error
        return output.model_dump(mode="json")

    @staticmethod
    def _error(
        payload: dict[str, Any],
        code: str,
        message: str,
        *,
        category: ErrorCategory = ErrorCategory.TERMINAL,
        retryable: bool = False,
    ) -> McpInvocationError:
        raw_timestamp = payload.get("timestamp")
        timestamp = raw_timestamp if isinstance(raw_timestamp, datetime) else datetime.now(UTC)
        incident_id = payload.get("incident_id", "INC-MCP")
        request_id = payload.get("request_id", "REQ-MCP")
        if not isinstance(incident_id, str) or not incident_id.startswith("INC-"):
            incident_id = "INC-MCP"
        if not isinstance(request_id, str) or not request_id.startswith("REQ-"):
            request_id = "REQ-MCP"
        response = ErrorResponse(
            incident_id=incident_id,
            request_id=request_id,
            timestamp=timestamp,
            source="mcp-registry",
            code=code,
            message=message,
            category=category,
            retryable=retryable,
            details={},
        )
        return McpInvocationError(response)
