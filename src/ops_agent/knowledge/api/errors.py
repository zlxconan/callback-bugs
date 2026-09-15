"""Map Knowledge domain errors at the HTTP boundary."""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException

from ops_agent.contracts import ContractBase, ErrorCategory, ErrorResponse
from ops_agent.knowledge.domain import KnowledgeError

T = TypeVar("T")


async def invoke(operation: Callable[[], Awaitable[T]], request: ContractBase) -> T:
    try:
        return await operation()
    except KnowledgeError as error:
        response = ErrorResponse(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="knowledge-api",
            code=error.code,
            message=str(error),
            category=ErrorCategory.DEPENDENCY if error.retryable else ErrorCategory.TERMINAL,
            retryable=error.retryable,
        )
        raise HTTPException(status_code=503, detail=response.model_dump(mode="json")) from error
