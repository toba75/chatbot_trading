"""Persistance et lecture PostgreSQL de la source de vérité des projections KA."""

from __future__ import annotations

import json
from hashlib import sha256
from collections.abc import Mapping, Sequence
from typing import Any

from app.contracts.source_references import SourceLocator
from app.contracts.technical_jobs import JobEnvironmentIdentity
from app.knowledge_access.application.extract_projected_bibliographic_metadata import (
    ProjectedBibliographicMetadata,
)
from app.knowledge_access.application.projection_queries import (
    ProjectionCatalogRecord,
    ProjectionReadRecord,
)
from app.knowledge_access.application.request_projection import (
    ProjectionAlreadyRequestedError,
    ProjectionPersistenceDecision,
)
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.knowledge_access.domain.time import ensure_utc_instant
from app.platform.postgres import PostgresConnectionFactory


class KnowledgeProjectionVersionConflictError(RuntimeError):
    """Un writer KA obsolète ne peut pas écraser une transition plus récente."""

    def __init__(self) -> None:
        super().__init__("KA_PROJECTION_VERSION_CONFLICT")


class KnowledgeProjectionReplayConflictError(RuntimeError):
    """Une version KA rejouée ne peut désigner des sorties divergentes."""

    def __init__(self) -> None:
        super().__init__("KA_PROJECTION_REPLAY_DIVERGENCE")


class PostgresKnowledgeProjectionRepository:
    """Produit le read-model durable depuis chaque transition d'agrégat KA."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        sample_storage_limit: int,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        if (
            isinstance(sample_storage_limit, bool)
            or not isinstance(sample_storage_limit, int)
            or sample_storage_limit < 1
        ):
            raise ValueError("sample_storage_limit invalide")
        self._connection_factory = connection_factory
        self._sample_storage_limit = sample_storage_limit

    def save_if_absent(
        self,
        projection: KnowledgeProjection,
    ) -> ProjectionPersistenceDecision:
        parsed_projection = _ensure_projection(projection)
        profile = parsed_projection.projection_profile
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at, aggregate_version
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP, %s)
                    ON CONFLICT (build_fingerprint) DO NOTHING
                    RETURNING projection_id
                    """,
                    (*_projection_parameters(parsed_projection, profile), parsed_projection.aggregate_version),
                )
                inserted = cursor.fetchone()
        if inserted is not None:
            return ProjectionPersistenceDecision(
                projection=parsed_projection,
                created=True,
            )
        existing = self.projection_for_build_fingerprint(
            parsed_projection.build_fingerprint
        )
        if existing is None:
            raise RuntimeError("KNOWLEDGE_PROJECTION_PERSISTENCE_FAILED")
        return ProjectionPersistenceDecision(projection=existing, created=False)

    def require_absent_build_fingerprint(
        self,
        build_fingerprint: BuildFingerprint,
    ) -> None:
        parsed_fingerprint = _ensure_build_fingerprint(build_fingerprint)
        existing = self.projection_for_build_fingerprint(parsed_fingerprint)
        if existing is not None:
            raise ProjectionAlreadyRequestedError(
                projection_id=existing.projection_id,
                build_fingerprint=parsed_fingerprint,
            )

    def projection_for_build_fingerprint(
        self,
        build_fingerprint: BuildFingerprint,
    ) -> KnowledgeProjection | None:
        parsed_fingerprint = _ensure_build_fingerprint(build_fingerprint)
        return self._find_projection(
            predicate="build_fingerprint = %s",
            parameters=(parsed_fingerprint.value,),
        )

    def projection_for_id(self, projection_id: str) -> KnowledgeProjection:
        if not isinstance(projection_id, str) or not projection_id.startswith("PROJ-"):
            raise ValueError("projection_id invalide")
        projection = self._find_projection(
            predicate="projection_id = %s",
            parameters=(projection_id,),
        )
        if projection is None:
            raise ValueError(f"projection inconnue: {projection_id}")
        return projection

    def save_transition(
        self,
        projection: KnowledgeProjection,
    ) -> KnowledgeProjection:
        parsed_projection = _ensure_projection(projection)
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE knowledge_access.knowledge_projections
                       SET status = %s,
                           execution_phase = CASE
                               WHEN %s = 'REQUESTED' THEN 'QUEUED'
                               WHEN %s IN ('BUILDING', 'BUILT', 'INDEXING') THEN 'RUNNING'
                               WHEN %s IN ('SEARCHABLE', 'STALE', 'RETIRED') THEN 'SUCCEEDED'
                               WHEN %s = 'FAILED' THEN 'FAILED'
                               ELSE execution_phase
                           END,
                           failure_error_code = CASE
                               WHEN %s = 'FAILED' THEN 'PROJECTION_FAILED'
                               ELSE NULL
                           END,
                           completed_units = CASE
                               WHEN %s IN ('SEARCHABLE', 'STALE', 'RETIRED') THEN total_units
                               ELSE completed_units
                           END,
                           state_observed_at = CURRENT_TIMESTAMP,
                           aggregate_version = %s
                     WHERE projection_id = %s
                       AND build_fingerprint = %s
                       AND aggregate_version = %s
                    RETURNING projection_id
                    """,
                    (
                        parsed_projection.status.value,
                        parsed_projection.status.value,
                        parsed_projection.status.value,
                        parsed_projection.status.value,
                        parsed_projection.status.value,
                        parsed_projection.status.value,
                        parsed_projection.status.value,
                        parsed_projection.aggregate_version,
                        parsed_projection.projection_id,
                        parsed_projection.build_fingerprint.value,
                        parsed_projection.aggregate_version - 1,
                    ),
                )
                updated = cursor.fetchone()
        if updated is None:
            raise KnowledgeProjectionVersionConflictError()
        return parsed_projection

    def save_projection_outputs(
        self,
        *,
        projection: KnowledgeProjection,
        chunk_count: int,
        chunks: Sequence[KnowledgeChunk],
        state_observed_at: str,
        index_generation: str | None,
    ) -> None:
        if not isinstance(projection, KnowledgeProjection):
            raise ValueError("KnowledgeProjection invalide")
        samples = _ensure_chunks(chunks, projection=projection)
        if (
            isinstance(chunk_count, bool)
            or not isinstance(chunk_count, int)
            or chunk_count < len(samples)
        ):
            raise ValueError("chunk_count KA invalide")
        if len(samples) > self._sample_storage_limit:
            raise ValueError("échantillons KA au-delà de la limite de stockage")
        observed_at = ensure_utc_instant(state_observed_at, "state_observed_at")
        if projection.status is ProjectionStatus.SEARCHABLE and (
            chunk_count < 1
            or len(samples) < 1
            or not isinstance(index_generation, str)
            or index_generation.strip() == ""
            or index_generation != index_generation.strip()
        ):
            raise ValueError("KA_SEARCHABLE_OUTPUTS_INCOMPLETE")
        if index_generation is not None and (
            not isinstance(index_generation, str)
            or index_generation.strip() == ""
            or index_generation != index_generation.strip()
        ):
            raise ValueError("index_generation KA invalide")
        outputs_fingerprint = _outputs_fingerprint(
            projection=projection,
            chunk_count=chunk_count,
            samples=samples,
            state_observed_at=observed_at,
            index_generation=index_generation,
        )
        profile = projection.projection_profile
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT aggregate_version, outputs_fingerprint
                      FROM knowledge_access.knowledge_projections
                     WHERE projection_id = %s
                     FOR UPDATE
                    """,
                    (projection.projection_id,),
                )
                existing_version_row = cursor.fetchone()
                if existing_version_row is not None:
                    if existing_version_row[0] == projection.aggregate_version:
                        if existing_version_row[1] == outputs_fingerprint:
                            return
                        raise KnowledgeProjectionReplayConflictError()
                    if existing_version_row[0] != projection.aggregate_version - 1:
                        raise KnowledgeProjectionVersionConflictError()
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at, aggregate_version,
                        outputs_fingerprint, index_generation,
                        execution_phase, completed_units,
                        total_units, failure_error_code
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'SUCCEEDED', %s, %s, NULL)
                    ON CONFLICT (projection_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        chunk_count = EXCLUDED.chunk_count,
                        state_observed_at = EXCLUDED.state_observed_at,
                        aggregate_version = EXCLUDED.aggregate_version,
                        outputs_fingerprint = EXCLUDED.outputs_fingerprint,
                        index_generation = EXCLUDED.index_generation,
                        execution_phase = EXCLUDED.execution_phase,
                        completed_units = EXCLUDED.completed_units,
                        total_units = EXCLUDED.total_units,
                        failure_error_code = EXCLUDED.failure_error_code
                    """,
                    (
                        projection.projection_id,
                        projection.document_id,
                        projection.canonical_version_id,
                        profile.projection_profile_id,
                        profile.chunking_profile,
                        profile.embedding_model,
                        profile.sparse_profile,
                        profile.index_schema,
                        projection.build_fingerprint.value,
                        projection.status.value,
                        chunk_count,
                        observed_at,
                        projection.aggregate_version,
                        outputs_fingerprint,
                        index_generation,
                        chunk_count + 1,
                        chunk_count + 1,
                    ),
                )
                cursor.execute(
                    """
                    DELETE FROM knowledge_access.knowledge_projection_chunk_samples
                     WHERE projection_id = %s
                    """,
                    (projection.projection_id,),
                )
                for ordinal, sample in enumerate(samples, start=1):
                    cursor.execute(
                        """
                        INSERT INTO knowledge_access.knowledge_projection_chunk_samples (
                            projection_id, sample_ordinal, chunk_id, chunk_level,
                            parent_chunk_id, profile_id, profile_version, chunk_text,
                            content_hash, source_locators
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            projection.projection_id,
                            ordinal,
                            sample.chunk_id,
                            sample.chunk_level,
                            sample.parent_chunk_id,
                            sample.profile_id,
                            sample.profile_version,
                            sample.text,
                            sample.content_hash,
                            json.dumps(
                                [locator.to_payload() for locator in sample.source_locators],
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        ),
                    )

    def save_bibliographic_metadata(
        self,
        *,
        projection_id: str,
        metadata: ProjectedBibliographicMetadata,
    ) -> None:
        if not isinstance(projection_id, str) or not projection_id.startswith("PROJ-"):
            raise ValueError("projection_id bibliographique invalide")
        if not isinstance(metadata, ProjectedBibliographicMetadata):
            raise ValueError("métadonnées projetées invalides")
        evidence_payload = [
            {
                "field": evidence.field,
                "page_pdf": evidence.page_pdf,
                "quoted_text": evidence.quoted_text,
            }
            for evidence in metadata.evidences
        ]
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE knowledge_access.knowledge_projections
                       SET bibliographic_metadata_status = 'EXTRACTED',
                           bibliographic_title = %s,
                           bibliographic_authors = %s,
                           bibliographic_publication_year = %s,
                           bibliographic_edition = %s,
                           bibliographic_evidence = %s::jsonb,
                           bibliographic_model_id = %s,
                           bibliographic_model_revision = %s,
                           bibliographic_runtime_version = %s,
                           state_observed_at = CURRENT_TIMESTAMP
                     WHERE projection_id = %s
                       AND status = 'INDEXING'
                       AND bibliographic_metadata_status = 'PENDING'
                    """,
                    (
                        metadata.title,
                        list(metadata.authors),
                        metadata.publication_year,
                        metadata.edition,
                        json.dumps(evidence_payload, ensure_ascii=False, separators=(",", ":")),
                        metadata.model_id,
                        metadata.model_revision,
                        metadata.runtime_version,
                        projection_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise KnowledgeProjectionVersionConflictError()

    def _find_projection(
        self,
        *,
        predicate: str,
        parameters: tuple[object, ...],
    ) -> KnowledgeProjection | None:
        if predicate not in ("build_fingerprint = %s", "projection_id = %s"):
            raise ValueError("prédicat projection PostgreSQL interdit")
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT projection_id, document_id, canonical_version_id,
                           projection_profile_id, chunking_profile, embedding_model,
                           sparse_profile, index_schema, build_fingerprint, status,
                           aggregate_version
                      FROM knowledge_access.knowledge_projections
                     WHERE {predicate}
                    """,
                    parameters,
                )
                row = cursor.fetchone()
        return None if row is None else _projection_from_row(row)


class PostgresProjectionReadRepository:
    """Lit l'agrégat KA courant sans déduire son état depuis Qdrant."""

    def __init__(
        self,
        *,
        connection_factory: PostgresConnectionFactory,
        environment_identity: JobEnvironmentIdentity,
    ) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        if not isinstance(environment_identity, JobEnvironmentIdentity):
            raise ValueError("environment_identity invalide")
        self._connection_factory = connection_factory
        self._identity = environment_identity

    def current_projection_statuses_for_document_ids(
        self,
        document_ids: Sequence[str],
    ) -> Mapping[str, str]:
        """Lit en une requête le dernier statut KA de chaque document demandé."""

        if isinstance(document_ids, (str, bytes)) or not isinstance(document_ids, Sequence):
            raise ValueError("document_ids KA invalides")
        parsed_ids = tuple(document_ids)
        if len(parsed_ids) > 100 or len(set(parsed_ids)) != len(parsed_ids):
            raise ValueError("document_ids KA invalides")
        for document_id in parsed_ids:
            if not isinstance(document_id, str) or not document_id.startswith("DOC-"):
                raise ValueError("document_id KA invalide")
        if len(parsed_ids) == 0:
            return {}
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT ON (document_id) document_id, status
                      FROM knowledge_access.knowledge_projections
                     WHERE document_id = ANY(%s)
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                     ORDER BY document_id, state_observed_at DESC, projection_id DESC
                    """,
                    (
                        list(parsed_ids),
                        self._identity.environment,
                        self._identity.deployment_id,
                        self._identity.configuration_hash,
                    ),
                )
                rows = cursor.fetchall()
        return {str(document_id): str(status) for document_id, status in rows}

    def current_projection_catalog_for_document_ids(
        self,
        document_ids: Sequence[str],
    ) -> Mapping[str, ProjectionCatalogRecord]:
        """Lit statut et métadonnées dérivées en une requête KA bornée."""

        if isinstance(document_ids, (str, bytes)) or not isinstance(document_ids, Sequence):
            raise ValueError("document_ids KA invalides")
        parsed_ids = tuple(document_ids)
        if len(parsed_ids) > 100 or len(set(parsed_ids)) != len(parsed_ids):
            raise ValueError("document_ids KA invalides")
        if any(not isinstance(document_id, str) or not document_id.startswith("DOC-") for document_id in parsed_ids):
            raise ValueError("document_id KA invalide")
        if len(parsed_ids) == 0:
            return {}
        with self._connection_factory.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT ON (document_id)
                           document_id, status, bibliographic_metadata_status,
                           bibliographic_title, bibliographic_authors,
                           bibliographic_publication_year, bibliographic_edition
                      FROM knowledge_access.knowledge_projections
                     WHERE document_id = ANY(%s)
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                     ORDER BY document_id, state_observed_at DESC, projection_id DESC
                    """,
                    (
                        list(parsed_ids),
                        self._identity.environment,
                        self._identity.deployment_id,
                        self._identity.configuration_hash,
                    ),
                )
                rows = cursor.fetchall()
        return {
            str(row[0]): ProjectionCatalogRecord(
                document_id=str(row[0]),
                projection_status=str(row[1]),
                metadata_status=str(row[2]),
                title=row[3],
                authors=None if row[4] is None else tuple(row[4]),
                publication_year=row[5],
                edition=row[6],
            )
            for row in rows
        }

    def current_projection_for_document_id(
        self,
        document_id: str,
        sample_limit: int,
    ) -> ProjectionReadRecord | None:
        if not isinstance(document_id, str) or not document_id.startswith("DOC-"):
            raise ValueError("document_id invalide")
        if isinstance(sample_limit, bool) or not isinstance(sample_limit, int) or sample_limit < 1:
            raise ValueError("sample_limit invalide")

        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                    (),
                )
                cursor.execute(
                    """
                    SELECT projection_id, document_id, canonical_version_id,
                           projection_profile_id, chunking_profile, embedding_model,
                           sparse_profile, index_schema, build_fingerprint, status,
                           aggregate_version, chunk_count, state_observed_at
                      FROM knowledge_access.knowledge_projections
                     WHERE document_id = %s
                       AND environment = %s
                       AND deployment_id = %s
                       AND configuration_hash = %s
                     ORDER BY state_observed_at DESC, projection_id DESC
                     LIMIT 1
                    """,
                    (
                        document_id,
                        self._identity.environment,
                        self._identity.deployment_id,
                        self._identity.configuration_hash,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """
                    SELECT chunk_level, chunk_text, content_hash, source_locators,
                           chunk_id, parent_chunk_id, profile_id, profile_version
                      FROM knowledge_access.knowledge_projection_chunk_samples
                     WHERE projection_id = %s
                     ORDER BY sample_ordinal
                     LIMIT %s
                    """,
                    (row[0], sample_limit),
                )
                sample_rows = tuple(cursor.fetchall())
        return _projection_record_from_rows(row, sample_rows)


def _projection_record_from_rows(
    row: Any,
    sample_rows: Sequence[Any],
) -> ProjectionReadRecord:
    observed_at = row[12]
    if not callable(getattr(observed_at, "isoformat", None)):
        raise ValueError("state_observed_at PostgreSQL invalide")
    observed_at_text = observed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    projection = _projection_from_row(row)

    return ProjectionReadRecord(
        projection=projection,
        chunk_count=row[11],
        chunk_samples=tuple(
            _chunk_from_row(sample_row, projection=projection)
            for sample_row in sample_rows
        ),
        state_observed_at=observed_at_text,
    )


def _projection_from_row(row: Any) -> KnowledgeProjection:
    return KnowledgeProjection(
        projection_id=row[0],
        document_id=row[1],
        canonical_version_id=row[2],
        projection_profile=ProjectionProfile(
            projection_profile_id=row[3],
            chunking_profile=row[4],
            embedding_model=row[5],
            sparse_profile=row[6],
            index_schema=row[7],
        ),
        build_fingerprint=BuildFingerprint(row[8]),
        status=ProjectionStatus.from_value(row[9]),
        aggregate_version=row[10],
    )


def _projection_parameters(
    projection: KnowledgeProjection,
    profile: ProjectionProfile,
) -> tuple[object, ...]:
    return (
        projection.projection_id,
        projection.document_id,
        projection.canonical_version_id,
        profile.projection_profile_id,
        profile.chunking_profile,
        profile.embedding_model,
        profile.sparse_profile,
        profile.index_schema,
        projection.build_fingerprint.value,
        projection.status.value,
    )


def _chunk_from_row(row: Any, *, projection: KnowledgeProjection) -> KnowledgeChunk:
    raw_locators = row[3]
    if isinstance(raw_locators, str):
        raw_locators = json.loads(raw_locators)
    if not isinstance(raw_locators, list) or len(raw_locators) == 0:
        raise ValueError("SourceLocator PostgreSQL absent")
    locators = tuple(_source_locator_from_payload(item) for item in raw_locators)
    return KnowledgeChunk(
        chunk_id=row[4],
        chunk_level=row[0],
        parent_chunk_id=row[5],
        canonical_version_id=projection.canonical_version_id,
        document_id=projection.document_id,
        profile_id=row[6],
        profile_version=row[7],
        text=row[1],
        pages=tuple(dict.fromkeys(locator.page_pdf for locator in locators)),
        item_ids=tuple(locator.item_id for locator in locators),
        source_locators=locators,
        content_hash=row[2],
    )


def _source_locator_from_payload(value: Any) -> SourceLocator:
    if not isinstance(value, Mapping):
        raise ValueError("SourceLocator PostgreSQL invalide")
    expected = {
        "schema_version",
        "canonical_version_id",
        "document_id",
        "page_pdf",
        "item_id",
        "bbox",
        "content_hash",
    }
    if set(value) != expected:
        raise ValueError("champs SourceLocator PostgreSQL invalides")
    bbox = value["bbox"]
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError("bbox PostgreSQL invalide")
    return SourceLocator(
        schema_version=value["schema_version"],
        canonical_version_id=value["canonical_version_id"],
        document_id=value["document_id"],
        page_pdf=value["page_pdf"],
        item_id=value["item_id"],
        bbox=tuple(bbox),
        content_hash=value["content_hash"],
    )


def _ensure_chunks(
    value: Sequence[KnowledgeChunk],
    *,
    projection: KnowledgeProjection,
) -> tuple[KnowledgeChunk, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError("échantillons KA invalides")
    chunks = tuple(value)
    for chunk in chunks:
        if not isinstance(chunk, KnowledgeChunk):
            raise ValueError("chunk KA invalide")
        if (
            chunk.document_id != projection.document_id
            or chunk.canonical_version_id != projection.canonical_version_id
        ):
            raise ValueError("chunk KA incohérent avec la projection")
    return chunks


def _outputs_fingerprint(
    *,
    projection: KnowledgeProjection,
    chunk_count: int,
    samples: tuple[KnowledgeChunk, ...],
    state_observed_at: str,
    index_generation: str | None,
) -> str:
    payload = {
        "aggregate_version": projection.aggregate_version,
        "build_fingerprint": projection.build_fingerprint.value,
        "chunk_count": chunk_count,
        "index_generation": index_generation,
        "profile": projection.projection_profile.to_fingerprint_payload(),
        "projection_id": projection.projection_id,
        "samples": [
            {
                "chunk_id": sample.chunk_id,
                "chunk_level": sample.chunk_level,
                "content_hash": sample.content_hash,
                "parent_chunk_id": sample.parent_chunk_id,
                "profile_id": sample.profile_id,
                "profile_version": sample.profile_version,
                "source_locators": [locator.to_payload() for locator in sample.source_locators],
                "text": sample.text,
            }
            for sample in samples
        ],
        "state_observed_at": state_observed_at,
        "status": projection.status.value,
    }
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256(serialized.encode("utf-8")).hexdigest()


def _ensure_projection(value: KnowledgeProjection) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("KnowledgeProjection invalide")
    return value


def _ensure_build_fingerprint(value: BuildFingerprint) -> BuildFingerprint:
    if not isinstance(value, BuildFingerprint):
        raise ValueError("build_fingerprint invalide")
    return value


__all__ = [
    "KnowledgeProjectionReplayConflictError",
    "KnowledgeProjectionVersionConflictError",
    "PostgresKnowledgeProjectionRepository",
    "PostgresProjectionReadRepository",
]
