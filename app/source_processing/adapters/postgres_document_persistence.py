"""Adaptateurs durables SP: PostgreSQL pour l'état et corpus pour les PDF."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.platform.job_runtime import JOB_RUNTIME_CATALOG, JobRequest, JobSubmissionDecision
from app.platform.job_runtime.postgres import PostgresJobQueue
from app.platform.configuration import ApplicationConfiguration
from app.platform.postgres import PostgresConnectionFactory, PsycopgConnectionFactory
from app.source_processing.application.document_commands import (
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.original_queries import (
    OriginalHashMismatchError,
    VerifiedOriginalBinary,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    DocumentProcessingStarted,
    ExistingOcrSignal,
    LayoutComplexitySignal,
    NativeTextSignal,
    PageCorruptionSignal,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageImageSignal,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PagePreprocessingAction,
    PageRoute,
    PageRouteName,
    ProcessingRunId,
    RouteDecisionMode,
    RoutePlan,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceDocumentStatus,
    SourceFingerprint,
)


_ARTIFACT_PREFIX = "artifact:source_processing.original_sources/"


class CorpusOriginalSourceStore:
    """Conserve chaque PDF original de manière immuable sous ``corpus_root``."""

    def __init__(self, *, corpus_root: Path) -> None:
        if not isinstance(corpus_root, Path):
            raise ValueError("corpus_root invalide")
        self._corpus_root = corpus_root

    def put_original_if_absent(
        self,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        original_content: bytes,
    ) -> str:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        if not isinstance(fingerprint, SourceFingerprint):
            raise ValueError("fingerprint invalide")
        if not isinstance(original_content, bytes) or len(original_content) == 0:
            raise ValueError("original_content invalide")
        if hashlib.sha256(original_content).hexdigest() != fingerprint.value:
            raise OriginalHashMismatchError()

        relative_path = Path(document_id.value) / f"{fingerprint.value}.pdf"
        target = self._corpus_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            _verify_file_hash(target, fingerprint.value)
            return f"{_ARTIFACT_PREFIX}{relative_path.as_posix()}"

        temporary = target.parent / f".{target.name}.{uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as stream:
                stream.write(original_content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
            _verify_file_hash(target, fingerprint.value)
        finally:
            if temporary.exists():
                temporary.unlink()
        return f"{_ARTIFACT_PREFIX}{relative_path.as_posix()}"

    def storage_ref(self, value: str) -> OriginalStorageRef:
        return OriginalStorageRef.from_value(value)

    def resolve_internal_path(self, storage_ref: OriginalStorageRef) -> Path:
        if not isinstance(storage_ref, OriginalStorageRef):
            raise ValueError("original_storage_ref invalide")
        relative = storage_ref.value.removeprefix(_ARTIFACT_PREFIX)
        resolved_root = self._corpus_root.resolve()
        resolved = (resolved_root / Path(relative)).resolve()
        if resolved_root not in resolved.parents:
            raise ValueError("ORIGINAL_STORAGE_REF_OUTSIDE_CORPUS")
        return resolved

    def open_verified_original(
        self,
        source_document: SourceDocument,
        *,
        chunk_size: int,
    ) -> VerifiedOriginalBinary:
        if not isinstance(source_document, SourceDocument):
            raise ValueError("source_document invalide")
        if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
            raise ValueError("chunk_size invalide")
        path = self.resolve_internal_path(source_document.original_storage_ref)
        try:
            stream = path.open("rb")
        except OSError as exc:
            raise RuntimeError("ORIGINAL_UNREADABLE") from exc
        try:
            digest = hashlib.sha256()
            content_length = 0
            while chunk := stream.read(chunk_size):
                digest.update(chunk)
                content_length += len(chunk)
            if content_length == 0:
                raise RuntimeError("ORIGINAL_UNREADABLE")
            if digest.hexdigest() != source_document.fingerprint.value:
                raise OriginalHashMismatchError()
            stream.seek(0)
        except BaseException:
            stream.close()
            raise

        def content_chunks():
            try:
                while chunk := stream.read(chunk_size):
                    yield chunk
            finally:
                stream.close()

        chunks = content_chunks()
        return VerifiedOriginalBinary(
            content_length=content_length,
            content_chunks=chunks,
            close=chunks.close,
        )

    def read_original(self, source_document: SourceDocument) -> bytes:
        """Compatibilité interne : matérialise explicitement le flux vérifié."""

        binary = self.open_verified_original(source_document, chunk_size=64 * 1024)
        try:
            return b"".join(binary.content_chunks)
        finally:
            binary.close()


class PostgresDocumentPersistence:
    """Façade de persistance SP sur le schéma PostgreSQL propriétaire."""

    def __init__(self, *, connection_factory: PostgresConnectionFactory) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        self._connection_factory = connection_factory

    def find_by_fingerprint(self, fingerprint: SourceFingerprint) -> SourceDocument | None:
        if not isinstance(fingerprint, SourceFingerprint):
            raise ValueError("fingerprint invalide")
        return self._find_source("fingerprint = %s", (fingerprint.value,))

    def find_by_work_key(
        self,
        work_key: tuple[str, tuple[str, ...]],
    ) -> SourceDocument | None:
        if (
            not isinstance(work_key, tuple)
            or len(work_key) != 2
            or not isinstance(work_key[0], str)
            or not isinstance(work_key[1], tuple)
        ):
            raise ValueError("work_key invalide")
        return self._find_source(
            "work_title = %s AND work_authors = %s",
            (work_key[0], list(work_key[1])),
        )

    def find_by_document_id(self, document_id: DocumentId) -> SourceDocument | None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        return self._find_source("document_id = %s", (document_id.value,))

    def list_documents(self) -> tuple[SourceDocument, ...]:
        """Retourne les sources persistées dans l'ordre de leur identité publique."""

        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT document_id, fingerprint, original_storage_ref, title,
                           authors, publication_year, edition, status,
                           quarantine_reason
                      FROM source_processing.source_documents
                     ORDER BY document_id
                    """,
                    (),
                )
                rows = cursor.fetchall()
        return tuple(_source_from_row(row) for row in rows)

    def save_if_absent(self, source_document: SourceDocument) -> SourceDocument | None:
        if not isinstance(source_document, SourceDocument):
            raise ValueError("source_document invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO source_processing.source_documents (
                            document_id, fingerprint, original_storage_ref, title,
                            authors, publication_year, edition, work_title,
                            work_authors, status, quarantine_reason
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        RETURNING document_id
                        """,
                        _source_parameters(source_document),
                    )
                    inserted = cursor.fetchone()
        if inserted is not None:
            return None
        existing = self.find_by_fingerprint(source_document.fingerprint)
        if existing is not None:
            return existing
        existing = self.find_by_document_id(source_document.document_id)
        if existing is None:
            raise RuntimeError("SOURCE_PERSISTENCE_FAILED")
        return existing

    def save(self, processing_run: DocumentProcessingRun) -> None:
        if not isinstance(processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                self._save_processing_run(connection, processing_run)

    def find_processing_run_by_document_id(
        self,
        document_id: DocumentId,
    ) -> DocumentProcessingRun | None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        with self._connection_factory.connect() as connection:
            return self._load_processing_run(connection, document_id)

    def submit_processing_run(
        self,
        processing_run: DocumentProcessingRun,
        job_queue: Any,
        job_request: JobRequest,
    ) -> JobSubmissionDecision:
        if not isinstance(processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        submit_in_transaction = getattr(job_queue, "submit_in_transaction", None)
        if not callable(submit_in_transaction):
            raise ValueError("PERSISTENT_JOB_QUEUE_REQUIRED")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                submission = submit_in_transaction(
                    connection,
                    job_request,
                    recalculate=False,
                )
                if submission.created:
                    self._save_processing_run(connection, processing_run, insert_only=True)
                return submission

    def find_conversion_by_document_id(
        self,
        document_id: DocumentId,
    ) -> DocumentConversionState | None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT document_id, conversion_status, canonical_version_id,
                           rejection_error_code
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (document_id.value,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return DocumentConversionState(
            document_id=DocumentId.from_value(row[0]),
            conversion_status=DocumentConversionStatus.from_value(row[1]),
            canonical_version_id=row[2],
            rejection_error_code=row[3],
        )

    def submit_conversion_request(
        self,
        conversion_state: DocumentConversionState,
        job_queue: Any,
        job_request: JobRequest,
    ) -> JobSubmissionDecision:
        if not isinstance(conversion_state, DocumentConversionState):
            raise ValueError("conversion_state invalide")
        submit_in_transaction = getattr(job_queue, "submit_in_transaction", None)
        if not callable(submit_in_transaction):
            raise ValueError("PERSISTENT_JOB_QUEUE_REQUIRED")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                submission = submit_in_transaction(
                    connection,
                    job_request,
                    recalculate=False,
                )
                if submission.created:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO source_processing.document_conversion_requests (
                                document_id, conversion_status, canonical_version_id,
                                rejection_error_code, job_id
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (document_id) DO NOTHING
                            RETURNING document_id
                            """,
                            (
                                conversion_state.document_id.value,
                                conversion_state.conversion_status.value,
                                conversion_state.canonical_version_id,
                                conversion_state.rejection_error_code,
                                submission.job.job_id,
                            ),
                        )
                        if cursor.fetchone() is None:
                            raise RuntimeError("CONVERSION_PERSISTENCE_CONFLICT")
                return submission

    def _find_source(self, predicate: str, parameters: tuple[Any, ...]) -> SourceDocument | None:
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT document_id, fingerprint, original_storage_ref, title,
                           authors, publication_year, edition, status,
                           quarantine_reason
                      FROM source_processing.source_documents
                     WHERE {predicate}
                     ORDER BY document_id
                     LIMIT 1
                    """,
                    parameters,
                )
                row = cursor.fetchone()
        return None if row is None else _source_from_row(row)

    def _save_processing_run(
        self,
        connection: Any,
        processing_run: DocumentProcessingRun,
        *,
        insert_only: bool = False,
    ) -> None:
        conflict_clause = "DO NOTHING" if insert_only else """DO UPDATE SET
            source_page_count = EXCLUDED.source_page_count,
            status = EXCLUDED.status,
            manual_review_reason = EXCLUDED.manual_review_reason,
            blocking_policy_version = EXCLUDED.blocking_policy_version"""
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO source_processing.document_processing_runs (
                    processing_run_id, document_id, source_page_count, status,
                    manual_review_reason, blocking_policy_version
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (processing_run_id) {conflict_clause}
                RETURNING processing_run_id
                """,
                (
                    processing_run.processing_run_id.value,
                    processing_run.document_id.value,
                    processing_run.page_manifest.source_page_count,
                    processing_run.status.value,
                    processing_run.manual_review_reason,
                    None
                    if processing_run.blocking_policy_version is None
                    else processing_run.blocking_policy_version.value,
                ),
            )
            if cursor.fetchone() is None:
                raise RuntimeError("PROCESSING_RUN_PERSISTENCE_CONFLICT")
            for table in ("page_routes", "route_plans", "page_decisions", "page_manifest_entries"):
                cursor.execute(
                    f"DELETE FROM source_processing.{table} WHERE processing_run_id = %s",
                    (processing_run.processing_run_id.value,),
                )
            for entry in processing_run.page_manifest.entries:
                cursor.execute(
                    """
                    INSERT INTO source_processing.page_manifest_entries
                        (processing_run_id, page_number, state)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        processing_run.processing_run_id.value,
                        entry.page_number.value,
                        entry.state.value,
                    ),
                )
            for decision in processing_run.page_decisions:
                signals = decision.signals
                cursor.execute(
                    """
                    INSERT INTO source_processing.page_decisions (
                        processing_run_id, page_number, page_state,
                        native_text_state, image_state, existing_ocr_state,
                        layout_complexity, corruption_state, mixed_content_detected,
                        has_table, has_formula, diagnostic_version, justification
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        processing_run.processing_run_id.value,
                        decision.page_number.value,
                        decision.page_state.value,
                        signals.native_text_state.value,
                        signals.image_state.value,
                        signals.existing_ocr_state.value,
                        signals.layout_complexity.value,
                        signals.corruption_state.value,
                        signals.mixed_content_detected,
                        signals.has_table,
                        signals.has_formula,
                        decision.diagnostic_version.value,
                        decision.justification,
                    ),
                )
            if processing_run.route_plan is not None:
                route_plan = processing_run.route_plan
                cursor.execute(
                    """
                    INSERT INTO source_processing.route_plans (
                        processing_run_id, routing_policy_version,
                        dominant_route_name, confidence_score
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        processing_run.processing_run_id.value,
                        route_plan.routing_policy_version.value,
                        route_plan.dominant_route_name.value,
                        route_plan.confidence_score,
                    ),
                )
                exception_pages = {route.page_number.value for route in route_plan.page_exceptions}
                for route in route_plan.page_routes:
                    cursor.execute(
                        """
                        INSERT INTO source_processing.page_routes (
                            processing_run_id, page_number, route_name,
                            decision_mode, confidence_score, preprocessing_action,
                            routing_policy_version, justification, is_exception
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            processing_run.processing_run_id.value,
                            route.page_number.value,
                            route.route_name.value,
                            route.decision_mode.value,
                            route.confidence_score,
                            route.preprocessing_action.value,
                            route.routing_policy_version.value,
                            route.justification,
                            route.page_number.value in exception_pages,
                        ),
                    )

    def _load_processing_run(
        self,
        connection: Any,
        document_id: DocumentId,
    ) -> DocumentProcessingRun | None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT processing_run_id, document_id, source_page_count, status,
                       manual_review_reason, blocking_policy_version
                  FROM source_processing.document_processing_runs
                 WHERE document_id = %s
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                (document_id.value,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            processing_run_id = row[0]
            cursor.execute(
                """
                SELECT page_number, state
                  FROM source_processing.page_manifest_entries
                 WHERE processing_run_id = %s
                 ORDER BY page_number
                """,
                (processing_run_id,),
            )
            manifest_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT page_number, page_state, native_text_state, image_state,
                       existing_ocr_state, layout_complexity, corruption_state,
                       mixed_content_detected, has_table, has_formula,
                       diagnostic_version, justification
                  FROM source_processing.page_decisions
                 WHERE processing_run_id = %s
                 ORDER BY page_number
                """,
                (processing_run_id,),
            )
            decision_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT routing_policy_version, dominant_route_name, confidence_score
                  FROM source_processing.route_plans
                 WHERE processing_run_id = %s
                """,
                (processing_run_id,),
            )
            plan_row = cursor.fetchone()
            cursor.execute(
                """
                SELECT page_number, route_name, decision_mode, confidence_score,
                       preprocessing_action, routing_policy_version, justification,
                       is_exception
                  FROM source_processing.page_routes
                 WHERE processing_run_id = %s
                 ORDER BY page_number
                """,
                (processing_run_id,),
            )
            route_rows = cursor.fetchall()

        run_id = ProcessingRunId.from_value(row[0])
        parsed_document_id = DocumentId.from_value(row[1])
        manifest = PageManifest.from_entries(
            source_page_count=row[2],
            entries=tuple(
                PageManifestEntry(
                    page_number=PageNumber.from_value(item[0]),
                    state=PageManifestEntryState(item[1]),
                )
                for item in manifest_rows
            ),
        )
        decisions = tuple(_decision_from_row(item) for item in decision_rows)
        routes = tuple(_route_from_row(item) for item in route_rows)
        route_plan = None
        if plan_row is not None:
            route_plan = RoutePlan(
                routing_policy_version=RoutingPolicyVersion.from_value(plan_row[0]),
                page_routes=routes,
                dominant_route_name=PageRouteName(plan_row[1]),
                page_exceptions=tuple(route for route, item in zip(routes, route_rows) if item[7]),
                confidence_score=plan_row[2],
            )
        started = DocumentProcessingStarted(
            processing_run_id=run_id,
            document_id=parsed_document_id,
            source_page_count=row[2],
        )
        return DocumentProcessingRun(
            processing_run_id=run_id,
            document_id=parsed_document_id,
            page_manifest=manifest,
            page_decisions=decisions,
            route_plan=route_plan,
            manual_review_reason=row[4],
            blocking_policy_version=None
            if row[5] is None
            else RoutingPolicyVersion.from_value(row[5]),
            status=DocumentProcessingRunStatus(row[3]),
            events=(started,),
        )


class PostgresProcessingRunRepository:
    """Vue du port ``ProcessingRunRepository`` sur la façade durable."""

    def __init__(self, persistence: PostgresDocumentPersistence) -> None:
        if not isinstance(persistence, PostgresDocumentPersistence):
            raise ValueError("persistence invalide")
        self._persistence = persistence

    def save(self, processing_run: DocumentProcessingRun) -> None:
        self._persistence.save(processing_run)

    def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None:
        return self._persistence.find_processing_run_by_document_id(document_id)

    def submit_processing_run(
        self,
        processing_run: DocumentProcessingRun,
        job_queue: Any,
        job_request: JobRequest,
    ) -> JobSubmissionDecision:
        return self._persistence.submit_processing_run(processing_run, job_queue, job_request)


class PostgresDocumentConversionRepository:
    """Vue du port conversion M-004 sur la façade durable SP."""

    def __init__(self, persistence: PostgresDocumentPersistence) -> None:
        if not isinstance(persistence, PostgresDocumentPersistence):
            raise ValueError("persistence invalide")
        self._persistence = persistence

    def find_conversion_by_document_id(self, document_id: DocumentId) -> DocumentConversionState | None:
        return self._persistence.find_conversion_by_document_id(document_id)

    def submit_conversion_request(
        self,
        conversion_state: DocumentConversionState,
        job_queue: Any,
        job_request: JobRequest,
    ) -> JobSubmissionDecision:
        return self._persistence.submit_conversion_request(conversion_state, job_queue, job_request)


@dataclass(frozen=True)
class DocumentPersistenceAdapters:
    """Adaptateurs durables injectables dans l'API et ``worker-documents``."""

    original_source_store: CorpusOriginalSourceStore
    source_document_repository: PostgresDocumentPersistence
    processing_run_repository: PostgresProcessingRunRepository
    document_conversion_repository: PostgresDocumentConversionRepository
    job_queue: PostgresJobQueue


def build_document_persistence(
    application_configuration: ApplicationConfiguration,
) -> DocumentPersistenceAdapters:
    """Construit le stockage partagé uniquement depuis M13-config."""

    if not isinstance(application_configuration, ApplicationConfiguration):
        raise ValueError("application_configuration invalide")
    connection_factory = PsycopgConnectionFactory(
        connection_url=application_configuration.services.postgres.url,
        password_path=Path(
            application_configuration.security.secrets.postgres_password_path
        ),
        connect_timeout_seconds=application_configuration.runtime.timeouts.startup_seconds,
    )
    persistence = PostgresDocumentPersistence(connection_factory=connection_factory)
    return DocumentPersistenceAdapters(
        original_source_store=CorpusOriginalSourceStore(
            corpus_root=Path(application_configuration.paths.corpus_root)
        ),
        source_document_repository=persistence,
        processing_run_repository=PostgresProcessingRunRepository(persistence),
        document_conversion_repository=PostgresDocumentConversionRepository(persistence),
        job_queue=PostgresJobQueue(
            connection_factory=connection_factory,
            catalog=JOB_RUNTIME_CATALOG,
        ),
    )


def _verify_file_hash(path: Path, expected_hash: str) -> None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        actual = digest.hexdigest()
    except OSError as exc:
        raise RuntimeError("ORIGINAL_UNREADABLE") from exc
    if actual != expected_hash:
        raise OriginalHashMismatchError()


def _source_parameters(source: SourceDocument) -> tuple[Any, ...]:
    quarantine_reason = None
    if source.status is SourceDocumentStatus.QUARANTINED:
        quarantine_reason = source.events[-1].reason
    return (
        source.document_id.value,
        source.fingerprint.value,
        source.original_storage_ref.value,
        source.metadata.title,
        list(source.metadata.authors),
        source.metadata.publication_year,
        source.metadata.edition,
        source.metadata.work_key[0],
        list(source.metadata.work_key[1]),
        source.status.value,
        quarantine_reason,
    )


def _source_from_row(row: Any) -> SourceDocument:
    source = SourceDocument.register_original(
        document_id=DocumentId.from_value(row[0]),
        fingerprint=SourceFingerprint.from_value(row[1]),
        original_storage_ref=OriginalStorageRef.from_value(row[2]),
        metadata=BibliographicMetadata(
            title=row[3],
            authors=tuple(row[4]),
            publication_year=row[5],
            edition=row[6],
        ),
    )
    if SourceDocumentStatus(row[7]) is SourceDocumentStatus.QUARANTINED:
        return source.quarantine(row[8])
    return source


def _decision_from_row(row: Any) -> PageDecision:
    return PageDecision(
        page_number=PageNumber.from_value(row[0]),
        page_state=PageDecisionState(row[1]),
        signals=PageDiagnosticSignals(
            native_text_state=NativeTextSignal(row[2]),
            image_state=PageImageSignal(row[3]),
            existing_ocr_state=ExistingOcrSignal(row[4]),
            layout_complexity=LayoutComplexitySignal(row[5]),
            corruption_state=PageCorruptionSignal(row[6]),
            mixed_content_detected=row[7],
            has_table=row[8],
            has_formula=row[9],
        ),
        diagnostic_version=DiagnosticVersion.from_value(row[10]),
        justification=row[11],
    )


def _route_from_row(row: Any) -> PageRoute:
    return PageRoute(
        page_number=PageNumber.from_value(row[0]),
        route_name=PageRouteName(row[1]),
        decision_mode=RouteDecisionMode(row[2]),
        confidence_score=row[3],
        preprocessing_action=PagePreprocessingAction(row[4]),
        routing_policy_version=RoutingPolicyVersion.from_value(row[5]),
        justification=row[6],
    )


__all__ = [
    "CorpusOriginalSourceStore",
    "DocumentPersistenceAdapters",
    "PostgresDocumentConversionRepository",
    "PostgresDocumentPersistence",
    "PostgresProcessingRunRepository",
    "build_document_persistence",
]
