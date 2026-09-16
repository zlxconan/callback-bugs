"""Minimal Playwright implementation of BrowserToolPort for the MVP experiment."""

import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Request,
    Response,
    async_playwright,
)
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightApiTimeoutError
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ops_agent.contracts import ExperimentExecutionRequest, ExperimentResult, ExperimentStatus


class PlaywrightBrowserConfig(BaseModel):
    """Small, explicit operation profile used by the duplicate-create MVP."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(min_length=1)
    screenshot_dir: Path
    browser_name: str = "chromium"
    headless: bool = True
    business_id: str = Field(default="BIZ-001", min_length=1)
    business_id_selector: str = Field(default="#business-id", min_length=1)
    create_button_selector: str = Field(default="#create-order", min_length=1)
    success_selector: str = Field(
        default="#status[data-final-status='success']",
        min_length=1,
    )
    navigation_timeout_ms: int = Field(default=2_000, gt=0)
    action_timeout_ms: int = Field(default=2_000, gt=0)


class BrowserObservation(BaseModel):
    """Adapter-local normalized browser observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: str
    request_count: int = Field(ge=0)
    first_backend_status: str
    retry_detected: bool
    database_record_count: int = Field(ge=0)
    request_ids: list[str]
    trace_id: str
    page_events: list[str]
    screenshot_uri: str
    network_requests: list[dict[str, str]]
    response_statuses: list[int]


class PlaywrightBrowserError(RuntimeError):
    """Base error for the concrete Playwright adapter."""


class PlaywrightTimeoutError(PlaywrightBrowserError):
    """The page did not reach the required state before the action deadline."""


class PlaywrightSelectorError(PlaywrightBrowserError):
    """A required MVP selector could not be resolved."""


class PlaywrightPageUnavailableError(PlaywrightBrowserError):
    """The configured test page could not be opened."""


class PlaywrightBrowserAdapter:
    """Open, fill, click, wait, inspect, screenshot and close one isolated page."""

    def __init__(self, config: PlaywrightBrowserConfig) -> None:
        self._config = config
        self._active_browser_count = 0
        self._cleanup_errors: list[str] = []

    @property
    def active_browser_count(self) -> int:
        return self._active_browser_count

    @property
    def cleanup_errors(self) -> tuple[str, ...]:
        return tuple(self._cleanup_errors)

    async def execute(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        self._config.screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = self._config.screenshot_dir / (
            f"{request.incident_id}-{request.plan.experiment_id}.png"
        )
        network_requests: list[dict[str, str]] = []
        response_statuses: list[int] = []
        stage = "launch"
        self._cleanup_errors.clear()

        try:
            async with async_playwright() as playwright:
                browser_type = getattr(playwright, self._config.browser_name, None)
                if browser_type is None:
                    raise PlaywrightBrowserError(
                        f"unsupported Playwright browser: {self._config.browser_name}"
                    )
                browser: Browser = await browser_type.launch(headless=self._config.headless)
                self._active_browser_count += 1
                context: BrowserContext | None = None
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    self._observe_network(page, network_requests, response_statuses)

                    stage = "navigation"
                    await page.goto(
                        self._config.base_url,
                        wait_until="domcontentloaded",
                        timeout=self._config.navigation_timeout_ms,
                    )
                    stage = "business selector"
                    await page.locator(self._config.business_id_selector).fill(
                        self._config.business_id,
                        timeout=self._config.action_timeout_ms,
                    )
                    stage = "create selector"
                    await page.locator(self._config.create_button_selector).click(
                        timeout=self._config.action_timeout_ms,
                    )
                    stage = "success wait"
                    status = page.locator(self._config.success_selector)
                    await status.wait_for(state="visible", timeout=self._config.action_timeout_ms)
                    stage = "state extraction"
                    observation = await self._extract_observation(
                        status,
                        screenshot_path,
                        page,
                        network_requests,
                        response_statuses,
                    )
                    return self.build_result(request, observation)
                finally:
                    await self._close(context, browser)
        except PlaywrightApiTimeoutError as error:
            if stage in {"business selector", "create selector"}:
                raise PlaywrightSelectorError(f"required selector unavailable: {stage}") from error
            if stage == "navigation":
                raise PlaywrightPageUnavailableError(
                    f"page navigation timed out: {self._config.base_url}"
                ) from error
            raise PlaywrightTimeoutError(f"browser operation timed out during {stage}") from error
        except PlaywrightBrowserError:
            raise
        except PlaywrightError as error:
            if stage in {"launch", "navigation"}:
                raise PlaywrightPageUnavailableError(
                    f"page unavailable: {self._config.base_url}"
                ) from error
            raise PlaywrightBrowserError(f"Playwright failed during {stage}: {error}") from error

    async def _close(self, context: BrowserContext | None, browser: Browser) -> None:
        if context is not None:
            try:
                await context.close()
            except PlaywrightError as error:
                self._cleanup_errors.append(str(error))
        try:
            await browser.close()
        except PlaywrightError as error:
            self._cleanup_errors.append(str(error))
        finally:
            self._active_browser_count -= 1

    def build_result(
        self,
        request: ExperimentExecutionRequest,
        observation: BrowserObservation,
    ) -> ExperimentResult:
        evidence_id = (
            f"E-BROWSER-{request.incident_id.removeprefix('INC-')}-"
            f"{request.plan.experiment_id.removeprefix('EXP-')}"
        )
        outputs: dict[str, JsonValue] = observation.model_dump(mode="json")
        outputs["screenshot_path"] = str(Path(urlparse(observation.screenshot_uri).path))
        return ExperimentResult(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="playwright-browser-adapter",
            metadata={"browser": self._config.browser_name, "headless": self._config.headless},
            experiment_id=request.plan.experiment_id,
            status=ExperimentStatus.SUCCEEDED,
            started_at=request.timestamp,
            completed_at=request.timestamp,
            observations=[
                "Playwright opened the test page and triggered the create action.",
                "The page observed a timeout, retry and successful final state.",
                f"Screenshot captured at {observation.screenshot_uri}.",
            ],
            evidence_ids=[evidence_id],
            outputs=outputs,
        )

    @staticmethod
    def _observe_network(
        page: Page,
        requests: list[dict[str, str]],
        response_statuses: list[int],
    ) -> None:
        def record_request(item: Request) -> None:
            if item.method == "POST" and urlparse(item.url).path == "/orders":
                requests.append(
                    {
                        "method": item.method,
                        "url": item.url,
                        "request_id": item.headers.get("x-request-id", ""),
                        "trace_id": item.headers.get("x-trace-id", ""),
                    }
                )

        def record_response(item: Response) -> None:
            if urlparse(item.url).path == "/orders":
                response_statuses.append(item.status)

        page.on("request", record_request)
        page.on("response", record_response)

    @staticmethod
    async def _extract_observation(
        status: Locator,
        screenshot_path: Path,
        page: Page,
        network_requests: list[dict[str, str]],
        response_statuses: list[int],
    ) -> BrowserObservation:
        locator = status
        business_id = await locator.get_attribute("data-business-id")
        backend_status = await locator.get_attribute("data-backend-status")
        retry_detected = await locator.get_attribute("data-retry-detected")
        record_count = await locator.get_attribute("data-database-record-count")
        events_json = await locator.get_attribute("data-events")
        if (
            business_id is None
            or backend_status is None
            or retry_detected is None
            or record_count is None
            or events_json is None
        ):
            raise PlaywrightBrowserError("required page state is incomplete")
        try:
            page_events = json.loads(events_json)
            database_record_count = int(record_count)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise PlaywrightBrowserError("required page state is invalid") from error
        if not isinstance(page_events, list) or not all(
            isinstance(item, str) for item in page_events
        ):
            raise PlaywrightBrowserError("page events must be a list of strings")
        await page.screenshot(path=screenshot_path, full_page=True)
        request_ids = [item["request_id"] for item in network_requests]
        trace_ids = [item["trace_id"] for item in network_requests if item["trace_id"]]
        return BrowserObservation(
            business_id=business_id,
            request_count=len(network_requests),
            first_backend_status=backend_status,
            retry_detected=retry_detected == "true",
            database_record_count=database_record_count,
            request_ids=request_ids,
            trace_id=trace_ids[0] if trace_ids else "",
            page_events=page_events,
            screenshot_uri=screenshot_path.resolve().as_uri(),
            network_requests=network_requests,
            response_statuses=response_statuses,
        )
