"""Couche domaine du contexte EG."""

from app.evidence_governance.domain.claim_evidence import (
    CanonicalEvidenceSpan,
    Claim,
    ClaimStatus,
    EvidenceAdmissibilityPolicy,
    EvidenceAssociation,
    EvidenceAttachedToClaim,
)
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimAtomicityPolicy,
    ClaimCanonicalizationPolicy,
    ClaimCondition,
    ClaimDrafted,
    ClaimExtractionProposal,
    ClaimScope,
    DraftClaim,
    DraftClaimStatus,
    EvidenceSpan,
    Limitation,
    claim_id_for,
)
from app.evidence_governance.domain.claim_relation import (
    ClaimRelation,
    ClaimRelationPolicy,
    ClaimRelationPolicyDecision,
    ClaimRelationRecorded,
    ClaimRelationType,
    ClaimVersionRef,
    ScopeCompatibility,
    ScopeCompatibilityStatus,
)


__all__ = [
    "CanonicalEvidenceSpan",
    "CanonicalProposition",
    "Claim",
    "ClaimAtomicityPolicy",
    "ClaimCanonicalizationPolicy",
    "ClaimCondition",
    "ClaimDrafted",
    "ClaimExtractionProposal",
    "ClaimRelation",
    "ClaimRelationPolicy",
    "ClaimRelationPolicyDecision",
    "ClaimRelationRecorded",
    "ClaimRelationType",
    "ClaimScope",
    "ClaimStatus",
    "ClaimVersionRef",
    "DraftClaim",
    "DraftClaimStatus",
    "EvidenceAdmissibilityPolicy",
    "EvidenceAssociation",
    "EvidenceAttachedToClaim",
    "EvidenceSpan",
    "Limitation",
    "ScopeCompatibility",
    "ScopeCompatibilityStatus",
    "claim_id_for",
]
