"""Provider-neutral language model boundary."""

from typing import Protocol, runtime_checkable

from ops_agent.contracts import LLMRequest, LLMResponse


@runtime_checkable
class LLMProviderPort(Protocol):
    """Generate one raw structured response without exposing provider SDK types."""

    async def generate(self, request: LLMRequest) -> LLMResponse: ...
