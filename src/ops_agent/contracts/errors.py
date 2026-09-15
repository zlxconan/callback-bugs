"""Standard error response contract."""

from pydantic import Field, JsonValue

from ops_agent.contracts.base import ContractBase, NonEmptyString
from ops_agent.contracts.enums import ErrorCategory


class ErrorResponse(ContractBase):
    """Machine-readable error returned across module or API boundaries."""

    code: NonEmptyString
    message: NonEmptyString
    category: ErrorCategory
    retryable: bool
    details: dict[str, JsonValue] = Field(default_factory=dict)
