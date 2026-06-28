"""Adaptateurs KA."""

from app.knowledge_access.adapters.in_memory_projection_repository import (
    InMemoryKnowledgeProjectionRepository,
    InMemoryProjectionEventRegistry,
)
from app.knowledge_access.adapters.in_memory_hybrid_search import (
    InMemoryHybridRetrievalIndex,
    InMemoryReranker,
    InMemorySearchTraceStore,
)
from app.knowledge_access.adapters.in_memory_vector_index import InMemoryVectorIndex
from app.knowledge_access.adapters.projection_http import (
    HttpRequest,
    HttpResponse,
    KnowledgeProjectionHttpAdapter,
)
from app.knowledge_access.adapters.search_http import (
    KnowledgeSearchHttpAdapter,
    SearchRequestDto,
    SearchResponseDto,
)

__all__ = [
    "HttpRequest",
    "HttpResponse",
    "InMemoryHybridRetrievalIndex",
    "InMemoryKnowledgeProjectionRepository",
    "InMemoryProjectionEventRegistry",
    "InMemoryReranker",
    "InMemorySearchTraceStore",
    "InMemoryVectorIndex",
    "KnowledgeProjectionHttpAdapter",
    "KnowledgeSearchHttpAdapter",
    "SearchRequestDto",
    "SearchResponseDto",
]
