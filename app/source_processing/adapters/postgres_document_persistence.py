"""Adaptateurs durables SP: PostgreSQL pour l'état et corpus pour les PDF."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NamedTuple
from uuid import uuid4

from app.contracts.technical_jobs import JobRequest
from app.platform.configuration import ApplicationConfiguration
from app.platform.postgres import (
    PostgresConnection,
    PostgresConnectionFactory,
    PostgresCursor,
)
from app.platform.request_context import current_trace_id
from app.source_processing.application.document_commands import (
    DocumentConversionExecutionPhase,
    DocumentConversionState,
    DocumentConversionStatus,
)
from app.source_processing.application.document_queries import DocumentStateSnapshot
from app.source_processing.application.native_document_conversion_worker import (
    NativeCanonicalPublication,
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
    ProcessingRunFailed,
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


class _ProcessingRunRow(NamedTuple):
    processing_run_id: str
    document_id: str
    source_page_count: int
    status: str
    manual_review_reason: str | None
    blocking_policy_version: str | None
    aggregate_version: int
    failure_error_code: str | None

    @classmethod
    def from_database(cls, row: Any) -> _ProcessingRunRow:
        return cls(*_database_row_values(row, len(cls._fields), "PROCESSING_RUN"))


class _ManifestEntryRow(NamedTuple):
    page_number: int
    state: str

    @classmethod
    def from_grouped(cls, row: Any) -> _ManifestEntryRow:
        return cls(*_database_row_values(row, len(cls._fields), "MANIFEST_ENTRY"))


class _ManifestEntryDatabaseRow(NamedTuple):
    processing_run_id: str
    page_number: int
    state: str

    @classmethod
    def from_database(cls, row: Any) -> _ManifestEntryDatabaseRow:
        return cls(*_database_row_values(row, len(cls._fields), "MANIFEST_ENTRY_DATABASE"))

    def grouped(self) -> _ManifestEntryRow:
        return _ManifestEntryRow(self.page_number, self.state)


class _DecisionRow(NamedTuple):
    page_number: int
    page_state: str
    native_text_state: str
    image_state: str
    existing_ocr_state: str
    layout_complexity: str
    corruption_state: str
    mixed_content_detected: bool
    has_table: bool
    has_formula: bool
    diagnostic_version: str
    justification: str


class _DecisionDatabaseRow(NamedTuple):
    processing_run_id: str
    page_number: int
    page_state: str
    native_text_state: str
    image_state: str
    existing_ocr_state: str
    layout_complexity: str
    corruption_state: str
    mixed_content_detected: bool
    has_table: bool
    has_formula: bool
    diagnostic_version: str
    justification: str

    @classmethod
    def from_database(cls, row: Any) -> _DecisionDatabaseRow:
        return cls(*_database_row_values(row, len(cls._fields), "DECISION_DATABASE"))

    def grouped(self) -> _DecisionRow:
        return _DecisionRow(*self[1:])


class _RoutePlanRow(NamedTuple):
    routing_policy_version: str
    dominant_route_name: str
    confidence_score: float


class _RoutePlanDatabaseRow(NamedTuple):
    processing_run_id: str
    routing_policy_version: str
    dominant_route_name: str
    confidence_score: float

    @classmethod
    def from_database(cls, row: Any) -> _RoutePlanDatabaseRow:
        return cls(*_database_row_values(row, len(cls._fields), "ROUTE_PLAN_DATABASE"))

    def grouped(self) -> _RoutePlanRow:
        return _RoutePlanRow(*self[1:])


class _RouteRow(NamedTuple):
    page_number: int
    route_name: str
    decision_mode: str
    confidence_score: float
    preprocessing_action: str
    routing_policy_version: str
    justification: str
    is_exception: bool


class _RouteDatabaseRow(NamedTuple):
    processing_run_id: str
    page_number: int
    route_name: str
    decision_mode: str
    confidence_score: float
    preprocessing_action: str
    routing_policy_version: str
    justification: str
    is_exception: bool

    @classmethod
    def from_database(cls, row: Any) -> _RouteDatabaseRow:
        return cls(*_database_row_values(row, len(cls._fields), "ROUTE_DATABASE"))

    def grouped(self) -> _RouteRow:
        return _RouteRow(*self[1:])


@dataclass(slots=True)
class _GroupedProcessingRunRows:
    manifest: dict[str, list[_ManifestEntryRow]]
    decisions: dict[str, list[_DecisionRow]]
    plans: dict[str, _RoutePlanRow]
    routes: dict[str, list[_RouteRow]]


_PROCESSING_RUN_COLUMNS_SQL = ", ".join(_ProcessingRunRow._fields)
_MANIFEST_ENTRY_COLUMNS_SQL = ", ".join(_ManifestEntryDatabaseRow._fields)
_DECISION_COLUMNS_SQL = ", ".join(_DecisionDatabaseRow._fields)
_ROUTE_PLAN_COLUMNS_SQL = ", ".join(_RoutePlanDatabaseRow._fields)
_ROUTE_COLUMNS_SQL = ", ".join(_RouteDatabaseRow._fields)


class ProcessingRunVersionConflictError(RuntimeError):
    """Conflit explicite entre deux writers du même agrégat SP."""

    def __init__(self) -> None:
        super().__init__("PROCESSING_RUN_VERSION_CONFLICT")


class CorpusQuotaExceededError(RuntimeError):
    """Refus stable avant toute écriture dépassant le quota agrégé."""

    def __init__(self) -> None:
        self.error_code = "CORPUS_QUOTA_EXCEEDED"
        super().__init__(self.error_code)


@dataclass(frozen=True, slots=True)
class DocumentCorpusStatusRow:
    """Projection SQL légère de la liste, sans enfant documentaire."""

    document_id: str
    title: str
    document_status: str
    diagnostic_status: str
    conversion_status: str
    canonical_version_id: str | None
    manual_review_reason: str | None
    failure_error_code: str | None
    conversion_action_available: bool


class PostgresCorpusQuotaRepository:
    """Compteur agrégé sérialisé par verrou de ligne PostgreSQL."""

    def __init__(self, *, connection_factory: PostgresConnectionFactory) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory quota invalide")
        self._connection_factory = connection_factory

    def reserve(self, *, fingerprint: str, content_length: int, quota_bytes: int) -> bool:
        SourceFingerprint.from_value(fingerprint)
        if isinstance(content_length, bool) or not isinstance(content_length, int) or content_length < 1:
            raise ValueError("content_length quota invalide")
        if isinstance(quota_bytes, bool) or not isinstance(quota_bytes, int) or quota_bytes < 1:
            raise ValueError("quota_bytes invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT total_bytes FROM source_processing.corpus_quota WHERE singleton = true FOR UPDATE",
                        (),
                    )
                    usage_row = cursor.fetchone()
                    if usage_row is None:
                        raise RuntimeError("CORPUS_QUOTA_STATE_MISSING")
                    cursor.execute(
                        "SELECT content_length FROM source_processing.corpus_original_reservations WHERE fingerprint = %s",
                        (fingerprint,),
                    )
                    existing = cursor.fetchone()
                    if existing is not None:
                        if existing[0] != content_length:
                            raise RuntimeError("CORPUS_QUOTA_RESERVATION_CONFLICT")
                        return False
                    if usage_row[0] + content_length > quota_bytes:
                        raise CorpusQuotaExceededError()
                    cursor.execute(
                        "INSERT INTO source_processing.corpus_original_reservations (fingerprint, content_length) VALUES (%s, %s)",
                        (fingerprint, content_length),
                    )
                    cursor.execute(
                        "UPDATE source_processing.corpus_quota SET total_bytes = total_bytes + %s WHERE singleton = true",
                        (content_length,),
                    )
        return True

    def release(self, *, fingerprint: str, content_length: int) -> None:
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT total_bytes FROM source_processing.corpus_quota WHERE singleton = true FOR UPDATE",
                        (),
                    )
                    if cursor.fetchone() is None:
                        raise RuntimeError("CORPUS_QUOTA_STATE_MISSING")
                    cursor.execute(
                        "DELETE FROM source_processing.corpus_original_reservations WHERE fingerprint = %s AND content_length = %s RETURNING content_length",
                        (fingerprint, content_length),
                    )
                    removed = cursor.fetchone()
                    if removed is not None:
                        cursor.execute(
                            "UPDATE source_processing.corpus_quota SET total_bytes = total_bytes - %s WHERE singleton = true",
                            (content_length,),
                        )

    def current_usage_bytes(self) -> int:
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT total_bytes FROM source_processing.corpus_quota WHERE singleton = true",
                    (),
                )
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("CORPUS_QUOTA_STATE_MISSING")
        return row[0]

    def reset_for_acceptance_test(self) -> None:
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM source_processing.corpus_original_reservations", ())
                    cursor.execute(
                        "UPDATE source_processing.corpus_quota SET total_bytes = 0 WHERE singleton = true",
                        (),
                    )


@dataclass(frozen=True, slots=True)
class OutboxSubmissionDecision:
    """Résultat local SP avant relais éventuellement cohérent vers platform."""

    outbox_id: str
    created: bool

    def __post_init__(self) -> None:
        if not isinstance(self.outbox_id, str) or not self.outbox_id.startswith("OUTBOX-SP-"):
            raise ValueError("outbox_id invalide")
        if not isinstance(self.created, bool):
            raise ValueError("created non booléen")


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

    def put_original_path_if_absent(
        self,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        source_path: Path,
    ) -> str:
        if not isinstance(source_path, Path) or not source_path.is_file():
            raise ValueError("source_path invalide")
        _verify_file_hash(source_path, fingerprint.value)
        relative_path = Path(document_id.value) / f"{fingerprint.value}.pdf"
        target = self._corpus_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            _verify_file_hash(target, fingerprint.value)
            return f"{_ARTIFACT_PREFIX}{relative_path.as_posix()}"
        temporary = target.parent / f".{target.name}.{uuid4().hex}.tmp"
        try:
            with source_path.open("rb") as source, temporary.open("xb") as destination:
                while chunk := source.read(64 * 1024):
                    destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())
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


class QuotaEnforcedOriginalSourceStore(CorpusOriginalSourceStore):
    """Stockage corpus dont chaque nouvel original réserve son volume durable."""

    def __init__(
        self,
        *,
        corpus_root: Path,
        quota_repository: PostgresCorpusQuotaRepository,
        quota_bytes: int,
    ) -> None:
        super().__init__(corpus_root=corpus_root)
        if not isinstance(quota_repository, PostgresCorpusQuotaRepository):
            raise ValueError("quota_repository invalide")
        if isinstance(quota_bytes, bool) or not isinstance(quota_bytes, int) or quota_bytes < 1:
            raise ValueError("quota_bytes invalide")
        self._quota_repository = quota_repository
        self._quota_bytes = quota_bytes

    def put_original_if_absent(
        self,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        original_content: bytes,
    ) -> str:
        reserved = self._quota_repository.reserve(
            fingerprint=fingerprint.value,
            content_length=len(original_content),
            quota_bytes=self._quota_bytes,
        )
        try:
            return super().put_original_if_absent(document_id, fingerprint, original_content)
        except BaseException:
            if reserved:
                self._quota_repository.release(
                    fingerprint=fingerprint.value,
                    content_length=len(original_content),
                )
            raise

    def put_original_path_if_absent(
        self,
        document_id: DocumentId,
        fingerprint: SourceFingerprint,
        source_path: Path,
    ) -> str:
        content_length = source_path.stat().st_size
        reserved = self._quota_repository.reserve(
            fingerprint=fingerprint.value,
            content_length=content_length,
            quota_bytes=self._quota_bytes,
        )
        try:
            return super().put_original_path_if_absent(document_id, fingerprint, source_path)
        except BaseException:
            if reserved:
                self._quota_repository.release(
                    fingerprint=fingerprint.value,
                    content_length=content_length,
                )
            raise


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

    def list_document_snapshots(
        self,
        *,
        limit: int,
        after_document_id: str | None,
    ) -> tuple[DocumentStateSnapshot, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 1000:
            raise ValueError("limit corpus invalide")
        parsed_after = None
        if after_document_id is not None:
            parsed_after = DocumentId.from_value(after_document_id).value
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                        (),
                    )
                    predicate = "" if parsed_after is None else "WHERE document_id > %s"
                    parameters: tuple[Any, ...] = () if parsed_after is None else (parsed_after,)
                    cursor.execute(
                        f"""
                        SELECT document_id, fingerprint, original_storage_ref, title,
                               authors, publication_year, edition, status,
                               quarantine_reason
                          FROM source_processing.source_documents
                          {predicate}
                         ORDER BY document_id
                         LIMIT %s
                        """,
                        (*parameters, limit),
                    )
                    sources = tuple(_source_from_row(row) for row in cursor.fetchall())
                    if len(sources) == 0:
                        return ()
                    document_ids = [source.document_id.value for source in sources]
                    cursor.execute(
                        f"""
                        SELECT {_PROCESSING_RUN_COLUMNS_SQL}
                          FROM source_processing.document_processing_runs
                         WHERE document_id = ANY(%s)
                         ORDER BY document_id
                        """,
                        (document_ids,),
                    )
                    run_rows = tuple(
                        _ProcessingRunRow.from_database(row) for row in cursor.fetchall()
                    )
                    run_ids = [row.processing_run_id for row in run_rows]
                    grouped = _load_processing_run_children(cursor, run_ids)
                    cursor.execute(
                        """
                        SELECT document_id, conversion_status, canonical_version_id,
                               rejection_error_code, execution_phase, completed_units,
                               total_units, failure_error_code
                          FROM source_processing.document_conversion_requests
                         WHERE document_id = ANY(%s)
                        """,
                        (document_ids,),
                    )
                    conversions = {
                        row[0]: DocumentConversionState(
                            document_id=DocumentId.from_value(row[0]),
                            conversion_status=DocumentConversionStatus.from_value(row[1]),
                            canonical_version_id=row[2],
                            rejection_error_code=row[3],
                            execution_phase=DocumentConversionExecutionPhase.from_value(row[4]),
                            completed_units=row[5],
                            total_units=row[6],
                            failure_error_code=row[7],
                        )
                        for row in cursor.fetchall()
                    }
        runs = {
            row.document_id: _processing_run_from_grouped_rows(row, grouped)
            for row in run_rows
        }
        return tuple(
            DocumentStateSnapshot(
                source_document=source,
                processing_run=runs.get(source.document_id.value),
                conversion=conversions.get(source.document_id.value),
            )
            for source in sources
        )

    def list_document_status_rows(
        self,
        *,
        limit: int,
        after_document_id: str | None,
    ) -> tuple[DocumentCorpusStatusRow, ...]:
        """Lit une page de statuts en une requête sans hydrater les enfants SP."""

        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 101:
            raise ValueError("limit corpus invalide")
        parsed_after = None
        if after_document_id is not None:
            parsed_after = DocumentId.from_value(after_document_id).value
        predicate = "" if parsed_after is None else "WHERE source.document_id > %s"
        parameters: tuple[Any, ...] = () if parsed_after is None else (parsed_after,)
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                        (),
                    )
                    cursor.execute(
                        f"""
                        SELECT source.document_id,
                               source.title,
                               source.status,
                               COALESCE(run.status, 'DIAGNOSTIC_NOT_REQUESTED'),
                               COALESCE(conversion.conversion_status, 'CONVERSION_NOT_REQUESTED'),
                               conversion.canonical_version_id,
                               run.manual_review_reason,
                               run.failure_error_code,
                                COALESCE(
                                    (
                                        conversion.document_id IS NULL
                                        AND run.status = 'ROUTE_PLANNED'
                                        AND (SELECT COUNT(*) FROM source_processing.page_routes AS route
                                             WHERE route.processing_run_id = run.processing_run_id)
                                            = run.source_page_count
                                    ),
                                    FALSE
                                ) AS conversion_action_available
                          FROM source_processing.source_documents AS source
                          LEFT JOIN source_processing.document_processing_runs AS run
                            ON run.document_id = source.document_id
                          LEFT JOIN source_processing.document_conversion_requests AS conversion
                            ON conversion.document_id = source.document_id
                          {predicate}
                         ORDER BY source.document_id
                         LIMIT %s
                        """,
                        (*parameters, limit),
                    )
                    rows = tuple(cursor.fetchall())
        return tuple(DocumentCorpusStatusRow(*row) for row in rows)

    def find_document_snapshot(
        self,
        document_id: DocumentId,
    ) -> DocumentStateSnapshot | None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                        (),
                    )
                source = self._find_source_in_connection(
                    connection,
                    "document_id = %s",
                    (document_id.value,),
                )
                if source is None:
                    return None
                return DocumentStateSnapshot(
                    source_document=source,
                    processing_run=self._load_processing_run(connection, document_id),
                    conversion=self._load_conversion(connection, document_id),
                )

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
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                        (),
                    )
                return self._load_processing_run(connection, document_id)

    def submit_processing_run(
        self,
        processing_run: DocumentProcessingRun,
        job_request: JobRequest,
    ) -> OutboxSubmissionDecision:
        if not isinstance(processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                submission = self._enqueue_job_outbox(
                    connection=connection,
                    job_request=job_request,
                    trace_id=current_trace_id(),
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
            return self._load_conversion(connection, document_id)

    def submit_conversion_request(
        self,
        conversion_state: DocumentConversionState,
        job_request: JobRequest,
    ) -> OutboxSubmissionDecision:
        if not isinstance(conversion_state, DocumentConversionState):
            raise ValueError("conversion_state invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction():
                submission = self._enqueue_job_outbox(
                    connection=connection,
                    job_request=job_request,
                    trace_id=current_trace_id(),
                )
                if submission.created:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO source_processing.document_conversion_requests (
                                document_id, conversion_status, canonical_version_id,
                                rejection_error_code, execution_phase, completed_units,
                                total_units, failure_error_code, submission_id, job_id
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                            ON CONFLICT (document_id) DO NOTHING
                            RETURNING document_id
                            """,
                            (
                                conversion_state.document_id.value,
                                conversion_state.conversion_status.value,
                                conversion_state.canonical_version_id,
                                conversion_state.rejection_error_code,
                                conversion_state.execution_phase.value,
                                conversion_state.completed_units,
                                conversion_state.total_units,
                                conversion_state.failure_error_code,
                                submission.outbox_id,
                            ),
                        )
                        if cursor.fetchone() is None:
                            raise RuntimeError("CONVERSION_PERSISTENCE_CONFLICT")
                return submission

    def complete_native_conversion(self, publication: NativeCanonicalPublication) -> None:
        if not isinstance(publication, NativeCanonicalPublication):
            raise ValueError("publication native invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO source_processing.canonical_source_versions (
                        canonical_source_id, canonical_version_id, document_id,
                        canonical_artifact_ref, canonical_artifact_sha256,
                        route_name, tool_version
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (canonical_version_id) DO NOTHING
                    """,
                    (
                        publication.canonical_source_id,
                        publication.canonical_version_id,
                        publication.document_id.value,
                        publication.canonical_artifact_ref,
                        publication.canonical_artifact_sha256,
                        publication.route_name,
                        publication.tool_version,
                    ),
                )
                cursor.execute(
                    """
                    UPDATE source_processing.document_conversion_requests
                       SET conversion_status = 'CANONICAL_ACCEPTED',
                           execution_phase = 'SUCCEEDED',
                           completed_units = total_units,
                           canonical_version_id = %s,
                           rejection_error_code = NULL,
                           failure_error_code = NULL,
                           canonical_artifact_ref = %s,
                           canonical_artifact_sha256 = %s,
                           route_name = %s,
                           tool_version = %s,
                           accepted_at = CURRENT_TIMESTAMP
                     WHERE document_id = %s
                       AND conversion_status = 'CONVERSION_REQUESTED'
                    """,
                    (
                        publication.canonical_version_id,
                        publication.canonical_artifact_ref,
                        publication.canonical_artifact_sha256,
                        publication.route_name,
                        publication.tool_version,
                        publication.document_id.value,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("CONVERSION_PERSISTENCE_CONFLICT")

    def begin_native_conversion(self, *, document_id: DocumentId) -> None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.document_conversion_requests
                       SET execution_phase = 'RUNNING'
                     WHERE document_id = %s
                       AND conversion_status = 'CONVERSION_REQUESTED'
                       AND execution_phase = 'QUEUED'
                    """,
                    (document_id.value,),
                )
                if cursor.rowcount == 1:
                    return
                cursor.execute(
                    """
                    SELECT execution_phase
                      FROM source_processing.document_conversion_requests
                     WHERE document_id = %s
                    """,
                    (document_id.value,),
                )
                row = cursor.fetchone()
                if row is None or row[0] != "RUNNING":
                    raise RuntimeError("CONVERSION_PERSISTENCE_CONFLICT")

    def record_conversion_progress(self, *, document_id: DocumentId, completed_units: int) -> None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        if isinstance(completed_units, bool) or not isinstance(completed_units, int) or completed_units < 1:
            raise ValueError("completed_units invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.document_conversion_requests
                       SET completed_units = %s
                     WHERE document_id = %s
                       AND conversion_status = 'CONVERSION_REQUESTED'
                       AND execution_phase = 'RUNNING'
                       AND completed_units = %s
                       AND total_units >= %s
                    """,
                    (
                        completed_units,
                        document_id.value,
                        completed_units - 1,
                        completed_units,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("CONVERSION_PERSISTENCE_CONFLICT")

    def reject_native_conversion(self, *, document_id: DocumentId, error_code: str) -> None:
        if not isinstance(document_id, DocumentId):
            raise ValueError("document_id invalide")
        if not isinstance(error_code, str) or error_code.strip() == "" or error_code != error_code.strip():
            raise ValueError("error_code invalide")
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE source_processing.document_conversion_requests
                       SET conversion_status = 'QA_REJECTED',
                           execution_phase = 'FAILED',
                           rejection_error_code = %s,
                           failure_error_code = %s,
                           canonical_version_id = NULL
                     WHERE document_id = %s
                       AND conversion_status = 'CONVERSION_REQUESTED'
                    """,
                    (error_code, error_code, document_id.value),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError("CONVERSION_PERSISTENCE_CONFLICT")

    def _enqueue_job_outbox(
        self,
        *,
        connection: PostgresConnection,
        job_request: JobRequest,
        trace_id: str,
    ) -> OutboxSubmissionDecision:
        if not isinstance(job_request, JobRequest):
            raise ValueError("job_request invalide")
        identity = job_request.idempotence_key.identity_tuple()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ("sp-outbox|" + "|".join(identity),),
            )
            cursor.execute(
                """
                SELECT outbox_id
                  FROM source_processing.job_outbox
                 WHERE job_name = %s
                   AND input_hash = %s
                   AND configuration_hash = %s
                   AND code_version = %s
                   AND model_version = %s
                 FOR UPDATE
                """,
                identity,
            )
            existing = cursor.fetchone()
            if existing is not None:
                return OutboxSubmissionDecision(outbox_id=existing[0], created=False)
            cursor.execute(
                """
                INSERT INTO source_processing.job_outbox (
                    job_name, priority, input_hash, configuration_hash,
                    code_version, model_version, payload, trace_id, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending')
                RETURNING outbox_id
                """,
                (
                    job_request.job_name,
                    job_request.priority.value,
                    *identity[1:],
                    json.dumps(
                        dict(job_request.payload), separators=(",", ":"), sort_keys=True
                    ),
                    trace_id,
                ),
            )
            inserted = cursor.fetchone()
        if inserted is None:
            raise RuntimeError("JOB_OUTBOX_PERSISTENCE_FAILED")
        return OutboxSubmissionDecision(outbox_id=inserted[0], created=True)

    def _find_source(self, predicate: str, parameters: tuple[Any, ...]) -> SourceDocument | None:
        with self._connection_factory.connect() as connection:
            return self._find_source_in_connection(connection, predicate, parameters)

    def _find_source_in_connection(
        self,
        connection: PostgresConnection,
        predicate: str,
        parameters: tuple[Any, ...],
    ) -> SourceDocument | None:
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

    def _load_conversion(
        self,
        connection: PostgresConnection,
        document_id: DocumentId,
    ) -> DocumentConversionState | None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT document_id, conversion_status, canonical_version_id,
                       rejection_error_code, execution_phase, completed_units,
                       total_units, failure_error_code
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
            execution_phase=DocumentConversionExecutionPhase.from_value(row[4]),
            completed_units=row[5],
            total_units=row[6],
            failure_error_code=row[7],
        )

    def _save_processing_run(
        self,
        connection: PostgresConnection,
        processing_run: DocumentProcessingRun,
        *,
        insert_only: bool = False,
    ) -> None:
        conflict_clause = "DO NOTHING" if insert_only else """DO UPDATE SET
            source_page_count = EXCLUDED.source_page_count,
            status = EXCLUDED.status,
            manual_review_reason = EXCLUDED.manual_review_reason,
            blocking_policy_version = EXCLUDED.blocking_policy_version,
            aggregate_version = EXCLUDED.aggregate_version,
            failure_error_code = EXCLUDED.failure_error_code
            WHERE source_processing.document_processing_runs.aggregate_version
                = EXCLUDED.aggregate_version - 1"""
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO source_processing.document_processing_runs (
                    processing_run_id, document_id, source_page_count, status,
                    manual_review_reason, blocking_policy_version, aggregate_version,
                    failure_error_code
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                    processing_run.aggregate_version,
                    processing_run.failure_error_code,
                ),
            )
            if cursor.fetchone() is None:
                if insert_only:
                    raise RuntimeError("PROCESSING_RUN_PERSISTENCE_CONFLICT")
                raise ProcessingRunVersionConflictError()
            for table in ("page_routes", "route_plans", "page_decisions", "page_manifest_entries"):
                cursor.execute(
                    f"DELETE FROM source_processing.{table} WHERE processing_run_id = %s",
                    (processing_run.processing_run_id.value,),
                )
            cursor.execute(
                """
                INSERT INTO source_processing.page_manifest_entries
                    (processing_run_id, page_number, state)
                SELECT %s, batch.page_number, batch.state
                  FROM jsonb_to_recordset(%s::jsonb)
                       AS batch(page_number integer, state text)
                """,
                (
                    processing_run.processing_run_id.value,
                    json.dumps(
                        [
                            {
                                "page_number": entry.page_number.value,
                                "state": entry.state.value,
                            }
                            for entry in processing_run.page_manifest.entries
                        ],
                        separators=(",", ":"),
                    ),
                ),
            )
            cursor.execute(
                """
                INSERT INTO source_processing.page_decisions (
                    processing_run_id, page_number, page_state,
                    native_text_state, image_state, existing_ocr_state,
                    layout_complexity, corruption_state, mixed_content_detected,
                    has_table, has_formula, diagnostic_version, justification
                )
                SELECT %s, batch.page_number, batch.page_state,
                       batch.native_text_state, batch.image_state,
                       batch.existing_ocr_state, batch.layout_complexity,
                       batch.corruption_state, batch.mixed_content_detected,
                       batch.has_table, batch.has_formula,
                       batch.diagnostic_version, batch.justification
                  FROM jsonb_to_recordset(%s::jsonb) AS batch(
                    page_number integer, page_state text, native_text_state text,
                    image_state text, existing_ocr_state text, layout_complexity text,
                    corruption_state text, mixed_content_detected boolean,
                    has_table boolean, has_formula boolean,
                    diagnostic_version text, justification text
                  )
                """,
                (
                    processing_run.processing_run_id.value,
                    json.dumps(
                        [
                            {
                                "page_number": decision.page_number.value,
                                "page_state": decision.page_state.value,
                                "native_text_state": decision.signals.native_text_state.value,
                                "image_state": decision.signals.image_state.value,
                                "existing_ocr_state": decision.signals.existing_ocr_state.value,
                                "layout_complexity": decision.signals.layout_complexity.value,
                                "corruption_state": decision.signals.corruption_state.value,
                                "mixed_content_detected": decision.signals.mixed_content_detected,
                                "has_table": decision.signals.has_table,
                                "has_formula": decision.signals.has_formula,
                                "diagnostic_version": decision.diagnostic_version.value,
                                "justification": decision.justification,
                            }
                            for decision in processing_run.page_decisions
                        ],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
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
                cursor.execute(
                    """
                    INSERT INTO source_processing.page_routes (
                        processing_run_id, page_number, route_name,
                        decision_mode, confidence_score, preprocessing_action,
                        routing_policy_version, justification, is_exception
                    )
                    SELECT %s, batch.page_number, batch.route_name,
                           batch.decision_mode, batch.confidence_score,
                           batch.preprocessing_action, batch.routing_policy_version,
                           batch.justification, batch.is_exception
                      FROM jsonb_to_recordset(%s::jsonb) AS batch(
                        page_number integer, route_name text, decision_mode text,
                        confidence_score double precision, preprocessing_action text,
                        routing_policy_version text, justification text,
                        is_exception boolean
                      )
                    """,
                    (
                        processing_run.processing_run_id.value,
                        json.dumps(
                            [
                                {
                                    "page_number": route.page_number.value,
                                    "route_name": route.route_name.value,
                                    "decision_mode": route.decision_mode.value,
                                    "confidence_score": route.confidence_score,
                                    "preprocessing_action": route.preprocessing_action.value,
                                    "routing_policy_version": route.routing_policy_version.value,
                                    "justification": route.justification,
                                    "is_exception": route.page_number.value in exception_pages,
                                }
                                for route in route_plan.page_routes
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    ),
                )

    def _load_processing_run(
        self,
        connection: PostgresConnection,
        document_id: DocumentId,
    ) -> DocumentProcessingRun | None:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {_PROCESSING_RUN_COLUMNS_SQL}
                  FROM source_processing.document_processing_runs
                 WHERE document_id = %s
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                (document_id.value,),
            )
            database_row = cursor.fetchone()
            if database_row is None:
                return None
            row = _ProcessingRunRow.from_database(database_row)
            grouped = _load_processing_run_children(cursor, [row.processing_run_id])
        return _processing_run_from_grouped_rows(row, grouped)


def _load_processing_run_children(
    cursor: PostgresCursor,
    processing_run_ids: list[str],
) -> _GroupedProcessingRunRows:
    grouped = _GroupedProcessingRunRows(manifest={}, decisions={}, plans={}, routes={})
    cursor.execute(
        f"""
        SELECT {_MANIFEST_ENTRY_COLUMNS_SQL}
          FROM source_processing.page_manifest_entries
         WHERE processing_run_id = ANY(%s)
         ORDER BY processing_run_id, page_number
        """,
        (processing_run_ids,),
    )
    for database_row in cursor.fetchall():
        row = _ManifestEntryDatabaseRow.from_database(database_row)
        grouped.manifest.setdefault(row.processing_run_id, []).append(row.grouped())
    cursor.execute(
        f"""
        SELECT {_DECISION_COLUMNS_SQL}
          FROM source_processing.page_decisions
         WHERE processing_run_id = ANY(%s)
         ORDER BY processing_run_id, page_number
        """,
        (processing_run_ids,),
    )
    for database_row in cursor.fetchall():
        row = _DecisionDatabaseRow.from_database(database_row)
        grouped.decisions.setdefault(row.processing_run_id, []).append(row.grouped())
    cursor.execute(
        f"""
        SELECT {_ROUTE_PLAN_COLUMNS_SQL}
          FROM source_processing.route_plans
         WHERE processing_run_id = ANY(%s)
        """,
        (processing_run_ids,),
    )
    for database_row in cursor.fetchall():
        row = _RoutePlanDatabaseRow.from_database(database_row)
        grouped.plans[row.processing_run_id] = row.grouped()
    cursor.execute(
        f"""
        SELECT {_ROUTE_COLUMNS_SQL}
          FROM source_processing.page_routes
         WHERE processing_run_id = ANY(%s)
         ORDER BY processing_run_id, page_number
        """,
        (processing_run_ids,),
    )
    for database_row in cursor.fetchall():
        row = _RouteDatabaseRow.from_database(database_row)
        grouped.routes.setdefault(row.processing_run_id, []).append(row.grouped())
    return grouped


def _processing_run_from_grouped_rows(
    row: Any,
    grouped: _GroupedProcessingRunRows,
) -> DocumentProcessingRun:
    parsed_row = row if isinstance(row, _ProcessingRunRow) else _ProcessingRunRow.from_database(row)
    processing_run_id = parsed_row.processing_run_id
    manifest_rows = grouped.manifest.get(processing_run_id, ())
    decision_rows = grouped.decisions.get(processing_run_id, ())
    plan_row = grouped.plans.get(processing_run_id)
    route_rows = grouped.routes.get(processing_run_id, ())
    run_id = ProcessingRunId.from_value(processing_run_id)
    document_id = DocumentId.from_value(parsed_row.document_id)
    manifest = PageManifest.from_entries(
        source_page_count=parsed_row.source_page_count,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(item.page_number),
                state=PageManifestEntryState(item.state),
            )
            for item in manifest_rows
        ),
    )
    decisions = tuple(_decision_from_row(item) for item in decision_rows)
    routes = tuple(_route_from_row(item) for item in route_rows)
    route_plan = None
    if plan_row is not None:
        route_plan = RoutePlan(
            routing_policy_version=RoutingPolicyVersion.from_value(
                plan_row.routing_policy_version
            ),
            page_routes=routes,
            dominant_route_name=PageRouteName(plan_row.dominant_route_name),
            page_exceptions=tuple(
                route for route, route_row in zip(routes, route_rows) if route_row.is_exception
            ),
            confidence_score=plan_row.confidence_score,
        )
    return DocumentProcessingRun(
        processing_run_id=run_id,
        document_id=document_id,
        page_manifest=manifest,
        page_decisions=decisions,
        route_plan=route_plan,
        manual_review_reason=parsed_row.manual_review_reason,
        blocking_policy_version=None
        if parsed_row.blocking_policy_version is None
        else RoutingPolicyVersion.from_value(parsed_row.blocking_policy_version),
        status=DocumentProcessingRunStatus(parsed_row.status),
        aggregate_version=parsed_row.aggregate_version,
        events=(
            DocumentProcessingStarted(
                processing_run_id=run_id,
                document_id=document_id,
                source_page_count=parsed_row.source_page_count,
            ),
        )
        + (
            (
                ProcessingRunFailed(
                    processing_run_id=run_id,
                    document_id=document_id,
                    error_code=parsed_row.failure_error_code,
                ),
            )
            if DocumentProcessingRunStatus(parsed_row.status)
            is DocumentProcessingRunStatus.FAILED
            else ()
        ),
        failure_error_code=parsed_row.failure_error_code,
    )


class PostgresProcessingRunRepository:
    """Vue du port ``ProcessingRunRepository`` sur la façade durable."""

    def __init__(self, persistence: PostgresDocumentPersistence) -> None:
        if not isinstance(persistence, PostgresDocumentPersistence):
            raise ValueError("persistence invalide")
        self._persistence = persistence

    def save(self, processing_run: DocumentProcessingRun) -> None:
        self._persistence.save(processing_run)

    def save_transition(
        self,
        processing_run: DocumentProcessingRun,
        *,
        expected_status: DocumentProcessingRunStatus,
    ) -> None:
        if not isinstance(processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        if not isinstance(expected_status, DocumentProcessingRunStatus):
            raise ValueError("expected_status invalide")
        current = self.find_by_document_id(processing_run.document_id)
        if current is None or current.status is not expected_status:
            raise ProcessingRunVersionConflictError()
        self._persistence.save(processing_run)

    def find_by_document_id(self, document_id: DocumentId) -> DocumentProcessingRun | None:
        return self._persistence.find_processing_run_by_document_id(document_id)

    def submit_processing_run(
        self,
        processing_run: DocumentProcessingRun,
        job_request: JobRequest,
    ) -> OutboxSubmissionDecision:
        return self._persistence.submit_processing_run(processing_run, job_request)


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
        job_request: JobRequest,
    ) -> OutboxSubmissionDecision:
        return self._persistence.submit_conversion_request(conversion_state, job_request)

    def complete_native_conversion(self, publication: NativeCanonicalPublication) -> None:
        self._persistence.complete_native_conversion(publication)

    def begin_native_conversion(self, *, document_id: DocumentId) -> None:
        self._persistence.begin_native_conversion(document_id=document_id)

    def record_conversion_progress(self, *, document_id: DocumentId, completed_units: int) -> None:
        self._persistence.record_conversion_progress(
            document_id=document_id,
            completed_units=completed_units,
        )

    def reject_native_conversion(self, *, document_id: DocumentId, error_code: str) -> None:
        self._persistence.reject_native_conversion(document_id=document_id, error_code=error_code)


@dataclass(frozen=True)
class DocumentPersistenceAdapters:
    """Adaptateurs durables injectables dans l'API et ``worker-documents``."""

    original_source_store: QuotaEnforcedOriginalSourceStore
    source_document_repository: PostgresDocumentPersistence
    processing_run_repository: PostgresProcessingRunRepository
    document_conversion_repository: PostgresDocumentConversionRepository


def build_document_persistence(
    application_configuration: ApplicationConfiguration,
    *,
    connection_factory: PostgresConnectionFactory,
) -> DocumentPersistenceAdapters:
    """Construit le stockage partagé uniquement depuis M13-config."""

    if not isinstance(application_configuration, ApplicationConfiguration):
        raise ValueError("application_configuration invalide")
    if not callable(getattr(connection_factory, "connect", None)):
        raise ValueError("connection_factory invalide")
    persistence = PostgresDocumentPersistence(connection_factory=connection_factory)
    return DocumentPersistenceAdapters(
        original_source_store=QuotaEnforcedOriginalSourceStore(
            corpus_root=Path(application_configuration.paths.corpus_root),
            quota_repository=PostgresCorpusQuotaRepository(
                connection_factory=connection_factory
            ),
            quota_bytes=application_configuration.paths.corpus_quota_bytes,
        ),
        source_document_repository=persistence,
        processing_run_repository=PostgresProcessingRunRepository(persistence),
        document_conversion_repository=PostgresDocumentConversionRepository(persistence),
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


def _decision_from_row(row: _DecisionRow) -> PageDecision:
    return PageDecision(
        page_number=PageNumber.from_value(row.page_number),
        page_state=PageDecisionState(row.page_state),
        signals=PageDiagnosticSignals(
            native_text_state=NativeTextSignal(row.native_text_state),
            image_state=PageImageSignal(row.image_state),
            existing_ocr_state=ExistingOcrSignal(row.existing_ocr_state),
            layout_complexity=LayoutComplexitySignal(row.layout_complexity),
            corruption_state=PageCorruptionSignal(row.corruption_state),
            mixed_content_detected=row.mixed_content_detected,
            has_table=row.has_table,
            has_formula=row.has_formula,
        ),
        diagnostic_version=DiagnosticVersion.from_value(row.diagnostic_version),
        justification=row.justification,
    )


def _route_from_row(row: _RouteRow) -> PageRoute:
    return PageRoute(
        page_number=PageNumber.from_value(row.page_number),
        route_name=PageRouteName(row.route_name),
        decision_mode=RouteDecisionMode(row.decision_mode),
        confidence_score=row.confidence_score,
        preprocessing_action=PagePreprocessingAction(row.preprocessing_action),
        routing_policy_version=RoutingPolicyVersion.from_value(row.routing_policy_version),
        justification=row.justification,
    )


def _database_row_values(row: Any, expected_length: int, row_name: str) -> tuple[Any, ...]:
    if not isinstance(row, (tuple, list)) or len(row) != expected_length:
        actual_length = len(row) if isinstance(row, (tuple, list)) else "non-sequence"
        raise RuntimeError(
            f"SQL_ROW_SHAPE_INVALID:{row_name}:expected={expected_length}:actual={actual_length}"
        )
    return tuple(row)


__all__ = [
    "CorpusQuotaExceededError",
    "CorpusOriginalSourceStore",
    "DocumentCorpusStatusRow",
    "PostgresCorpusQuotaRepository",
    "QuotaEnforcedOriginalSourceStore",
    "DocumentPersistenceAdapters",
    "PostgresDocumentConversionRepository",
    "PostgresDocumentPersistence",
    "PostgresProcessingRunRepository",
    "ProcessingRunVersionConflictError",
    "OutboxSubmissionDecision",
    "build_document_persistence",
]
