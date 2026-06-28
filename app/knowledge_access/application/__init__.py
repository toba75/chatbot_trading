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
from app.knowledge_access.application.search_knowledge import (
    KnowledgeSearchPort,
    SearchIndexUnavailableError,
    SearchKnowledge,
    SearchProfileUnsupportedError,
    SearchProjectionStaleError,
    SearchProjectionUnavailableError,
    SearchTracePersistenceError,
)
from app.knowledge_access.application.traceability_metrics import (
    EvaluationQuestion,
    EvaluationResult,
    InitialSearchMetricSnapshot,
    InitialSearchMetricsPublisher,
    KnowledgeSearchAuditSignal,
    SearchEvaluationCorpus,
    assert_no_full_passage_in_audit_payload,
)

__all__ = [
    "CanonicalSourceForProjection",
    "CanonicalSourcePublishedProjectionConsumer",
    "ChunkingSourceNotFoundError",
    "EvaluationQuestion",
    "EvaluationResult",
    "InitialSearchMetricSnapshot",
    "InitialSearchMetricsPublisher",
    "KnowledgeSearchAuditSignal",
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
    "KnowledgeSearchPort",
    "SearchIndexUnavailableError",
    "SearchKnowledge",
    "SearchProfileUnsupportedError",
    "SearchProjectionStaleError",
    "SearchProjectionUnavailableError",
    "SearchEvaluationCorpus",
    "SearchTracePersistenceError",
    "append_projection_events_to_outbox",
    "assert_no_full_passage_in_audit_payload",
]
