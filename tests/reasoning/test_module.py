import pytest

from ops_agent.contracts import HypothesisGenerationRequest
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reasoning.domain import ReasoningConfig, ReasoningDisabledError
from ops_agent.reasoning.ports import ReasoningPort
from ops_agent.reasoning.service import ReasoningService


@pytest.mark.asyncio
async def test_service_is_port_and_delegates_to_fake(
    hypothesis_request: HypothesisGenerationRequest,
) -> None:
    service = ReasoningService(FakeReasoningEngine(), ReasoningConfig())

    hypotheses = await service.generate_hypotheses(hypothesis_request)

    assert isinstance(service, ReasoningPort)
    assert hypotheses.prioritized_hypothesis_ids[0] == "H-1"
    assert (await service.health()).status == "ok"


@pytest.mark.asyncio
async def test_disabled_service_raises_module_error(
    hypothesis_request: HypothesisGenerationRequest,
) -> None:
    service = ReasoningService(FakeReasoningEngine(), ReasoningConfig(enabled=False))

    with pytest.raises(ReasoningDisabledError):
        await service.generate_hypotheses(hypothesis_request)
