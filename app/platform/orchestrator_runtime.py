"""Composition runtime réelle et unique de ``orchestrator-api``."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
import asyncio
from typing import Any, Mapping, Protocol, Sequence

from fastapi import APIRouter

from app.contracts.document_public_statuses import PublicProjectionStatus
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
from app.platform.orchestrator_contract_routers import build_public_contract_router
from app.platform.orchestrator_public_services import build_public_contract_services
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import (
    POSTGRES_MIGRATIONS_PATH,
    PostgresMigrationRunner,
)
from app.source_processing.adapters.document_http import SourceProcessingHttpAdapter
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.adapters.original_http import build_original_pdf_router
from app.source_processing.adapters.pdf_document_inspector import CorpusPdfDocumentInspector
from app.source_processing.adapters.postgres_document_persistence import (
    build_document_persistence,
)
from app.source_processing.adapters.query_http import build_document_query_router
from app.source_processing.application.document_commands import DocumentCommandService
from app.source_processing.application.document_queries import (
    DocumentCorpusItem,
    DocumentCorpusPageView,
    DocumentConversionView,
    DocumentDiagnosticView,
    DocumentQueryService,
)
from app.source_processing.application.original_queries import OriginalPdfQueryService


MAX_PDF_BYTES = 50 * 1024 * 1024
PROJECTION_CHUNK_SAMPLE_LIMIT = 3
PROJECTION_TEXT_PREVIEW_CHARACTER_LIMIT = 500
PROJECTION_SOURCE_LOCATOR_LIMIT = 3


class SourceProcessingCorpusPagePort(Protocol):
    def list_documents(self, *, limit: int, cursor: str | None) -> DocumentCorpusPageView: ...
    def read_diagnostic(self, document_id: str) -> DocumentDiagnosticView: ...
    def read_conversion(self, document_id: str) -> DocumentConversionView: ...


class KnowledgeProjectionStatusesPort(Protocol):
    def current_projection_statuses_for_document_ids(
        self,
        document_ids: Sequence[str],
    ) -> Mapping[str, str]: ...


@dataclass(frozen=True, slots=True)
class OrchestratorDocumentCorpusItem:
    document_id: str
    title: str
    document_status: str
    diagnostic_status: str
    conversion_status: str
    canonical_version_id: str | None
    projection_status: str


@dataclass(frozen=True, slots=True)
class OrchestratorDocumentCorpusPage:
    documents: tuple[OrchestratorDocumentCorpusItem, ...]
    next_cursor: str | None


class OrchestratorDocumentCatalogService:
    """Agrège deux read-models bornés dans l'unique composition intercontextes."""

    def __init__(
        self,
        *,
        source_processing_pages: SourceProcessingCorpusPagePort,
        projection_statuses: KnowledgeProjectionStatusesPort,
    ) -> None:
        if not callable(getattr(source_processing_pages, "list_documents", None)):
            raise ValueError("source_processing_pages sans pagination")
        if not callable(
            getattr(projection_statuses, "current_projection_statuses_for_document_ids", None)
        ):
            raise ValueError("projection_statuses sans lecture batch")
        self._source_processing_pages = source_processing_pages
        self._projection_statuses = projection_statuses

    def list_documents(
        self,
        *,
        limit: int,
        cursor: str | None,
    ) -> OrchestratorDocumentCorpusPage:
        page = self._source_processing_pages.list_documents(limit=limit, cursor=cursor)
        if not isinstance(page, DocumentCorpusPageView):
            raise TypeError("page SP invalide")
        document_ids = tuple(item.document_id for item in page.documents)
        statuses = dict(
            self._projection_statuses.current_projection_statuses_for_document_ids(document_ids)
        )
        if set(statuses) - set(document_ids):
            raise ValueError("statuts KA hors page SP")
        return OrchestratorDocumentCorpusPage(
            documents=tuple(
                _enrich_corpus_item(item, projection_status=statuses.get(item.document_id))
                for item in page.documents
            ),
            next_cursor=page.next_cursor,
        )

    def read_diagnostic(self, document_id: str) -> DocumentDiagnosticView:
        return self._source_processing_pages.read_diagnostic(document_id)

    def read_conversion(self, document_id: str) -> DocumentConversionView:
        return self._source_processing_pages.read_conversion(document_id)


def _enrich_corpus_item(
    item: DocumentCorpusItem,
    *,
    projection_status: Any,
) -> OrchestratorDocumentCorpusItem:
    if not isinstance(item, DocumentCorpusItem):
        raise TypeError("document corpus SP invalide")
    status = (
        "PROJECTION_NOT_REQUESTED"
        if projection_status is None
        else PublicProjectionStatus.from_value(projection_status).value
    )
    return OrchestratorDocumentCorpusItem(
        document_id=item.document_id,
        title=item.title,
        document_status=item.document_status,
        diagnostic_status=item.diagnostic_status,
        conversion_status=item.conversion_status,
        canonical_version_id=item.canonical_version_id,
        projection_status=status,
    )


@dataclass(slots=True)
class PostgresOrchestratorDependency:
    """Readiness stricte qui bloque le démarrage si PostgreSQL manque."""

    connection_factory: PsycopgConnectionFactory
    migration_runner: PostgresMigrationRunner
    _opened: bool = field(init=False, default=False)

    async def open(self) -> None:
        if self._opened:
            raise RuntimeError("dépendance PostgreSQL déjà ouverte")
        await asyncio.to_thread(self.migration_runner.run)
        if not await asyncio.to_thread(self.migration_runner.is_required_schema_ready):
            raise RuntimeError("POSTGRES_SCHEMA_VERSION_REQUIRED")
        self._opened = True

    async def close(self) -> None:
        if not self._opened:
            raise RuntimeError("dépendance PostgreSQL non ouverte")
        self._opened = False

    def readiness(self) -> DependencyReadiness:
        if not self._opened:
            status = "unavailable"
        else:
            try:
                status = (
                    "ready"
                    if self.migration_runner.is_required_schema_ready()
                    else "unavailable"
                )
            except Exception:
                status = "unavailable"
        return DependencyReadiness(
            name="postgres",
            status=status,
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
        connect_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
    )
    migration_runner = PostgresMigrationRunner(
        connection_factory=connection_factory,
        migrations_path=POSTGRES_MIGRATIONS_PATH,
        operation_timeout_seconds=configuration.runtime.timeouts.startup_seconds,
    )
    persistence = build_document_persistence(
        configuration,
        connection_factory=connection_factory,
    )
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
        document_snapshot_repository=persistence.source_document_repository,
    )
    original_queries = OriginalPdfQueryService(
        source_document_repository=persistence.source_document_repository,
        original_source_reader=persistence.original_source_store,
    )
    projection_read_repository = PostgresProjectionReadRepository(
        connection_factory=connection_factory
    )
    projection_queries = ProjectionQueryService(
        projection_read_repository=projection_read_repository,
        chunk_sample_limit=PROJECTION_CHUNK_SAMPLE_LIMIT,
        text_preview_character_limit=PROJECTION_TEXT_PREVIEW_CHARACTER_LIMIT,
        source_locator_limit=PROJECTION_SOURCE_LOCATOR_LIMIT,
    )
    document_catalog = OrchestratorDocumentCatalogService(
        source_processing_pages=document_queries,
        projection_statuses=projection_read_repository,
    )

    document_router = APIRouter()
    document_router.include_router(
        build_public_contract_router(build_public_contract_services(configuration))
    )
    document_router.include_router(
        build_document_command_router(
            document_http_adapter=SourceProcessingHttpAdapter(document_commands),
            max_pdf_bytes=MAX_PDF_BYTES,
        )
    )
    document_router.include_router(build_document_query_router(document_queries=document_catalog))
    document_router.include_router(build_original_pdf_router(original_pdf_queries=original_queries))
    document_router.include_router(build_projection_query_router(projection_queries=projection_queries))

    return OrchestratorCompositionRoot(
        configuration=configuration,
        dependencies=(
            PostgresOrchestratorDependency(
                connection_factory=connection_factory,
                migration_runner=migration_runner,
            ),
        ),
        document_command_router=document_router,
    )


__all__ = [
    "MAX_PDF_BYTES",
    "POSTGRES_MIGRATIONS_PATH",
    "PostgresOrchestratorDependency",
    "OrchestratorDocumentCatalogService",
    "OrchestratorDocumentCorpusItem",
    "OrchestratorDocumentCorpusPage",
    "build_orchestrator_composition_root",
]
