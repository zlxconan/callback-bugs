"""Local and small-model Agent Host integration boundary."""

from ops_agent.integrations.local_agent.agent import LocalAgentConfig, LocalSmallModelAgent
from ops_agent.integrations.local_agent.fake_runner import (
    FakeIncidentOutcome,
    FakeIncidentRunner,
    FakeTaskReasoner,
    FixedClock,
)
from ops_agent.integrations.local_agent.providers import (
    FakeLLMProvider,
    OpenAICompatibleProvider,
    OpenAICompatibleProviderConfig,
)
from ops_agent.integrations.local_agent.runner import LocalAgentOutcome, LocalAgentRunner
from ops_agent.integrations.local_agent.validator import (
    StructuredOutputValidationError,
    StructuredTaskOutputValidator,
)

__all__ = [
    "FakeIncidentOutcome",
    "FakeIncidentRunner",
    "FakeLLMProvider",
    "FakeTaskReasoner",
    "FixedClock",
    "LocalAgentConfig",
    "LocalAgentOutcome",
    "LocalAgentRunner",
    "LocalSmallModelAgent",
    "OpenAICompatibleProvider",
    "OpenAICompatibleProviderConfig",
    "StructuredOutputValidationError",
    "StructuredTaskOutputValidator",
]
