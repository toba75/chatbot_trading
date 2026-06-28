"""Domaine KA."""

from app.knowledge_access.domain.chunking import (
    CanonicalChunkDocument,
    CanonicalChunkItem,
    ChunkingProfile,
    HierarchicalChunkProjection,
    HierarchicalChunkProjector,
    KnowledgeChunk,
)
from app.knowledge_access.domain.knowledge_projection import (
    BuildFingerprint,
    KnowledgeProjection,
    ProjectionProfile,
    ProjectionStatus,
)
from app.knowledge_access.domain.projection_metadata import (
    AppliedFilterTrace,
    DiversificationTrace,
    EvidenceDiversificationPolicy,
    ProjectionFilterTrace,
    ProjectionFreshnessDecision,
    ProjectionFreshnessPolicy,
    ProjectionMetadata,
    ProjectionMetadataSelection,
    ProjectionMetadataSelector,
    SearchFilter,
)
from app.knowledge_access.domain.projection_index import (
    PartialVectorIndexError,
    VectorIndexDeletion,
    VectorIndexPoint,
    VectorIndexPublication,
    VectorIndexPublishRequest,
    VectorIndexSchema,
    VectorIndexUnavailableError,
    index_generation_for,
)

__all__ = [
    "AppliedFilterTrace",
    "BuildFingerprint",
    "CanonicalChunkDocument",
    "CanonicalChunkItem",
    "ChunkingProfile",
    "DiversificationTrace",
    "EvidenceDiversificationPolicy",
    "HierarchicalChunkProjection",
    "HierarchicalChunkProjector",
    "KnowledgeChunk",
    "KnowledgeProjection",
    "PartialVectorIndexError",
    "ProjectionFilterTrace",
    "ProjectionFreshnessDecision",
    "ProjectionFreshnessPolicy",
    "ProjectionMetadata",
    "ProjectionMetadataSelection",
    "ProjectionMetadataSelector",
    "ProjectionProfile",
    "ProjectionStatus",
    "SearchFilter",
    "VectorIndexDeletion",
    "VectorIndexPoint",
    "VectorIndexPublication",
    "VectorIndexPublishRequest",
    "VectorIndexSchema",
    "VectorIndexUnavailableError",
    "index_generation_for",
]
