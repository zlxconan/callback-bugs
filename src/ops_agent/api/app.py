"""FastAPI application composition for the external HTTP boundary."""

from fastapi import FastAPI

from ops_agent.contracts.health import ServiceStatus


def create_app() -> FastAPI:
    """Create the HTTP application without initializing engine implementations."""

    application = FastAPI(title="Ops Agent", version="0.1.0")

    @application.get("/health", response_model=ServiceStatus, tags=["system"])
    async def health() -> ServiceStatus:
        return ServiceStatus(status="ok")

    @application.get("/ready", response_model=ServiceStatus, tags=["system"])
    async def ready() -> ServiceStatus:
        # Step 1 has no external dependencies, so process readiness is sufficient.
        return ServiceStatus(status="ready")

    return application


app = create_app()
