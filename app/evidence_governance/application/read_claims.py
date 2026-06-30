"""Cas d'usage EG de lecture publique des claims et preuves."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.evidence_claims import EvidenceRef
from app.contracts.source_references import SourceLocator
from app.evidence_governance.domain.claim_evidence import (
    CanonicalEvidenceSpan,
    Claim,
    ClaimStatus,
)


_PUBLIC_CLAIM_STATUSES = frozenset(
    {
        ClaimStatus.VERIFIED,
        ClaimStatus.REJECTED,
        ClaimStatus.SUPERSEDED,
    }
)


class ClaimReaderPort(Protocol):
    """Port de lecture publique de claims EG."""

    def read_claim(self, claim_id: str) -> Claim:
        """Retourne le claim consultable par identifiant."""


class CanonicalEvidenceReaderPort(Protocol):
    """Port de résolution publique des preuves EG."""

    def resolve(self, source_locator: SourceLocator) -> CanonicalEvidenceSpan:
        """Retourne le span canonique associé au SourceLocator."""


@dataclass(frozen=True)
class ReadPublicClaimResult:
    """Résultat applicatif de lecture publique d'un claim."""

    claim: Claim

    def __post_init__(self) -> None:
        if not isinstance(self.claim, Claim):
            raise ValueError("claim invalide")


@dataclass(frozen=True)
class ReadClaimEvidenceResult:
    """Résultat applicatif de lecture des preuves publiques d'un claim."""

    claim: Claim
    evidence_refs: Sequence[EvidenceRef]
    dependency_group_ids: Sequence[str]
    verification_case_ids: Sequence[str]

    def __post_init__(self) -> None:
        if not isinstance(self.claim, Claim):
            raise ValueError("claim invalide")
        object.__setattr__(self, "evidence_refs", _ensure_evidence_refs(self.evidence_refs))
        object.__setattr__(
            self,
            "dependency_group_ids",
            _ensure_text_tuple(self.dependency_group_ids, "dependency_group_ids"),
        )
        object.__setattr__(
            self,
            "verification_case_ids",
            _ensure_text_tuple(self.verification_case_ids, "verification_case_ids"),
        )


@dataclass(frozen=True)
class ReadPublicClaimHandler:
    """Applique la politique de publication des claims hors transport HTTP."""

    claim_reader: ClaimReaderPort
    canonical_evidence_reader: CanonicalEvidenceReaderPort

    def __init__(
        self,
        *,
        claim_reader: ClaimReaderPort,
        canonical_evidence_reader: CanonicalEvidenceReaderPort,
    ) -> None:
        if not callable(getattr(claim_reader, "read_claim", None)):
            raise ValueError("claim_reader sans read_claim")
        if not callable(getattr(canonical_evidence_reader, "resolve", None)):
            raise ValueError("canonical_evidence_reader sans resolve")
        object.__setattr__(self, "claim_reader", claim_reader)
        object.__setattr__(self, "canonical_evidence_reader", canonical_evidence_reader)

    def read_claim(self, claim_id: str) -> ReadPublicClaimResult:
        claim = self._read_claim(claim_id)
        _ensure_claim_publication_allowed(claim)
        return ReadPublicClaimResult(claim=claim)

    def read_evidence(self, claim_id: str) -> ReadClaimEvidenceResult:
        claim = self.read_claim(claim_id).claim
        if claim.verified_claim_ref is None:
            raise ValueError("CLAIM_EVIDENCE_REQUIRED")
        if claim.accepted_verification_id is None:
            raise ValueError("CLAIM_EVIDENCE_REQUIRED")

        accepted_evidence_refs = claim.verified_claim_ref.evidence_refs
        for evidence_ref in accepted_evidence_refs:
            _ensure_evidence_ref_attached(claim, evidence_ref)
            canonical_span = self.canonical_evidence_reader.resolve(evidence_ref.source_locator)
            if not isinstance(canonical_span, CanonicalEvidenceSpan):
                raise ValueError("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE")
            if canonical_span.source_locator != evidence_ref.source_locator:
                raise ValueError("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE")
            if canonical_span.quoted_span_hash != evidence_ref.quoted_span_hash:
                raise ValueError("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE")

        return ReadClaimEvidenceResult(
            claim=claim,
            evidence_refs=accepted_evidence_refs,
            dependency_group_ids=claim.verified_claim_ref.dependency_group_ids,
            verification_case_ids=(claim.accepted_verification_id,),
        )

    def _read_claim(self, claim_id: str) -> Claim:
        claim = self.claim_reader.read_claim(_ensure_claim_id(claim_id))
        if not isinstance(claim, Claim):
            raise ValueError("claim invalide")
        return claim


def _ensure_claim_publication_allowed(claim: Claim) -> None:
    if claim.status not in _PUBLIC_CLAIM_STATUSES:
        raise ValueError("CLAIM_PUBLICATION_FORBIDDEN")


def _ensure_evidence_refs(value: Sequence[EvidenceRef]) -> tuple[EvidenceRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_refs invalides")
    evidence_refs = tuple(value)
    if len(evidence_refs) == 0:
        raise ValueError("evidence_refs absentes")
    for evidence_ref in evidence_refs:
        if not isinstance(evidence_ref, EvidenceRef):
            raise ValueError("evidence_ref invalide")
    return evidence_refs


def _ensure_evidence_ref_attached(claim: Claim, evidence_ref: EvidenceRef) -> None:
    if not any(
        association.evidence_ref == evidence_ref for association in claim.evidence_associations
    ):
        raise ValueError("CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE")


def _ensure_text_tuple(value: Sequence[str], field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    return parsed


def _ensure_claim_id(value: object) -> str:
    text = _ensure_text(value, "claim_id")
    if not text.startswith("CLM-"):
        raise ValueError("claim_id invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


__all__ = [
    "CanonicalEvidenceReaderPort",
    "ClaimReaderPort",
    "ReadClaimEvidenceResult",
    "ReadPublicClaimHandler",
    "ReadPublicClaimResult",
]
