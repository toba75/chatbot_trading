from __future__ import annotations

from pathlib import Path
import sys


def test_validate_documentary_projection_retrieval_unit() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.knowledge_access.adapters.live_documentary_retrieval import (
        DocumentaryChunk,
        DocumentaryProjectionRetriever,
        SearchableProjection,
    )

    class ProjectionReader:
        def find_searchable_projection(self, document_id: str) -> SearchableProjection:
            assert document_id == "DOC-M013-RETRIEVAL-001"
            return SearchableProjection(
                document_id=document_id,
                projection_id="PROJ-M013-RETRIEVAL-001",
                canonical_version_id="CVER-M013-RETRIEVAL-001",
            )

    class CanonicalReader:
        def chunks_for_canonical_version(self, canonical_version_id: str):
            assert canonical_version_id == "CVER-M013-RETRIEVAL-001"
            return (
                DocumentaryChunk(
                    chunk_id="KCHK-M013-RETRIEVAL-001-A",
                    chunk_level="PARENT",
                    text="Vue d'ensemble du document.",
                    source_locators=(
                        {
                            "schema_version": "1.0",
                            "canonical_version_id": canonical_version_id,
                            "document_id": "DOC-M013-RETRIEVAL-001",
                            "page_pdf": 4,
                            "item_id": "ITEM-M013-RETRIEVAL-001-A",
                            "bbox": (0.1, 0.2, 0.3, 0.4),
                            "content_hash": "a" * 64,
                        },
                    ),
                ),
                DocumentaryChunk(
                    chunk_id="KCHK-M013-RETRIEVAL-001-B",
                    chunk_level="CHILD",
                    text="Le momentum suit la persistance de la tendance.",
                    source_locators=(
                        {
                            "schema_version": "1.0",
                            "canonical_version_id": canonical_version_id,
                            "document_id": "DOC-M013-RETRIEVAL-001",
                            "page_pdf": 5,
                            "item_id": "ITEM-M013-RETRIEVAL-001-B1",
                            "bbox": (0.1, 0.2, 0.3, 0.4),
                            "content_hash": "b" * 64,
                        },
                        {
                            "schema_version": "1.0",
                            "canonical_version_id": canonical_version_id,
                            "document_id": "DOC-M013-RETRIEVAL-001",
                            "page_pdf": 6,
                            "item_id": "ITEM-M013-RETRIEVAL-001-B2",
                            "bbox": (0.1, 0.2, 0.3, 0.4),
                            "content_hash": "c" * 64,
                        },
                    ),
                ),
            )

    class Selector:
        def select_chunk_ids(self, *, projection_id: str, question: str, limit: int):
            assert projection_id == "PROJ-M013-RETRIEVAL-001"
            assert question == "Explique le momentum."
            assert limit == 32
            return (
                "KCHK-M013-RETRIEVAL-001-A",
                "KCHK-M013-RETRIEVAL-001-B",
            )

    retriever = DocumentaryProjectionRetriever(
        projection_reader=ProjectionReader(),
        canonical_reader=CanonicalReader(),
        chunk_selector=Selector(),
        result_limit=4,
    )

    # Given une projection KA réellement SEARCHABLE et des chunks canoniques.
    # When RA demande les extraits d'un document explicitement sélectionné.
    # Then KA utilise les identifiants produits par l'index, résout chaque
    # chunk vers la source canonique et ne mélange jamais un autre document.
    evidence = retriever.retrieve(
        question="Explique le momentum.",
        selected_document_ids=("DOC-M013-RETRIEVAL-001",),
    )
    assert len(evidence) == 1
    assert evidence[0].excerpt.startswith("Le momentum")
    assert tuple(locator["page_pdf"] for locator in evidence[0].source_locators) == (5, 6)
