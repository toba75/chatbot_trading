from __future__ import annotations

import hashlib
import inspect
from datetime import datetime, timezone

from app.contracts.source_references import SourceLocator
from app.knowledge_access.adapters.postgres_projection_read import (
    PostgresKnowledgeProjectionRepository,
    PostgresProjectionReadRepository,
)
from app.knowledge_access.domain.chunking import KnowledgeChunk
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)


class _Cursor:
    def __init__(self, projection_row: object = None, sample_rows: object = ()) -> None:
        self.projection_row = projection_row
        self.sample_rows = sample_rows
        self.calls: list[tuple[str, object]] = []
        self.current: str | None = None

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_arguments: object) -> bool:
        return False

    def execute(self, sql: str, parameters: object = ()) -> None:
        normalized = " ".join(sql.split())
        self.calls.append((normalized, parameters))
        if "SELECT projection_id" in normalized:
            self.current = "projection"
        elif "SELECT chunk_level" in normalized:
            self.current = "samples"
        elif "SELECT aggregate_version" in normalized:
            self.current = "writer-version"

    def fetchone(self) -> object:
        if self.current == "projection":
            return self.projection_row
        return None

    def fetchall(self) -> object:
        if self.current == "samples":
            return self.sample_rows
        return ()


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_arguments: object) -> bool:
        return False

    def cursor(self) -> _Cursor:
        return self._cursor

    def transaction(self) -> "_Connection":
        return self


class _Factory:
    def __init__(self, cursors: list[_Cursor]) -> None:
        self.cursors = cursors

    def connect(self) -> _Connection:
        return _Connection(self.cursors.pop(0))


DOCUMENT_ID = "DOC-M013-KA-PERSIST"
CANONICAL_VERSION_ID = "CVER-M013-KA-PERSIST"
PROFILE = ProjectionProfile(
    projection_profile_id="projection-publique-v1",
    chunking_profile="hierarchical-v1",
    embedding_model="dense-v1",
    sparse_profile="sparse-v1",
    index_schema="hybrid-v1",
)
PROJECTION = KnowledgeProjection(
    projection_id="PROJ-M013-KA-PERSIST",
    document_id=DOCUMENT_ID,
    canonical_version_id=CANONICAL_VERSION_ID,
    projection_profile=PROFILE,
    build_fingerprint=BuildFingerprint(
        hashlib.sha256(DOCUMENT_ID.encode()).hexdigest()
    ),
    status=ProjectionStatus.BUILDING,
)


def _chunk(number: int) -> KnowledgeChunk:
    text = f"Extrait persistant {number}"
    locator = SourceLocator(
        schema_version="1.0",
        canonical_version_id=CANONICAL_VERSION_ID,
        document_id=DOCUMENT_ID,
        page_pdf=number,
        item_id=f"item-{number}",
        bbox=(0.0, 0.0, 10.0, 10.0),
        content_hash=hashlib.sha256(f"item-{number}".encode()).hexdigest(),
    )
    return KnowledgeChunk.parent(
        chunk_id=f"KCHK-{hashlib.sha256(text.encode()).hexdigest()[:32].upper()}",
        canonical_version_id=CANONICAL_VERSION_ID,
        document_id=DOCUMENT_ID,
        profile_id="hierarchical",
        profile_version="1",
        text=text,
        source_locators=(locator,),
    )


def test_validate_ka_projection_persistence_unit() -> None:
    writer_cursor = _Cursor()
    writer = PostgresKnowledgeProjectionRepository(
        connection_factory=_Factory([writer_cursor]),
        sample_storage_limit=3,
    )
    index_parameter = inspect.signature(writer.save_projection_outputs).parameters[
        "index_generation"
    ]
    assert index_parameter.default is inspect.Parameter.empty
    writer.save_projection_outputs(
        projection=PROJECTION,
        chunk_count=3,
        chunks=(_chunk(1), _chunk(2), _chunk(3)),
        state_observed_at="2026-07-12T10:00:00Z",
        index_generation=None,
    )
    assert any(
        "knowledge_projection_chunk_samples" in sql
        for sql, _parameters in writer_cursor.calls
    )

    projection_row = (
        PROJECTION.projection_id,
        DOCUMENT_ID,
        CANONICAL_VERSION_ID,
        PROFILE.projection_profile_id,
        PROFILE.chunking_profile,
        PROFILE.embedding_model,
        PROFILE.sparse_profile,
        PROFILE.index_schema,
        PROJECTION.build_fingerprint.value,
        "BUILDING",
        PROJECTION.aggregate_version,
        3,
        datetime(2026, 7, 12, 10, tzinfo=timezone.utc),
    )
    sample_rows = tuple(
        (
            sample.chunk_level,
            sample.text,
            sample.content_hash,
            [locator.to_payload() for locator in sample.source_locators],
            sample.chunk_id,
            sample.parent_chunk_id,
            sample.profile_id,
            sample.profile_version,
        )
        for sample in (_chunk(1), _chunk(2))
    )
    reader_cursor = _Cursor(projection_row, sample_rows)
    reader = PostgresProjectionReadRepository(
        connection_factory=_Factory([reader_cursor])
    )
    record = reader.current_projection_for_document_id(DOCUMENT_ID, sample_limit=2)
    assert record is not None
    assert record.chunk_count == 3
    assert len(record.chunk_samples) == 2
    assert record.chunk_samples[0].source_locators[0].page_pdf == 1
