import pytest

from ops_agent.contracts import IncidentState
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.investigation.domain import InvestigationConfig, InvestigationDisabledError
from ops_agent.investigation.ports import InvestigationPort
from ops_agent.investigation.service import InvestigationService


@pytest.mark.asyncio
async def test_service_is_port_and_delegates_to_fake(fake_incident_state: IncidentState) -> None:
    service = InvestigationService(FakeInvestigationEngine(), InvestigationConfig())
    plan = fake_incident_state.latest_evidence_plan
    assert plan is not None

    batch = await service.collect_batch(plan)

    assert isinstance(service, InvestigationPort)
    assert len(batch.evidence) == 4
    assert (await service.health()).status == "ok"


@pytest.mark.asyncio
async def test_disabled_service_raises_module_error(fake_incident_state: IncidentState) -> None:
    service = InvestigationService(FakeInvestigationEngine(), InvestigationConfig(enabled=False))
    plan = fake_incident_state.latest_evidence_plan
    assert plan is not None

    with pytest.raises(InvestigationDisabledError):
        await service.collect_batch(plan)
