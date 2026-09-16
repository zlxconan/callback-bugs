from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from ops_agent.contracts import ExperimentExecutionRequest, IncidentState
from ops_agent.ports import BrowserToolPort
from ops_agent.reproduction.adapters.browser.playwright import (
    BrowserObservation,
    PlaywrightBrowserAdapter,
    PlaywrightBrowserConfig,
    PlaywrightPageUnavailableError,
    PlaywrightSelectorError,
    PlaywrightTimeoutError,
)
from ops_agent.reproduction.adapters.fake import FakeReproductionEngine
from tests.reproduction.playwright_lab import LabServer


async def make_request(state: IncidentState) -> ExperimentExecutionRequest:
    plan = state.experiment_plans[0]
    environment = await FakeReproductionEngine().prepare(plan)
    return ExperimentExecutionRequest(
        **plan.model_dump(include={"schema_version", "incident_id", "request_id", "timestamp"}),
        source="playwright-adapter-test",
        plan=plan,
        environment=environment,
    )


@pytest.mark.asyncio
async def test_adapter_unit_maps_observation_to_experiment_contract(
    fake_incident_state: IncidentState,
    tmp_path: Path,
) -> None:
    request = await make_request(fake_incident_state)
    adapter = PlaywrightBrowserAdapter(
        PlaywrightBrowserConfig(base_url="http://example.invalid", screenshot_dir=tmp_path)
    )
    observation = BrowserObservation(
        business_id="BIZ-001",
        request_count=2,
        first_backend_status="success",
        retry_detected=True,
        database_record_count=2,
        request_ids=["HTTP-REQ-1", "HTTP-REQ-2"],
        trace_id="TRACE-001",
        page_events=["submit", "timeout", "retry", "success"],
        screenshot_uri=(tmp_path / "shot.png").resolve().as_uri(),
        network_requests=[{"method": "POST", "url": "http://example.invalid/orders"}],
        response_statuses=[200],
    )

    result = adapter.build_result(request, observation)

    assert isinstance(adapter, BrowserToolPort)
    assert result.outputs["request_count"] == 2
    assert result.outputs["screenshot_uri"] == observation.screenshot_uri
    assert result.evidence_ids == ["E-BROWSER-DUPLICATE-ORDER-001-1"]
    assert type(result).model_validate_json(result.model_dump_json()) == result


@pytest.mark.asyncio
async def test_real_browser_runs_local_timeout_retry_page_and_captures_evidence(
    fake_incident_state: IncidentState,
    browser_lab: LabServer,
    tmp_path: Path,
) -> None:
    request = await make_request(fake_incident_state)
    adapter = PlaywrightBrowserAdapter(
        PlaywrightBrowserConfig(base_url=browser_lab.url, screenshot_dir=tmp_path)
    )

    result = await adapter.execute(request)

    screenshot = Path(cast(str, result.outputs["screenshot_path"]))
    assert result.outputs["business_id"] == "BIZ-001"
    assert result.outputs["request_count"] == 2
    assert result.outputs["retry_detected"] is True
    assert result.outputs["database_record_count"] == 2
    assert result.outputs["page_events"] == ["submit", "timeout", "retry", "success"]
    assert result.evidence_ids == ["E-BROWSER-DUPLICATE-ORDER-001-1"]
    assert result.outputs["response_statuses"] == [200]
    assert screenshot.is_file() and screenshot.stat().st_size > 0
    assert result.outputs["screenshot_uri"] == screenshot.resolve().as_uri()
    assert adapter.active_browser_count == 0
    assert adapter.cleanup_errors == ()
    assert len(browser_lab.state.requests) == 2


@pytest.mark.asyncio
async def test_selector_not_found_is_typed_and_browser_is_closed(
    fake_incident_state: IncidentState,
    browser_lab: LabServer,
    tmp_path: Path,
) -> None:
    adapter = PlaywrightBrowserAdapter(
        PlaywrightBrowserConfig(
            base_url=browser_lab.url,
            screenshot_dir=tmp_path,
            business_id_selector="#missing-business-id",
            action_timeout_ms=100,
        )
    )

    with pytest.raises(PlaywrightSelectorError):
        await adapter.execute(await make_request(fake_incident_state))

    assert adapter.active_browser_count == 0


@pytest.mark.asyncio
async def test_page_unavailable_is_typed_and_browser_is_closed(
    fake_incident_state: IncidentState,
    tmp_path: Path,
) -> None:
    adapter = PlaywrightBrowserAdapter(
        PlaywrightBrowserConfig(
            base_url="http://127.0.0.1:1/",
            screenshot_dir=tmp_path,
            navigation_timeout_ms=200,
        )
    )

    with pytest.raises(PlaywrightPageUnavailableError):
        await adapter.execute(await make_request(fake_incident_state))

    assert adapter.active_browser_count == 0


@pytest.mark.asyncio
async def test_wait_timeout_is_typed_and_browser_is_closed(
    fake_incident_state: IncidentState,
    browser_lab: LabServer,
    tmp_path: Path,
) -> None:
    adapter = PlaywrightBrowserAdapter(
        PlaywrightBrowserConfig(
            base_url=browser_lab.url,
            screenshot_dir=tmp_path,
            success_selector="#never-completes",
            action_timeout_ms=100,
        )
    )

    with pytest.raises(PlaywrightTimeoutError):
        await adapter.execute(await make_request(fake_incident_state))

    assert adapter.active_browser_count == 0
