"""FastAPI application composition for the external HTTP boundary."""

import os

from fastapi import FastAPI

from ops_agent.bootstrap.application import ApplicationContainer, build_application_container
from ops_agent.contracts.health import ServiceStatus
from ops_agent.investigation.api import create_router as create_investigation_router
from ops_agent.knowledge.api import create_router as create_knowledge_router
from ops_agent.reasoning.api import create_router as create_reasoning_router
from ops_agent.reproduction.api import create_router as create_reproduction_router
from ops_agent.skill_runtime import PRODUCT_SKILLS_PATH_ENV, SkillInstallationConfig


def create_app(container: ApplicationContainer | None = None) -> FastAPI:
    """Create the HTTP boundary, optionally hosting the full modular-monolith container."""

    application = FastAPI(title="Ops Agent", version="0.1.0")

    if container is not None:
        application.state.container = container
        application.state.runtime_mcp = container.runtime_mcp
        application.include_router(create_knowledge_router(container.knowledge))
        application.include_router(create_reasoning_router(container.reasoning))
        application.include_router(create_investigation_router(container.investigation))
        application.include_router(create_reproduction_router(container.reproduction))

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


app = create_app(_configured_container())
