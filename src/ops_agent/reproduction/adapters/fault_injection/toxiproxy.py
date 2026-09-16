"""Experiment-scoped Toxiproxy HTTP API implementation of FaultInjectionToolPort."""

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ops_agent.contracts import (
    CleanupResult,
    EnvironmentCleanupRequest,
    ExperimentExecutionRequest,
    ExperimentResult,
    ExperimentStatus,
)


class ToxiproxyConfig(BaseModel):
    """Explicit connection and downstream-latency settings for one adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_url: str = Field(min_length=1)
    upstream: str = Field(min_length=1)
    listen: str = Field(default="0.0.0.0:0", min_length=1)
    latency_ms: int = Field(default=80, gt=0)
    jitter_ms: int = Field(default=0, ge=0)
    request_timeout_seconds: float = Field(default=2.0, gt=0)
    proxy_name_prefix: str = Field(default="ops-agent", pattern=r"^[a-z0-9-]+$")

    @field_validator("api_url")
    @classmethod
    def normalize_api_url(cls, value: str) -> str:
        return value.rstrip("/")


class ToxiproxyError(RuntimeError):
    """Base error for the Toxiproxy adapter."""


class ToxiproxyUnavailableError(ToxiproxyError):
    """The Toxiproxy control API could not be reached."""


class ToxiproxyTimeoutError(ToxiproxyError):
    """The Toxiproxy control API exceeded its operation deadline."""


class ToxiproxyApiError(ToxiproxyError):
    """The Toxiproxy control API rejected an operation."""


class _ProxyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    listen: str
    upstream: str
    enabled: bool = True


@dataclass(frozen=True)
class _FaultResource:
    environment_ref: str
    proxy_name: str
    toxic_name: str
    listen: str


class ToxiproxyAdapter:
    """Own one proxy and downstream latency toxic per experiment environment."""

    def __init__(
        self,
        config: ToxiproxyConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._resources: dict[str, _FaultResource] = {}
        self._cleanup_errors: list[str] = []

    @property
    def active_environment_refs(self) -> tuple[str, ...]:
        return tuple(sorted(self._resources))

    @property
    def cleanup_errors(self) -> tuple[str, ...]:
        return tuple(self._cleanup_errors)

    async def apply(self, request: ExperimentExecutionRequest) -> ExperimentResult:
        resource = self._resource(request.environment.environment_ref)
        self._cleanup_errors.clear()
        await self._remove_owned_resource(resource, tolerate_missing=True)
        try:
            resource = await self._create_proxy(resource)
            await self._enable_latency(resource)
        except Exception:
            try:
                await self._remove_owned_resource(resource, tolerate_missing=True)
            except ToxiproxyError as cleanup_error:
                self._cleanup_errors.append(str(cleanup_error))
            raise
        self._resources[resource.environment_ref] = resource
        evidence_id = (
            f"E-TOXIPROXY-{request.incident_id.removeprefix('INC-')}-"
            f"{request.plan.experiment_id.removeprefix('EXP-')}"
        )
        return ExperimentResult(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="toxiproxy-adapter",
            metadata={"adapter": "toxiproxy", "environment_scoped": True},
            experiment_id=request.plan.experiment_id,
            status=ExperimentStatus.SUCCEEDED,
            started_at=request.timestamp,
            completed_at=request.timestamp,
            observations=[
                f"Created isolated proxy {resource.proxy_name}.",
                f"Enabled {self._config.latency_ms}ms downstream latency toxic.",
            ],
            evidence_ids=[evidence_id],
            outputs={
                "proxy_name": resource.proxy_name,
                "proxy_listen": resource.listen,
                "proxy_upstream": self._config.upstream,
                "toxic_name": resource.toxic_name,
                "latency_ms": self._config.latency_ms,
                "jitter_ms": self._config.jitter_ms,
                "stream": "downstream",
            },
        )

    async def rollback(self, request: EnvironmentCleanupRequest) -> CleanupResult:
        environment_ref = request.environment_ref
        resource = self._resources.get(environment_ref, self._resource(environment_ref))
        removed = await self._remove_owned_resource(resource, tolerate_missing=True)
        self._resources.pop(environment_ref, None)
        observation = (
            f"Removed toxic and proxy for {environment_ref}."
            if removed
            else f"Toxiproxy resources for {environment_ref} were already absent."
        )
        return CleanupResult(
            **request.model_dump(
                include={"schema_version", "incident_id", "request_id", "timestamp"}
            ),
            source="toxiproxy-adapter",
            metadata={"adapter": "toxiproxy", "environment_scoped": True},
            experiment_id=request.experiment_id,
            environment_ref=environment_ref,
            cleaned=True,
            observations=[observation],
        )

    async def _create_proxy(self, resource: _FaultResource) -> _FaultResource:
        response = await self._request(
            "POST",
            "/proxies",
            json={
                "name": resource.proxy_name,
                "listen": self._config.listen,
                "upstream": self._config.upstream,
                "enabled": True,
            },
            accepted={200, 201},
        )
        proxy = _ProxyResponse.model_validate(response.json())
        return _FaultResource(
            environment_ref=resource.environment_ref,
            proxy_name=resource.proxy_name,
            toxic_name=resource.toxic_name,
            listen=proxy.listen,
        )

    async def _enable_latency(self, resource: _FaultResource) -> None:
        proxy = quote(resource.proxy_name, safe="")
        await self._request(
            "POST",
            f"/proxies/{proxy}/toxics",
            json={
                "name": resource.toxic_name,
                "type": "latency",
                "stream": "downstream",
                "toxicity": 1.0,
                "attributes": {
                    "latency": self._config.latency_ms,
                    "jitter": self._config.jitter_ms,
                },
            },
            accepted={200, 201},
        )

    async def _remove_owned_resource(
        self,
        resource: _FaultResource,
        *,
        tolerate_missing: bool,
    ) -> bool:
        proxy = quote(resource.proxy_name, safe="")
        toxic = quote(resource.toxic_name, safe="")
        accepted = {200, 204, 404} if tolerate_missing else {200, 204}
        toxic_response = await self._request(
            "DELETE",
            f"/proxies/{proxy}/toxics/{toxic}",
            accepted=accepted,
        )
        reset_response = await self._request(
            "POST",
            f"/proxies/{proxy}",
            json={"enabled": True},
            accepted=accepted,
        )
        proxy_response = await self._request(
            "DELETE",
            f"/proxies/{proxy}",
            accepted=accepted,
        )
        return (
            toxic_response.status_code != 404
            or proxy_response.status_code != 404
            or (reset_response.status_code != 404)
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
        accepted: set[int],
    ) -> httpx.Response:
        url = f"{self._config.api_url}{path}"
        try:
            if self._client is not None:
                response = await self._client.request(
                    method,
                    url,
                    json=json,
                    timeout=self._config.request_timeout_seconds,
                )
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method,
                        url,
                        json=json,
                        timeout=self._config.request_timeout_seconds,
                    )
        except httpx.TimeoutException as error:
            raise ToxiproxyTimeoutError(f"Toxiproxy operation {method} {path} timed out") from error
        except httpx.RequestError as error:
            raise ToxiproxyUnavailableError(
                f"Toxiproxy unavailable during {method} {path}: {error}"
            ) from error
        if response.status_code not in accepted:
            raise ToxiproxyApiError(
                f"Toxiproxy rejected {method} {path} with HTTP {response.status_code}"
            )
        return response

    def _resource(self, environment_ref: str) -> _FaultResource:
        normalized = re.sub(r"[^a-z0-9]+", "-", environment_ref.lower()).strip("-")
        digest = hashlib.sha256(environment_ref.encode()).hexdigest()[:10]
        suffix = f"{normalized[:32]}-{digest}"
        return _FaultResource(
            environment_ref=environment_ref,
            proxy_name=f"{self._config.proxy_name_prefix}-{suffix}",
            toxic_name=f"latency-{suffix}",
            listen=self._config.listen,
        )
