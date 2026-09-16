"""Deployment composition for Fake or Playwright/Toxiproxy reproduction adapters."""

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ops_agent.integrations.mcp.fake import FakeApiTool, FakeShellTool
from ops_agent.reproduction.adapters import FakeReproductionEngine
from ops_agent.reproduction.adapters.browser import PlaywrightBrowserAdapter, PlaywrightBrowserConfig
from ops_agent.reproduction.adapters.fault_injection import ToxiproxyAdapter, ToxiproxyConfig
from ops_agent.reproduction.domain import ReproductionConfig
from ops_agent.reproduction.service import RealReproductionEngine, ReproductionService


class ReproductionInstallationConfig(BaseModel):
    """Environment-backed configuration used only at the deployment boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter: Literal["fake", "playwright-toxiproxy"] = "fake"
    browser_base_url: str = Field(default="http://127.0.0.1:8080/", min_length=1)
    browser_screenshot_dir: Path = Path("/tmp/ops-agent/screenshots")
    browser_headless: bool = True
    browser_navigation_timeout_ms: int = Field(default=5_000, gt=0)
    browser_action_timeout_ms: int = Field(default=5_000, gt=0)
    toxiproxy_api_url: str = Field(default="http://127.0.0.1:8474", min_length=1)
    toxiproxy_upstream: str = Field(default="127.0.0.1:8080", min_length=1)
    toxiproxy_listen: str = Field(default="0.0.0.0:8666", min_length=1)
    toxiproxy_latency_ms: int = Field(default=80, gt=0)
    toxiproxy_jitter_ms: int = Field(default=0, ge=0)
    toxiproxy_request_timeout_seconds: float = Field(default=2.0, gt=0)
    tool_timeout_seconds: float = Field(default=10.0, gt=0)

    @classmethod
    def from_env(cls) -> "ReproductionInstallationConfig":
        mapping = {
            "adapter": "OPS_AGENT_REPRODUCTION_ADAPTER",
            "browser_base_url": "OPS_AGENT_BROWSER_BASE_URL",
            "browser_screenshot_dir": "OPS_AGENT_REPRODUCTION_SCREENSHOT_DIR",
            "browser_headless": "OPS_AGENT_BROWSER_HEADLESS",
            "browser_navigation_timeout_ms": "OPS_AGENT_BROWSER_NAVIGATION_TIMEOUT_MS",
            "browser_action_timeout_ms": "OPS_AGENT_BROWSER_ACTION_TIMEOUT_MS",
            "toxiproxy_api_url": "OPS_AGENT_TOXIPROXY_API_URL",
            "toxiproxy_upstream": "OPS_AGENT_TOXIPROXY_UPSTREAM",
            "toxiproxy_listen": "OPS_AGENT_TOXIPROXY_LISTEN",
            "toxiproxy_latency_ms": "OPS_AGENT_TOXIPROXY_LATENCY_MS",
            "toxiproxy_jitter_ms": "OPS_AGENT_TOXIPROXY_JITTER_MS",
            "toxiproxy_request_timeout_seconds": "OPS_AGENT_TOXIPROXY_REQUEST_TIMEOUT_SECONDS",
            "tool_timeout_seconds": "OPS_AGENT_REPRODUCTION_TOOL_TIMEOUT_SECONDS",
        }
        values = {
            field: value
            for field, environment_name in mapping.items()
            if (value := os.environ.get(environment_name)) is not None
        }
        return cls.model_validate(values)


def build_reproduction_service(config: ReproductionInstallationConfig) -> ReproductionService:
    """Select deployment adapters without leaking them into Engine services or domain code."""

    if config.adapter == "fake":
        return ReproductionService(
            FakeReproductionEngine(),
            ReproductionConfig(adapter_name="fake"),
        )

    module_config = ReproductionConfig(
        adapter_name="playwright-toxiproxy",
        tool_timeout_seconds=config.tool_timeout_seconds,
    )
    engine = RealReproductionEngine(
        browser=PlaywrightBrowserAdapter(
            PlaywrightBrowserConfig(
                base_url=config.browser_base_url,
                screenshot_dir=config.browser_screenshot_dir,
                headless=config.browser_headless,
                navigation_timeout_ms=config.browser_navigation_timeout_ms,
                action_timeout_ms=config.browser_action_timeout_ms,
            )
        ),
        api=FakeApiTool(),
        shell=FakeShellTool(),
        fault=ToxiproxyAdapter(
            ToxiproxyConfig(
                api_url=config.toxiproxy_api_url,
                upstream=config.toxiproxy_upstream,
                listen=config.toxiproxy_listen,
                latency_ms=config.toxiproxy_latency_ms,
                jitter_ms=config.toxiproxy_jitter_ms,
                request_timeout_seconds=config.toxiproxy_request_timeout_seconds,
            )
        ),
        config=module_config,
    )
    return ReproductionService(engine, module_config)
