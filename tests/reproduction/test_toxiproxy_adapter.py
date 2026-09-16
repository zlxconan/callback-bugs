from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from ops_agent.contracts import (
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    IncidentState,
)
from ops_agent.core.runtime import CoreRuntime, RuntimeConfig
from ops_agent.core.state import InMemoryStateRepository
from ops_agent.integrations.local_agent import FakeIncidentRunner, FixedClock
from ops_agent.integrations.mcp.fake import FakeApiTool, FakeBrowserTool, FakeShellTool
from ops_agent.investigation.adapters import FakeInvestigationEngine
from ops_agent.knowledge.adapters import FakeKnowledgeEngine
from ops_agent.ports import FaultInjectionToolPort
from ops_agent.reasoning.adapters import FakeReasoningEngine
from ops_agent.reproduction.adapters.browser import (
    PlaywrightBrowserAdapter,
    PlaywrightBrowserConfig,
)
from ops_agent.reproduction.adapters.fake import FakeReproductionEngine
from ops_agent.reproduction.adapters.fault_injection import (
    ToxiproxyAdapter,
    ToxiproxyConfig,
    ToxiproxyTimeoutError,
    ToxiproxyUnavailableError,
)
from ops_agent.reproduction.domain import ReproductionConfig
from ops_agent.reproduction.service import RealReproductionEngine
from tests.e2e.test_fake_incident_flow import incident_request
from tests.reproduction.playwright_lab import LabServer
from tests.reproduction.toxiproxy_lab import ToxiproxyLab


async def make_request(state: IncidentState) -> ExperimentExecutionRequest:
    plan = state.experiment_plans[0]
    prepared = await FakeReproductionEngine().prepare(plan)
    return ExperimentExecutionRequest(
        **plan.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="toxiproxy-adapter-test",
        plan=plan,
        environment=prepared,
    )


def cleanup_request(request: ExperimentExecutionRequest) -> EnvironmentCleanupRequest:
    return EnvironmentCleanupRequest(
        **request.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="toxiproxy-adapter-test",
        experiment_id=request.plan.experiment_id,
        environment_ref=request.environment.environment_ref,
    )


@dataclass
class FakeToxiproxyApi:
    requests: list[tuple[str, str, dict[str, Any] | None]] = field(default_factory=list)
    proxies: dict[str, dict[str, Any]] = field(default_factory=dict)
    toxics: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    async def handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        path = request.url.path
        self.requests.append((request.method, path, body))
        parts = path.strip("/").split("/")
        if request.method == "POST" and path == "/proxies":
            assert body is not None
            created_proxy = dict(body)
            created_proxy["listen"] = "127.0.0.1:40123"
            self.proxies[str(body["name"])] = created_proxy
            return httpx.Response(201, json=created_proxy)
        if request.method == "POST" and len(parts) == 3 and parts[2] == "toxics":
            assert body is not None
            self.toxics[(parts[1], str(body["name"]))] = dict(body)
            return httpx.Response(200, json=body)
        if request.method == "DELETE" and len(parts) == 4 and parts[2] == "toxics":
            removed = self.toxics.pop((parts[1], parts[3]), None)
            return httpx.Response(204 if removed else 404)
        if request.method == "POST" and len(parts) == 2:
            existing_proxy = self.proxies.get(parts[1])
            if existing_proxy is None:
                return httpx.Response(404)
            assert body is not None
            existing_proxy.update(body)
            return httpx.Response(200, json=existing_proxy)
        if request.method == "DELETE" and len(parts) == 2:
            removed = self.proxies.pop(parts[1], None)
            return httpx.Response(204 if removed else 404)
        return httpx.Response(404)


def build_adapter(api: FakeToxiproxyApi) -> ToxiproxyAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(api.handle))
    return ToxiproxyAdapter(
        ToxiproxyConfig(
            api_url="http://toxiproxy.test:8474",
            upstream="backend.test:8000",
            listen="0.0.0.0:0",
            latency_ms=80,
            request_timeout_seconds=0.2,
        ),
        client=client,
    )


@pytest.mark.asyncio
async def test_create_fault_and_remove_it_idempotently(
    fake_incident_state: IncidentState,
) -> None:
    request = await make_request(fake_incident_state)
    api = FakeToxiproxyApi()
    adapter = build_adapter(api)

    result = await adapter.apply(request)
    first_cleanup = await adapter.rollback(cleanup_request(request))
    duplicate_cleanup = await adapter.rollback(cleanup_request(request))

    assert isinstance(adapter, FaultInjectionToolPort)
    assert result.outputs["latency_ms"] == 80
    assert result.outputs["stream"] == "downstream"
    assert result.outputs["proxy_listen"] == "127.0.0.1:40123"
    assert first_cleanup.cleaned and duplicate_cleanup.cleaned
    assert "already absent" in duplicate_cleanup.observations[0]
    assert not api.proxies and not api.toxics
    assert not adapter.active_environment_refs
    assert any(method == "POST" and path.endswith("/toxics") for method, path, _ in api.requests)
    assert any(
        method == "POST" and path.startswith("/proxies/") and not path.endswith("/toxics")
        for method, path, _ in api.requests
    )
    assert all(path != "/reset" for _, path, _ in api.requests)


@pytest.mark.asyncio
async def test_unavailable_toxiproxy_is_typed(fake_incident_state: IncidentState) -> None:
    request = await make_request(fake_incident_state)

    async def unavailable(item: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=item)

    client = httpx.AsyncClient(transport=httpx.MockTransport(unavailable))
    adapter = ToxiproxyAdapter(
        ToxiproxyConfig(api_url="http://toxiproxy.test:8474", upstream="backend:80"),
        client=client,
    )

    with pytest.raises(ToxiproxyUnavailableError, match="unavailable"):
        await adapter.apply(request)


@pytest.mark.asyncio
async def test_toxiproxy_timeout_is_typed(fake_incident_state: IncidentState) -> None:
    request = await make_request(fake_incident_state)

    async def timeout(item: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow admin API", request=item)

    client = httpx.AsyncClient(transport=httpx.MockTransport(timeout))
    adapter = ToxiproxyAdapter(
        ToxiproxyConfig(api_url="http://toxiproxy.test:8474", upstream="backend:80"),
        client=client,
    )

    with pytest.raises(ToxiproxyTimeoutError, match="timed out"):
        await adapter.apply(request)


@pytest.mark.asyncio
async def test_engine_failure_cleans_toxic_without_masking_original_error(
    fake_incident_state: IncidentState,
) -> None:
    api = FakeToxiproxyApi()
    fault = build_adapter(api)
    engine = RealReproductionEngine(
        browser=FakeBrowserTool(fail=True),
        api=FakeApiTool(),
        shell=FakeShellTool(),
        fault=fault,
        config=ReproductionConfig(),
    )
    plan = fake_incident_state.experiment_plans[0]
    environment = await engine.prepare(plan)
    request = ExperimentExecutionRequest(
        **plan.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="toxiproxy-cleanup-test",
        plan=plan,
        environment=environment,
    )

    with pytest.raises(RuntimeError, match="configured Fake browser failure"):
        await engine.execute(request)

    assert not api.proxies and not api.toxics
    assert not fault.active_environment_refs


@pytest.mark.asyncio
async def test_experiments_have_isolated_proxy_and_toxic_names(
    fake_incident_state: IncidentState,
) -> None:
    first = await make_request(fake_incident_state)
    second = first.model_copy(
        update={
            "incident_id": "INC-DUPLICATE-ORDER-002",
            "environment": first.environment.model_copy(
                update={"environment_ref": "ENV-DUPLICATE-ORDER-002-1"}
            ),
        }
    )
    api = FakeToxiproxyApi()
    adapter = build_adapter(api)

    first_result = await adapter.apply(first)
    second_result = await adapter.apply(second)
    await adapter.rollback(cleanup_request(first))

    assert first_result.outputs["proxy_name"] != second_result.outputs["proxy_name"]
    assert first_result.outputs["toxic_name"] != second_result.outputs["toxic_name"]
    assert adapter.active_environment_refs == (second.environment.environment_ref,)
    assert list(api.proxies) == [second_result.outputs["proxy_name"]]


@pytest.mark.asyncio
async def test_real_toxiproxy_and_playwright_complete_runtime_e2e(
    fake_incident_state: IncidentState,
    fast_browser_lab: LabServer,
    toxiproxy_lab: ToxiproxyLab,
    tmp_path: Path,
) -> None:
    upstream_port = httpx.URL(fast_browser_lab.url).port
    assert upstream_port is not None
    fault = ToxiproxyAdapter(
        ToxiproxyConfig(
            api_url=toxiproxy_lab.api_url,
            upstream=f"host.docker.internal:{upstream_port}",
            listen=f"0.0.0.0:{toxiproxy_lab.proxy_port}",
            latency_ms=80,
        )
    )
    reproduction = RealReproductionEngine(
        browser=PlaywrightBrowserAdapter(
            PlaywrightBrowserConfig(
                base_url=toxiproxy_lab.proxy_url,
                screenshot_dir=tmp_path,
                navigation_timeout_ms=3_000,
                action_timeout_ms=3_000,
            )
        ),
        api=FakeApiTool(),
        shell=FakeShellTool(),
        fault=fault,
        config=ReproductionConfig(tool_timeout_seconds=5),
    )

    runner = FakeIncidentRunner(
        runtime=CoreRuntime(
            repository=InMemoryStateRepository(),
            clock=FixedClock(datetime(2026, 9, 16, 12, 0, tzinfo=UTC)),
            config=RuntimeConfig(max_reflection_loops=3),
        ),
        knowledge=FakeKnowledgeEngine(),
        reasoning=FakeReasoningEngine(),
        investigation=FakeInvestigationEngine(),
        reproduction=reproduction,
    )
    outcome = await runner.run(incident_request())

    assert outcome.final_state.runtime_stage == "completed"
    assert outcome.final_state.experiment_results[-1].outputs["request_count"] == 2
    assert outcome.final_state.experiment_results[-1].outputs["latency_ms"] == 80
    assert outcome.final_state.verification_results[-1].status == "confirmed"
    assert len(fast_browser_lab.state.requests) == 2
    assert not fault.active_environment_refs
    assert httpx.get(f"{toxiproxy_lab.api_url}/proxies", timeout=1).json() == {}
