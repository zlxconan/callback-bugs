"""Deployment wiring tests for the real browser and fault adapters."""

from pathlib import Path

import pytest

from ops_agent.bootstrap.application import build_application_container
from ops_agent.bootstrap.reproduction import ReproductionInstallationConfig
from ops_agent.skill_runtime import SkillInstallationConfig

ROOT = Path(__file__).parents[2]


def test_reproduction_installation_config_reads_real_adapter_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "OPS_AGENT_REPRODUCTION_ADAPTER": "playwright-toxiproxy",
        "OPS_AGENT_BROWSER_BASE_URL": "http://toxiproxy:8666/",
        "OPS_AGENT_TOXIPROXY_API_URL": "http://toxiproxy:8474",
        "OPS_AGENT_TOXIPROXY_UPSTREAM": "backend:8080",
        "OPS_AGENT_TOXIPROXY_LISTEN": "0.0.0.0:8666",
        "OPS_AGENT_TOXIPROXY_LATENCY_MS": "80",
        "OPS_AGENT_REPRODUCTION_SCREENSHOT_DIR": "/tmp/ops-agent/screenshots",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    config = ReproductionInstallationConfig.from_env()

    assert config.adapter == "playwright-toxiproxy"
    assert config.browser_base_url == "http://toxiproxy:8666/"
    assert config.toxiproxy_upstream == "backend:8080"
    assert config.toxiproxy_latency_ms == 80


@pytest.mark.asyncio
async def test_application_can_wire_real_reproduction_adapters() -> None:
    container = build_application_container(
        SkillInstallationConfig(
            builtin_skills_path=ROOT / "skills" / "builtin",
            product_skills_path=ROOT / "tests" / "fixtures" / "product-skills",
        ),
        reproduction_config=ReproductionInstallationConfig(
            adapter="playwright-toxiproxy",
            browser_base_url="http://toxiproxy:8666/",
            toxiproxy_api_url="http://toxiproxy:8474",
            toxiproxy_upstream="backend:8080",
            toxiproxy_listen="0.0.0.0:8666",
        ),
    )

    health = await container.reproduction.health()

    assert health.status == "ok"
    assert health.adapter == "playwright-toxiproxy"
