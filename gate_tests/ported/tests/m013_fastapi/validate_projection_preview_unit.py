from __future__ import annotations

import hashlib

from app.contracts.source_references import SourceLocator
from app.knowledge_access.application.projection_queries import (
    ProjectionQueryService,
    ProjectionReadRecord,
)
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)


class _ProjectionReadRepository:
    def __init__(self, record: ProjectionReadRecord) -> None:
        self._record = record

    def current_projection_for_document_id(
        self,
        document_id: str,
        sample_limit: int,
    ) -> ProjectionReadRecord | None:
        if document_id != self._record.projection.document_id:
            return None
        return self._record


def test_given_a_chunk_cut_after_whitespace_when_the_public_preview_is_built_then_it_remains_a_valid_non_empty_value() -> None:
    """Given-When-Then : le bornage d'un aperçu n'invalide pas le read-model."""

    document_id = "DOC-M013-PREVIEW"
    canonical_version_id = "CVER-M013-PREVIEW"
    projection = KnowledgeProjection(
        projection_id="PROJ-M013-PREVIEW",
        document_id=document_id,
        canonical_version_id=canonical_version_id,
        projection_profile=ProjectionProfile(
            projection_profile_id="projection-publique-v1",
            chunking_profile="hierarchical-v1",
            embedding_model="dense-v1",
            sparse_profile="sparse-v1",
            index_schema="hybrid-v1",
        ),
        build_fingerprint=BuildFingerprint(hashlib.sha256(document_id.encode()).hexdigest()),
        status=ProjectionStatus.SEARCHABLE,
    )
    locator = SourceLocator(
        schema_version="1.0",
        canonical_version_id=canonical_version_id,
        document_id=document_id,
        page_pdf=1,
        item_id="item-1",
        bbox=(0.0, 0.0, 1.0, 1.0),
        content_hash=hashlib.sha256(b"item-1").hexdigest(),
    )
    chunk = KnowledgeChunk.parent(
        chunk_id="KCHK-0123456789ABCDEF0123456789ABCDEF",
        canonical_version_id=canonical_version_id,
        document_id=document_id,
        profile_id="hierarchical-pagewise-v1",
        profile_version="hierarchical-v1",
        text="Texte   final",
        source_locators=(locator,),
    )
    service = ProjectionQueryService(
        projection_read_repository=_ProjectionReadRepository(
            ProjectionReadRecord(
                projection=projection,
                chunk_count=1,
                chunk_samples=(chunk,),
                state_observed_at="2026-07-14T22:40:00Z",
            )
        ),
        chunk_sample_limit=1,
        text_preview_character_limit=6,
        source_locator_limit=1,
    )

    view = service.read_projection(document_id)

    assert view.chunk_samples[0].text_preview == "Texte"
    assert view.chunk_samples[0].text_preview_truncated is True
