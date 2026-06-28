"""Couche application du contexte KA."""
"""Application KA."""

from app.knowledge_access.application.chunk_canonical_source import (
    ChunkingSourceNotFoundError,
    ProjectCanonicalChunksCommand,
    ProjectCanonicalChunksHandler,
)
from app.knowledge_access.application.request_projection import (
    CanonicalSourceForProjection,
    CanonicalSourcePublishedProjectionConsumer,
    ProjectionEligibilityPolicy,
    RequestKnowledgeProjectionCommand,
    RequestKnowledgeProjectionHandler,
)
from app.knowledge_access.application.projection_events import (
    KnowledgeProjectionEventFactory,
    append_projection_events_to_outbox,
)
from app.knowledge_access.application.publish_projection_index import (
    MarkProjectionStaleCommand,
    ProjectionLifecycleResult,
    PublishProjectionIndexCommand,
    PublishProjectionIndexHandler,
    PublishProjectionIndexResult,
    RetireProjectionIndexCommand,
)

__all__ = [
    "CanonicalSourceForProjection",
    "CanonicalSourcePublishedProjectionConsumer",
    "ChunkingSourceNotFoundError",
    "KnowledgeProjectionEventFactory",
    "MarkProjectionStaleCommand",
    "ProjectionLifecycleResult",
    "ProjectionEligibilityPolicy",
    "ProjectCanonicalChunksCommand",
    "ProjectCanonicalChunksHandler",
    "PublishProjectionIndexCommand",
    "PublishProjectionIndexHandler",
    "PublishProjectionIndexResult",
    "RequestKnowledgeProjectionCommand",
    "RequestKnowledgeProjectionHandler",
    "RetireProjectionIndexCommand",
    "append_projection_events_to_outbox",
]
