import pytest

from ops_agent.contracts import IncidentState
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.knowledge.domain import KnowledgeConfig, KnowledgeDisabledError
from ops_agent.knowledge.ports import KnowledgePort
from ops_agent.knowledge.service import KnowledgeService


@pytest.mark.asyncio
async def test_service_is_port_and_delegates_to_fake(fake_incident_state: IncidentState) -> None:
    service = KnowledgeService(FakeKnowledgeEngine(), KnowledgeConfig())

    product = await service.resolve_product(fake_incident_state.problem)

    assert isinstance(service, KnowledgePort)
    assert product.product_name == "Order Service"
    assert (await service.health()).status == "ok"


@pytest.mark.asyncio
async def test_disabled_service_raises_module_error(fake_incident_state: IncidentState) -> None:
    service = KnowledgeService(FakeKnowledgeEngine(), KnowledgeConfig(enabled=False))

    with pytest.raises(KnowledgeDisabledError):
        await service.resolve_product(fake_incident_state.problem)
