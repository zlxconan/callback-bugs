import pytest

from ops_agent.contracts import ExperimentExecutionRequest
from ops_agent.reproduction.adapters import FakeReproductionEngine
from ops_agent.reproduction.domain import ReproductionConfig, ReproductionDisabledError
from ops_agent.reproduction.ports import ReproductionPort
from ops_agent.reproduction.service import ReproductionService


@pytest.mark.asyncio
async def test_service_is_port_and_delegates_to_fake(
    execution_request: ExperimentExecutionRequest,
) -> None:
    service = ReproductionService(FakeReproductionEngine(), ReproductionConfig())

    result = await service.execute(execution_request)

    assert isinstance(service, ReproductionPort)
    assert result.outputs["orders_created"] == 2
    assert (await service.health()).status == "ok"


@pytest.mark.asyncio
async def test_disabled_service_raises_module_error(
    execution_request: ExperimentExecutionRequest,
) -> None:
    service = ReproductionService(FakeReproductionEngine(), ReproductionConfig(enabled=False))

    with pytest.raises(ReproductionDisabledError):
        await service.execute(execution_request)
