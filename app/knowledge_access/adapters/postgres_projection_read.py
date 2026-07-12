"""Lecture PostgreSQL de la source de vérité des projections KA."""

from __future__ import annotations

from typing import Any

from app.knowledge_access.application.projection_queries import ProjectionReadRecord
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.platform.postgres import PostgresConnectionFactory


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
            with connection.cursor() as cursor:
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
        return _projection_record_from_row(row)


def _projection_record_from_row(row: Any) -> ProjectionReadRecord:
    observed_at = row[11]
    if not callable(getattr(observed_at, "isoformat", None)):
        raise ValueError("state_observed_at PostgreSQL invalide")
    observed_at_text = observed_at.isoformat().replace("+00:00", "Z")
    return ProjectionReadRecord(
        projection=KnowledgeProjection(
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
        ),
        chunk_count=row[10],
        chunk_samples=(),
        state_observed_at=observed_at_text,
    )


__all__ = ["PostgresProjectionReadRepository"]
