"""Acceptance tests for the single-process deployment composition root."""

from pathlib import Path

import httpx
import pytest

from ops_agent.api.app import create_app
from ops_agent.bootstrap.application import build_application_container
from ops_agent.skill_runtime import SkillInstallationConfig

ROOT = Path(__file__).parents[2]


@pytest.mark.asyncio
async def test_deployment_container_exposes_modules_and_runtime_mcp() -> None:
    container = build_application_container(
        SkillInstallationConfig(
            builtin_skills_path=ROOT / "skills" / "builtin",
            product_skills_path=ROOT / "tests" / "fixtures" / "product-skills",
        )
    )
    app = create_app(container)
    transport = httpx.ASGITransport(app=app)

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            responses = {
                path: await client.get(path)
                for path in (
                    "/health",
                    "/ready",
                    "/knowledge/health",
                    "/reasoning/health",
                    "/investigation/health",
                    "/reproduction/health",
                )
            }

    assert all(response.status_code == 200 for response in responses.values())
    assert app.state.container is container
    assert app.state.runtime_mcp.names() == (
        "incident_start",
        "incident_next",
        "incident_submit",
        "incident_get_state",
        "incident_finish",
    )
    assert len(container.skills.builtin_skills) == 6
