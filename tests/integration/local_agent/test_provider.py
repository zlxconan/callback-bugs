import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from ops_agent.contracts import IncidentState, LLMRequest, RuntimeTask
from ops_agent.integrations.local_agent import (
    OpenAICompatibleProvider,
    OpenAICompatibleProviderConfig,
)
from ops_agent.ports import LLMProviderPort


@pytest.mark.asyncio
async def test_openai_compatible_provider_uses_injected_langchain_model(
    hypothesis_task: RuntimeTask,
    fake_incident_state: IncidentState,
) -> None:
    provider = OpenAICompatibleProvider(
        OpenAICompatibleProviderConfig.model_validate(
            {
                "model": "deployment-selected-model",
                "base_url": "http://localhost:8000/v1",
                "api_key": "test-key",
            }
        ),
        chat_model=FakeListChatModel(responses=['{"problem": null}']),
    )
    request = LLMRequest(
        schema_version=hypothesis_task.schema_version,
        incident_id=hypothesis_task.incident_id,
        request_id=hypothesis_task.request_id,
        timestamp=hypothesis_task.timestamp,
        source="provider-test",
        task=hypothesis_task,
        state=fake_incident_state,
        state_summary='{"problem": "bounded state"}',
        skill_names=["hypothesis-generation"],
        skill_instructions=["return structured output"],
        required_output_field="hypotheses",
        output_schema={"type": "object"},
        attempt=1,
    )

    response = await provider.generate(request)

    assert isinstance(provider, LLMProviderPort)
    assert response.content == '{"problem": null}'
    assert response.model == "deployment-selected-model"
