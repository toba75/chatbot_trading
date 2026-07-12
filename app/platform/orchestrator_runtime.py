"""Composition runtime réelle et unique de ``orchestrator-api``."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.knowledge_access.adapters.postgres_projection_read import (
    PostgresProjectionReadRepository,
)
from app.knowledge_access.application.projection_queries import ProjectionQueryService
from app.knowledge_access.adapters.http import build_projection_query_router
from app.platform.configuration import ApplicationConfiguration
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)
from app.platform.postgres import PsycopgConnectionFactory
from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.adapters.original_http import build_original_pdf_router
from app.source_processing.adapters.pdf_document_inspector import CorpusPdfDocumentInspector
from app.source_processing.adapters.postgres_document_persistence import (
    build_document_persistence,
)
from app.source_processing.adapters.query_http import build_document_query_router
from app.source_processing.application.document_commands import DocumentCommandService
from app.source_processing.application.document_queries import DocumentQueryService
from app.source_processing.application.original_queries import OriginalPdfQueryService


MAX_PDF_BYTES = 50 * 1024 * 1024
PROJECTION_CHUNK_SAMPLE_LIMIT = 3
PROJECTION_TEXT_PREVIEW_CHARACTER_LIMIT = 500
PROJECTION_SOURCE_LOCATOR_LIMIT = 3


@dataclass(slots=True)
class PostgresOrchestratorDependency:
    """Readiness stricte qui bloque le démarrage si PostgreSQL manque."""

    connection_factory: PsycopgConnectionFactory
    _opened: bool = field(init=False, default=False)

    async def open(self) -> None:
        if self._opened:
            raise RuntimeError("dépendance PostgreSQL déjà ouverte")
        with self.connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1", ())
                row = cursor.fetchone()
        if row != (1,):
            raise RuntimeError("POSTGRES_READINESS_INVALID")
        self._opened = True

    async def close(self) -> None:
        if not self._opened:
            raise RuntimeError("dépendance PostgreSQL non ouverte")
        self._opened = False

    def readiness(self) -> DependencyReadiness:
        return DependencyReadiness(
            name="postgres",
            status="ready" if self._opened else "unavailable",
        )


def build_orchestrator_composition_root(
    configuration: ApplicationConfiguration,
) -> OrchestratorCompositionRoot:
    """Construit les ports réels depuis l'unique configuration validée."""

    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")

    connection_factory = PsycopgConnectionFactory(
        connection_url=configuration.services.postgres.url,
        password_path=Path(configuration.security.secrets.postgres_password_path),
    )
    persistence = build_document_persistence(configuration)
    document_commands = DocumentCommandService(
        original_source_store=persistence.original_source_store,
        source_document_repository=persistence.source_document_repository,
        document_inspector=CorpusPdfDocumentInspector(
            original_source_store=persistence.original_source_store
        ),
        processing_run_repository=persistence.processing_run_repository,
        job_queue=persistence.job_queue,
        diagnosis_configuration_hash=configuration.configuration_hash,
        code_version=version("chatbot-trading"),
        model_version=f"pypdf-{version('pypdf')}",
    )
    document_queries = DocumentQueryService(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        document_conversion_repository=persistence.document_conversion_repository,
    )
    original_queries = OriginalPdfQueryService(
        source_document_repository=persistence.source_document_repository,
        original_source_reader=persistence.original_source_store,
    )
    projection_queries = ProjectionQueryService(
        projection_read_repository=PostgresProjectionReadRepository(
            connection_factory=connection_factory
        ),
        chunk_sample_limit=PROJECTION_CHUNK_SAMPLE_LIMIT,
        text_preview_character_limit=PROJECTION_TEXT_PREVIEW_CHARACTER_LIMIT,
        source_locator_limit=PROJECTION_SOURCE_LOCATOR_LIMIT,
    )

    document_router = APIRouter()
    document_router.include_router(
        build_document_command_router(
            document_http_adapter=SourceProcessingHttpAdapter(document_commands),
            max_pdf_bytes=MAX_PDF_BYTES,
        )
    )
    document_router.include_router(build_document_query_router(document_queries=document_queries))
    document_router.include_router(build_original_pdf_router(original_pdf_queries=original_queries))
    document_router.include_router(build_projection_query_router(projection_queries=projection_queries))

    return OrchestratorCompositionRoot(
        configuration=configuration,
        dependencies=(PostgresOrchestratorDependency(connection_factory),),
        document_command_router=document_router,
    )


__all__ = [
    "MAX_PDF_BYTES",
    "PostgresOrchestratorDependency",
    "build_orchestrator_composition_root",
]
