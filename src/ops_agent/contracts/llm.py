"""Provider-neutral structured LLM boundary contracts."""

from pydantic import Field, JsonValue

from ops_agent.contracts.base import ContractBase, NonEmptyString
from ops_agent.contracts.runtime import IncidentState, RuntimeTask


class LLMRequest(ContractBase):
    """One bounded RuntimeTask prompt request sent to an LLM provider."""

    task: RuntimeTask
    state: IncidentState
    state_summary: NonEmptyString
    skill_names: list[NonEmptyString] = Field(min_length=1)
    skill_instructions: list[NonEmptyString] = Field(min_length=1)
    required_output_field: NonEmptyString
    output_schema: dict[str, JsonValue]
    attempt: int = Field(ge=1)


class LLMResponse(ContractBase):
    """Raw provider response that must be validated before Runtime submission."""

    content: NonEmptyString
    provider: NonEmptyString
    model: NonEmptyString
