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

__all__ = [
    "BuildFingerprint",
    "CanonicalChunkDocument",
    "CanonicalChunkItem",
    "ChunkingProfile",
    "HierarchicalChunkProjection",
    "HierarchicalChunkProjector",
    "KnowledgeChunk",
    "KnowledgeProjection",
    "ProjectionProfile",
    "ProjectionStatus",
]
