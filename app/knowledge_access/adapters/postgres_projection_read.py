"""Persistance et lecture PostgreSQL de la source de vérité des projections KA."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.contracts.source_references import SourceLocator
from app.knowledge_access.application.projection_queries import ProjectionReadRecord
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
                        chunk_count, state_observed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP)
                    ON CONFLICT (build_fingerprint) DO NOTHING
                    RETURNING projection_id
                    """,
                    _projection_parameters(parsed_projection, profile),
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
                           state_observed_at = CURRENT_TIMESTAMP
                     WHERE projection_id = %s
                       AND build_fingerprint = %s
                    RETURNING projection_id
                    """,
                    (
                        parsed_projection.status.value,
                        parsed_projection.projection_id,
                        parsed_projection.build_fingerprint.value,
                    ),
                )
                updated = cursor.fetchone()
        if updated is None:
            raise ValueError(
                f"projection inconnue ou empreinte incohérente: {parsed_projection.projection_id}"
            )
        return parsed_projection

    def save_projection_outputs(
        self,
        *,
        projection: KnowledgeProjection,
        chunk_count: int,
        chunks: Sequence[KnowledgeChunk],
        state_observed_at: str,
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
        profile = projection.projection_profile
        with self._connection_factory.connect() as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO knowledge_access.knowledge_projections (
                        projection_id, document_id, canonical_version_id,
                        projection_profile_id, chunking_profile, embedding_model,
                        sparse_profile, index_schema, build_fingerprint, status,
                        chunk_count, state_observed_at
                    )

                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (projection_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        chunk_count = EXCLUDED.chunk_count,
                        state_observed_at = EXCLUDED.state_observed_at
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
                           sparse_profile, index_schema, build_fingerprint, status
                      FROM knowledge_access.knowledge_projections
                     WHERE {predicate}
                    """,
                    parameters,
                )
                row = cursor.fetchone()
        return None if row is None else _projection_from_row(row)


class PostgresProjectionReadRepository:
    """Lit l'agrégat KA courant sans déduire son état depuis Qdrant."""

    def __init__(self, *, connection_factory: PostgresConnectionFactory) -> None:
        if not callable(getattr(connection_factory, "connect", None)):
            raise ValueError("connection_factory invalide")
        self._connection_factory = connection_factory

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
                           chunk_count, state_observed_at
                      FROM knowledge_access.knowledge_projections
                     WHERE document_id = %s
                     ORDER BY state_observed_at DESC, projection_id DESC
                     LIMIT 1
                    """,
                    (document_id,),
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
    observed_at = row[11]
    if not callable(getattr(observed_at, "isoformat", None)):
        raise ValueError("state_observed_at PostgreSQL invalide")
    observed_at_text = observed_at.isoformat().replace("+00:00", "Z")
    projection = _projection_from_row(row)

    return ProjectionReadRecord(
        projection=projection,
        chunk_count=row[10],
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
        pages=tuple(locator.page_pdf for locator in locators),
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


def _ensure_projection(value: KnowledgeProjection) -> KnowledgeProjection:
    if not isinstance(value, KnowledgeProjection):
        raise ValueError("KnowledgeProjection invalide")
    return value


def _ensure_build_fingerprint(value: BuildFingerprint) -> BuildFingerprint:
    if not isinstance(value, BuildFingerprint):
        raise ValueError("build_fingerprint invalide")
    return value


__all__ = [
    "PostgresKnowledgeProjectionRepository",
    "PostgresProjectionReadRepository",
]
