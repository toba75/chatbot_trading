from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

from app.platform.configuration import ApplicationConfiguration
from app.platform.orchestrator_composition import OrchestratorCompositionRoot
from app.platform.orchestrator_contract_routers import (
    build_conversation_router,
    build_evaluation_router,
    build_health_router,
    build_indexing_router,
    build_search_router,
)


CompositionRootFactory = Callable[[ApplicationConfiguration], OrchestratorCompositionRoot]


def create_orchestrator_app(
    *,
    configuration: ApplicationConfiguration,
    composition_root_factory: CompositionRootFactory,
) -> FastAPI:
    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        composition_root = composition_root_factory(configuration)
        if not isinstance(composition_root, OrchestratorCompositionRoot):
            raise TypeError("composition_root_factory doit construire OrchestratorCompositionRoot")

        await composition_root.open()
        application.state.composition_root = composition_root
        try:
            yield
        finally:
            await composition_root.close()

    application = FastAPI(lifespan=lifespan)
    application.include_router(build_health_router())
    application.include_router(build_conversation_router(configuration))
    application.include_router(build_evaluation_router(configuration))
    application.include_router(build_search_router())
    application.include_router(build_indexing_router())

    @application.get("/ready")
    async def ready() -> JSONResponse:
        composition_root = application.state.composition_root
        dependencies = composition_root.readiness_snapshot()
        is_ready = all(dependency.status == "ready" for dependency in dependencies)
        return JSONResponse(
            status_code=200 if is_ready else 503,
            content={
                "service": "orchestrator-api",
                "status": "ready" if is_ready else "not_ready",
                "dependencies": [asdict(dependency) for dependency in dependencies],
            },
        )

    return application


def serve_orchestrator_app(
    *,
    configuration: ApplicationConfiguration,
    composition_root_factory: CompositionRootFactory,
) -> None:
    application = create_orchestrator_app(
        configuration=configuration,
        composition_root_factory=composition_root_factory,
    )
    uvicorn.run(
        application,
        host=configuration.services.api.bind_host,
        port=configuration.services.api.port,
    )


__all__ = [
    "CompositionRootFactory",
    "create_orchestrator_app",
    "serve_orchestrator_app",
]
