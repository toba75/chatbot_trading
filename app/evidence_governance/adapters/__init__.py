"""Couche adaptateurs du contexte EG."""

from app.evidence_governance.adapters.claim_http import (
    ClaimExtractionRequestDto,
    ClaimHttpAdapter,
    ClaimHttpRequestValidationError,
    ClaimVerificationRequestDto,
    HttpRequest,
    HttpResponse,
)
from app.evidence_governance.adapters.deterministic_claim_extractor import (
    DeterministicClaimExtractor,
)
from app.evidence_governance.adapters.in_memory_canonical_evidence_reader import (
    InMemoryCanonicalEvidenceReader,
)
from app.evidence_governance.adapters.in_memory_claim_draft_repository import (
    InMemoryClaimDraftRepository,
)
from app.evidence_governance.adapters.in_memory_claim_repository import (
    InMemoryClaimRepository,
)
from app.evidence_governance.adapters.in_memory_claim_relation_repository import (
    InMemoryClaimRelationRepository,
)


__all__ = [
    "ClaimExtractionRequestDto",
    "ClaimHttpAdapter",
    "ClaimHttpRequestValidationError",
    "ClaimVerificationRequestDto",
    "DeterministicClaimExtractor",
    "HttpRequest",
    "HttpResponse",
    "InMemoryCanonicalEvidenceReader",
    "InMemoryClaimDraftRepository",
    "InMemoryClaimRepository",
    "InMemoryClaimRelationRepository",
]
