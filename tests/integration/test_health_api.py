import httpx
import pytest
from fastapi import FastAPI

from ops_agent.api.app import create_app


def test_app_can_be_created() -> None:
    app = create_app()

    assert isinstance(app, FastAPI)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_body"),
    [
        ("/health", {"status": "ok"}),
        ("/ready", {"status": "ready"}),
    ],
)
async def test_service_status_endpoints(
    path: str,
    expected_body: dict[str, str],
) -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(path)

    assert response.status_code == 200
    assert response.json() == expected_body
