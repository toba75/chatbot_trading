"""Couche application du contexte EG."""

from app.evidence_governance.application.attach_evidence import (
    AttachEvidenceToClaimCommand,
    AttachEvidenceToClaimHandler,
    AttachEvidenceToClaimResult,
    CanonicalEvidenceReader,
    ClaimRepository,
)
from app.evidence_governance.application.extract_claims import (
    ClaimDraftRepository,
    ClaimExtractionResult,
    ClaimExtractor,
    ExtractClaimsFromEvidenceCommand,
    ExtractClaimsFromEvidenceHandler,
)
from app.evidence_governance.application.relate_claims import (
    ClaimRelationRepository,
    RelateClaims,
    RelateClaimsHandler,
    RelateClaimsResult,
)


__all__ = [
    "AttachEvidenceToClaimCommand",
    "AttachEvidenceToClaimHandler",
    "AttachEvidenceToClaimResult",
    "CanonicalEvidenceReader",
    "ClaimDraftRepository",
    "ClaimExtractionResult",
    "ClaimExtractor",
    "ClaimRepository",
    "ClaimRelationRepository",
    "ExtractClaimsFromEvidenceCommand",
    "ExtractClaimsFromEvidenceHandler",
    "RelateClaims",
    "RelateClaimsHandler",
    "RelateClaimsResult",
]
