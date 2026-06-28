"""Couche adaptateurs du contexte KA."""
"""Adaptateurs KA."""

from app.knowledge_access.adapters.in_memory_projection_repository import (
    InMemoryKnowledgeProjectionRepository,
    InMemoryProjectionEventRegistry,
)
from app.knowledge_access.adapters.projection_http import (
    HttpRequest,
    HttpResponse,
    KnowledgeProjectionHttpAdapter,
)
from app.knowledge_access.adapters.in_memory_vector_index import InMemoryVectorIndex

__all__ = [
    "HttpRequest",
    "HttpResponse",
    "InMemoryKnowledgeProjectionRepository",
    "InMemoryProjectionEventRegistry",
    "InMemoryVectorIndex",
    "KnowledgeProjectionHttpAdapter",
]
