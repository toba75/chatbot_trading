"""Composition runtime réelle et unique de ``orchestrator-api``."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
import asyncio
from typing import Mapping, Protocol, Sequence
from uuid import uuid4

from fastapi import APIRouter

from app.contracts.llm_inference import LlmInferenceGateway
from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.conversation.application.public_chat import ProductConversationHandler
from app.conversation.adapters.in_memory_conversation_repository import (
    InMemoryConversationRepository,
)
from app.conversation.adapters.in_memory_turn_repository import InMemoryTurnRepository
from app.conversation.adapters.live_documentary_answer_provider import (
    LiveDocumentaryConversationAnswerProvider,
)
from app.conversation.adapters.product_conversation_http import ProductConversationHttpAdapter
from app.evaluation.application.llm_real_path import LlmRealPathBenchmarkHandler
from app.knowledge_access.application.public_commands import (
    IndexingUnavailableHandler,
    SearchUnavailableHandler,
)
from app.contracts.document_public_statuses import PublicProjectionStatus
from app.knowledge_access.adapters.postgres_projection_read import (
    PostgresProjectionReadRepository,
)
from app.knowledge_access.adapters.projection_http import KnowledgeProjectionHttpAdapter
from app.knowledge_access.adapters.projection_runtime import ProjectionRuntimeService
from app.knowledge_access.adapters.live_documentary_retrieval import (
    CanonicalProjectionChunkReader,
    DocumentaryProjectionRetriever,
    PostgresSearchableProjectionReader,
    QdrantSparseChunkSelector,
)
from app.knowledge_access.application.projection_queries import ProjectionQueryService
from app.knowledge_access.application.projection_queries import ProjectionCatalogRecord
from app.knowledge_access.adapters.http import (
    build_projection_command_router,
    build_projection_progress_router,
    build_projection_query_router,
)
from app.platform.configuration import ApplicationConfiguration
from app.platform.configured_datastore_identity import (
    build_configured_datastore_preflight,
    configured_datastore_identity,
)
from app.platform.datastore_identity import DatastorePreflightPlan, PostgresIdentityPreflight
from app.platform.orchestrator_composition import (
    DependencyReadiness,
    OrchestratorCompositionRoot,
)
from app.platform.orchestrator_contract_routers import build_public_contract_router
from app.platform.orchestrator_contract_routers import build_product_conversation_router
from app.platform.orchestrator_public_services import PublicContractServices
from app.platform.llm_gateway.orchestrator_health import HttpHealthOrchestratorDependency
from app.platform.llm_gateway.orchestrator_http import UrllibLlmInferenceGateway
from app.platform.postgres import PsycopgConnectionFactory
from app.platform.postgres_migrations import (
    POSTGRES_MIGRATIONS_PATH,
    PostgresMigrationRunner,
)
from app.source_processing.adapters.document_http import (
    SourceProcessingConversionHttpAdapter,
    SourceProcessingHttpAdapter,
)
from app.source_processing.adapters.http import build_document_command_router
from app.source_processing.adapters.original_http import build_original_pdf_router
from app.source_processing.adapters.pdf_document_inspector import (
    build_m13_corpus_pdf_document_inspector,
)
from app.source_processing.adapters.postgres_document_persistence import (
    build_document_persistence,
)
from app.source_processing.adapters.query_http import build_document_query_router
from app.source_processing.application.document_commands import (
    DocumentCommandService,
    DocumentConversionCommandService,
)
from app.source_processing.application.document_queries import (
    DocumentCorpusItem,
    DocumentCorpusPageView,
    DocumentActionProgressView,
    DocumentConversionView,
    DocumentDiagnosticView,
    DocumentQueryService,
)
from app.source_processing.application.original_queries import OriginalPdfQueryService
from app.source_processing.application.resolve_manual_review import (
    ResolveManualReviewHandler,
)
from app.source_processing.application.routing_policy import (
    build_document_routing_configuration,
)
from app.research_answering.application.live_documentary_answer import (
    LiveDocumentaryAnswerService,
)


MAX_PDF_BYTES = 50 * 1024 * 1024
PROJECTION_CHUNK_SAMPLE_LIMIT = 3
PROJECTION_TEXT_PREVIEW_CHARACTER_LIMIT = 500
PROJECTION_SOURCE_LOCATOR_LIMIT = 3


class RuntimeIdentifierFactory:
    """Produit des identifiants métier opaques au bord de composition."""

    def __init__(self, *, prefix: str) -> None:
        if prefix not in {"CONV", "TURN"}:
            raise ValueError("prefixe identifiant runtime invalide")
        self._prefix = prefix

    def next_id(self) -> str:
        return f"{self._prefix}-{uuid4().hex.upper()}"


class SourceProcessingCorpusPagePort(Protocol):
    def list_documents(self, *, limit: int, cursor: str | None) -> DocumentCorpusPageView: ...
    def read_diagnostic(self, document_id: str) -> DocumentDiagnosticView: ...
    def read_document_action_progress(
        self,
        document_id: str,
        action_name: str,
    ) -> DocumentActionProgressView: ...
    def read_conversion(self, document_id: str) -> DocumentConversionView: ...


class KnowledgeProjectionStatusesPort(Protocol):
    def current_projection_catalog_for_document_ids(
        self,
        document_ids: Sequence[str],
    ) -> Mapping[str, ProjectionCatalogRecord]: ...


@dataclass(frozen=True, slots=True)
class OrchestratorDocumentCorpusItem:
    document_id: str
    title: str | None
    authors: tuple[str, ...] | None
    publication_year: int | None
    edition: str | None
    metadata_status: str
    document_status: str
    diagnostic_status: str
    conversion_status: str
    conversion_action_available: bool
    projection_action_available: bool
    canonical_version_id: str | None
    projection_status: str
    manual_review_reason: str | None
    failure_error_code: str | None


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
            getattr(projection_statuses, "current_projection_catalog_for_document_ids", None)
        ):
            raise ValueError("projection_statuses sans catalogue batch")
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
        projections = dict(
            self._projection_statuses.current_projection_catalog_for_document_ids(document_ids)
        )
        if set(projections) - set(document_ids):
            raise ValueError("statuts KA hors page SP")
        return OrchestratorDocumentCorpusPage(
            documents=tuple(
                _enrich_corpus_item(item, projection_record=projections.get(item.document_id))
                for item in page.documents
            ),
            next_cursor=page.next_cursor,
        )

    def read_diagnostic(self, document_id: str) -> DocumentDiagnosticView:
        return self._source_processing_pages.read_diagnostic(document_id)

    def read_document_action_progress(
        self,
        document_id: str,
        action_name: str,
    ) -> DocumentActionProgressView:
        return self._source_processing_pages.read_document_action_progress(
            document_id,
            action_name,
        )

    def read_conversion(self, document_id: str) -> DocumentConversionView:
        return self._source_processing_pages.read_conversion(document_id)


def _enrich_corpus_item(
    item: DocumentCorpusItem,
    *,
    projection_record: ProjectionCatalogRecord | None,
) -> OrchestratorDocumentCorpusItem:
    if not isinstance(item, DocumentCorpusItem):
        raise TypeError("document corpus SP invalide")
    status = (
        "PROJECTION_NOT_REQUESTED"
        if projection_record is None
        else PublicProjectionStatus.from_value(projection_record.projection_status).value
    )
    if projection_record is None or projection_record.metadata_status == "PENDING":
        title = item.title
        authors = item.authors
        publication_year = item.publication_year
        edition = item.edition
        metadata_status = item.metadata_status
    else:
        title = projection_record.title
        authors = projection_record.authors
        publication_year = projection_record.publication_year
        edition = projection_record.edition
        metadata_status = projection_record.metadata_status
    return OrchestratorDocumentCorpusItem(
        document_id=item.document_id,
        title=title,
        authors=authors,
        publication_year=publication_year,
        edition=edition,
        metadata_status=metadata_status,
        document_status=item.document_status,
        diagnostic_status=item.diagnostic_status,
        conversion_status=item.conversion_status,
        conversion_action_available=item.conversion_action_available,
        projection_action_available=(
            item.conversion_status == "CANONICAL_ACCEPTED"
            and item.canonical_version_id is not None
            and status == "PROJECTION_NOT_REQUESTED"
        ),
        canonical_version_id=item.canonical_version_id,
        projection_status=status,
        manual_review_reason=item.manual_review_reason,
        failure_error_code=item.failure_error_code,
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
            error_code=None if status == "ready" else "POSTGRES_SCHEMA_VERSION_REQUIRED",
        )


@dataclass(slots=True)
class DatastoreIdentityOrchestratorDependency:
    """Bloque tous les adaptateurs tant que les stockages ne portent pas le profil."""

    preflight: DatastorePreflightPlan
    _opened: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        if not isinstance(self.preflight, DatastorePreflightPlan):
            raise ValueError("préflight d'identité orchestrateur invalide")

    async def open(self) -> None:
        if self._opened:
            raise RuntimeError("préflight d'identité déjà ouvert")
        await asyncio.to_thread(self.preflight.run, initialize_if_empty=True)
        self._opened = True

    async def close(self) -> None:
        if not self._opened:
            raise RuntimeError("préflight d'identité non ouvert")
        self._opened = False

    def readiness(self) -> DependencyReadiness:
        return DependencyReadiness(
            name="datastore-identity",
            status="ready" if self._opened else "unavailable",
            error_code=None if self._opened else "DATASTORE_ENVIRONMENT_MISMATCH",
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
        identity_preflight=PostgresIdentityPreflight(
            expected_identity=configured_datastore_identity(configuration),
        ),
        initialize_identity_if_empty=False,
        adopt_legacy_if_unidentified=False,
    )
    persistence = build_document_persistence(
        configuration,
        connection_factory=connection_factory,
    )
    document_commands = DocumentCommandService(
        original_source_store=persistence.original_source_store,
        source_document_repository=persistence.source_document_repository,
        document_inspector=build_m13_corpus_pdf_document_inspector(
            original_source_store=persistence.original_source_store,
        ),
        processing_run_repository=persistence.processing_run_repository,
        environment=configuration.application.environment,
        deployment_id=configuration.application.deployment_id,
        diagnosis_configuration_hash=configuration.configuration_hash,
        code_version=version("chatbot-trading"),
        model_version=f"pypdf-{version('pypdf')}",
    )
    document_conversion_commands = DocumentConversionCommandService(
        source_document_repository=persistence.source_document_repository,
        processing_run_repository=persistence.processing_run_repository,
        document_conversion_repository=persistence.document_conversion_repository,
        environment=configuration.application.environment,
        deployment_id=configuration.application.deployment_id,
        conversion_configuration_hash=configuration.configuration_hash,
        code_version=version("chatbot-trading"),
        model_version=f"docling-{version('docling')}",
    )
    document_queries = DocumentQueryService(
        document_snapshot_repository=persistence.source_document_repository,
        document_corpus_status_repository=persistence.source_document_repository,
        environment_identity=JobEnvironmentIdentity(
            environment=configuration.application.environment,
            deployment_id=configuration.application.deployment_id,
            configuration_hash=configuration.configuration_hash,
        ),
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
    inference_gateway = UrllibLlmInferenceGateway(
        endpoint_url=f"{configuration.services.llm_gateway.url.rstrip('/')}/v1/infer",
        timeout_seconds=configuration.services.llm_gateway.timeout_seconds,
    )
    projection_runtime = ProjectionRuntimeService(
        connection_factory=connection_factory,
        canonical_sources_root=Path(configuration.paths.canonical_sources_root),
        environment=configuration.application.environment,
        deployment_id=configuration.application.deployment_id,
        configuration_hash=configuration.configuration_hash,
        qdrant_url=configuration.services.qdrant.url,
        qdrant_collection_name=configuration.services.qdrant.collections.knowledge_access,
        qdrant_timeout_seconds=configuration.runtime.timeouts.request_seconds,
        max_parallel_workers=configuration.services.workers.concurrency,
        inference_gateway=inference_gateway,
    )
    documentary_retriever = DocumentaryProjectionRetriever(
        projection_reader=PostgresSearchableProjectionReader(
            projection_read_repository=projection_read_repository,
        ),
        canonical_reader=CanonicalProjectionChunkReader(
            projection_runtime=projection_runtime,
        ),
        chunk_selector=QdrantSparseChunkSelector(
            qdrant_url=configuration.services.qdrant.url,
            collection_name=configuration.services.qdrant.collections.knowledge_access,
            timeout_seconds=configuration.runtime.timeouts.request_seconds,
        ),
        result_limit=4,
    )
    product_conversation_adapter = ProductConversationHttpAdapter(
        conversation_repository=InMemoryConversationRepository.empty(),
        turn_repository=InMemoryTurnRepository.empty(),
        conversation_id_factory=RuntimeIdentifierFactory(prefix="CONV"),
        turn_id_factory=RuntimeIdentifierFactory(prefix="TURN"),
        answer_provider=LiveDocumentaryConversationAnswerProvider(
            answer_service=LiveDocumentaryAnswerService(
                evidence_retriever=documentary_retriever,
                inference_gateway=inference_gateway,
                configuration_hash=configuration.configuration_hash,
            )
        ),
        retention_policy_version="conversation-retention-m013-v1",
    )

    document_router = APIRouter()
    document_router.include_router(build_product_conversation_router(product_conversation_adapter))
    document_router.include_router(
        build_public_contract_router(
            compose_public_contract_services(
                configuration,
                inference_gateway=inference_gateway,
            ),
            include_indexing_router=False,
        )
    )
    document_router.include_router(
        build_document_command_router(
            document_http_adapter=SourceProcessingHttpAdapter(document_commands),
            document_conversion_http_adapter=SourceProcessingConversionHttpAdapter(
                document_conversion_commands
            ),
            manual_review_handler=ResolveManualReviewHandler(
                processing_run_repository=persistence.processing_run_repository,
                routing_configuration=build_document_routing_configuration(),
            ),
            max_pdf_bytes=MAX_PDF_BYTES,
        )
    )
    document_router.include_router(build_document_query_router(document_queries=document_catalog))
    document_router.include_router(
        build_projection_command_router(
            projection_command_adapter=KnowledgeProjectionHttpAdapter(
                projection_commands=projection_runtime,
            )
        )
    )
    document_router.include_router(
        build_projection_progress_router(projection_progress=projection_runtime)
    )
    document_router.include_router(build_original_pdf_router(original_pdf_queries=original_queries))
    document_router.include_router(build_projection_query_router(projection_queries=projection_queries))

    return OrchestratorCompositionRoot(
        configuration=configuration,
        dependencies=(
            DatastoreIdentityOrchestratorDependency(
                preflight=build_configured_datastore_preflight(
                    configuration,
                    include_postgres=True,
                    include_qdrant=True,
                    file_root_names=(
                        "data_root",
                        "corpus_root",
                        "canonical_sources_root",
                    ),
                )
            ),
            PostgresOrchestratorDependency(
                connection_factory=connection_factory,
                migration_runner=migration_runner,
            ),
            HttpHealthOrchestratorDependency(
                name="llm-gateway",
                health_url=f"{configuration.services.llm_gateway.url}/health",
                timeout_seconds=configuration.services.llm_gateway.timeout_seconds,
                not_ready_error_code="LLM_GATEWAY_NOT_READY",
            ),
            HttpHealthOrchestratorDependency(
                name="qdrant",
                health_url=f"{configuration.services.qdrant.url.rstrip('/')}/healthz",
                timeout_seconds=configuration.runtime.timeouts.request_seconds,
                not_ready_error_code="QDRANT_NOT_READY",
            ),
        ),
        document_command_router=document_router,
    )


def compose_public_contract_services(
    configuration: ApplicationConfiguration,
    *,
    inference_gateway: LlmInferenceGateway,
) -> PublicContractServices:
    """Compose les handlers propriétaires sans déplacer leur logique dans platform."""

    if not isinstance(configuration, ApplicationConfiguration):
        raise TypeError("configuration applicative validée obligatoire")
    if not callable(getattr(inference_gateway, "infer", None)):
        raise TypeError("port d'inférence obligatoire")
    return PublicContractServices(
        conversation=ProductConversationHandler(
            served_model=configuration.models.llm.served_model_name,
            configuration_hash=configuration.configuration_hash,
            gateway_endpoint=f"{configuration.services.llm_gateway.url.rstrip('/')}/v1/infer",
            inference_gateway=inference_gateway,
        ),
        evaluation=LlmRealPathBenchmarkHandler(
            served_model=configuration.models.llm.served_model_name,
            configuration_hash=configuration.configuration_hash,
            inference_gateway=inference_gateway,
        ),
        search=SearchUnavailableHandler(),
        indexing=IndexingUnavailableHandler(),
    )


__all__ = [
    "DatastoreIdentityOrchestratorDependency",
    "MAX_PDF_BYTES",
    "POSTGRES_MIGRATIONS_PATH",
    "PostgresOrchestratorDependency",
    "HttpHealthOrchestratorDependency",
    "OrchestratorDocumentCatalogService",
    "OrchestratorDocumentCorpusItem",
    "OrchestratorDocumentCorpusPage",
    "RuntimeIdentifierFactory",
    "build_orchestrator_composition_root",
    "compose_public_contract_services",
]
