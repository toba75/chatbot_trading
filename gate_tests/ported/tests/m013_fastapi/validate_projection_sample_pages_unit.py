from __future__ import annotations

import hashlib

from app.contracts.source_references import SourceLocator
from app.knowledge_access.adapters.postgres_projection_read import _chunk_from_row
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)


def test_given_two_source_locators_on_one_page_when_a_projection_sample_is_read_then_pages_are_deduplicated() -> None:
    """Given-When-Then : la lecture KA préserve l'invariant public du chunk."""

    document_id = "DOC-M013-PROJECTION-SAMPLE"
    canonical_version_id = "CVER-M013-PROJECTION-SAMPLE"
    projection = KnowledgeProjection(
        projection_id="PROJ-M013-PROJECTION-SAMPLE",
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
    text = "Deux éléments canoniques sur la même page."
    row = (
        "PARENT",
        text,
        hashlib.sha256(text.encode()).hexdigest(),
        [
            _source_locator_payload(
                document_id=document_id,
                canonical_version_id=canonical_version_id,
                item_id="item-1",
            ),
            _source_locator_payload(
                document_id=document_id,
                canonical_version_id=canonical_version_id,
                item_id="item-2",
            ),
        ],
        "KCHK-0123456789ABCDEF0123456789ABCDEF",
        None,
        "hierarchical-pagewise-v1",
        "hierarchical-v1",
    )

    sample = _chunk_from_row(row, projection=projection)

    assert sample.pages == (3,)
    assert tuple(locator.item_id for locator in sample.source_locators) == ("item-1", "item-2")


def _source_locator_payload(
    *,
    document_id: str,
    canonical_version_id: str,
    item_id: str,
) -> dict[str, object]:
    item_hash = hashlib.sha256(item_id.encode()).hexdigest()
    locator = SourceLocator(
        schema_version="1.0",
        canonical_version_id=canonical_version_id,
        document_id=document_id,
        page_pdf=3,
        item_id=item_id,
        bbox=(0.0, 0.0, 10.0, 10.0),
        content_hash=item_hash,
    )
    return locator.to_payload()
