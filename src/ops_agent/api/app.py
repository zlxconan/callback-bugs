"""FastAPI application composition for the external HTTP boundary."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from ops_agent.bootstrap.application import ApplicationContainer, build_application_container
from ops_agent.contracts.health import ServiceStatus
from ops_agent.integrations.mcp.runtime import create_runtime_mcp_server
from ops_agent.investigation.api import create_router as create_investigation_router
from ops_agent.knowledge.api import create_router as create_knowledge_router
from ops_agent.reasoning.api import create_router as create_reasoning_router
from ops_agent.reproduction.api import create_router as create_reproduction_router
from ops_agent.skill_runtime import PRODUCT_SKILLS_PATH_ENV, SkillInstallationConfig


def create_app(container: ApplicationContainer | None = None) -> FastAPI:
    """Create the HTTP boundary, optionally hosting the full modular-monolith container."""

    runtime_mcp_server: MCPServer | None = None
    runtime_mcp_app = None
    if container is not None:
        runtime_mcp_server = create_runtime_mcp_server(container.runtime_mcp)
        runtime_mcp_app = runtime_mcp_server.streamable_http_app(
            streamable_http_path="/",
            stateless_http=True,
            json_response=True,
            transport_security=TransportSecuritySettings(
                allowed_hosts=_mcp_allowed_hosts(),
            ),
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if runtime_mcp_server is None:
            yield
            return
        async with runtime_mcp_server.session_manager.run():
            yield

    application = FastAPI(title="Ops Agent", version="0.1.0", lifespan=lifespan)

    if container is not None:
        assert runtime_mcp_server is not None and runtime_mcp_app is not None
        application.state.container = container
        application.state.runtime_mcp = container.runtime_mcp
        application.state.runtime_mcp_server = runtime_mcp_server
        application.include_router(create_knowledge_router(container.knowledge))
        application.include_router(create_reasoning_router(container.reasoning))
        application.include_router(create_investigation_router(container.investigation))
        application.include_router(create_reproduction_router(container.reproduction))
        application.mount("/mcp/runtime", runtime_mcp_app, name="runtime-mcp")

    @application.get("/health", response_model=ServiceStatus, tags=["system"])
    async def health() -> ServiceStatus:
        return ServiceStatus(status="ok")

    @application.get("/ready", response_model=ServiceStatus, tags=["system"])
    async def ready() -> ServiceStatus:
        # Step 1 has no external dependencies, so process readiness is sufficient.
        return ServiceStatus(status="ready")

    return application


def _configured_container() -> ApplicationContainer | None:
    if not os.environ.get(PRODUCT_SKILLS_PATH_ENV):
        return None
    return build_application_container(SkillInstallationConfig.from_env())


def _mcp_allowed_hosts() -> list[str]:
    configured = os.environ.get(
        "OPS_AGENT_MCP_ALLOWED_HOSTS",
        "127.0.0.1:8000,localhost:8000,testserver,test",
    )
    return [host.strip() for host in configured.split(",") if host.strip()]


app = create_app(_configured_container())
