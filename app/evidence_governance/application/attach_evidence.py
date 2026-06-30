"""Cas d'usage EG d'attachement de preuves admissibles."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.contracts.evidence_claims import EvidenceRef
from app.contracts.source_references import SourceLocator
from app.evidence_governance.domain.claim_evidence import (
    CanonicalEvidenceSpan,
    Claim,
    EvidenceAdmissibilityPolicy,
    EvidenceAttachedToClaim,
)


@runtime_checkable
class CanonicalEvidenceReader(Protocol):
    """Port EG de resolution d'une preuve canonique publiee."""

    def resolve(self, source_locator: SourceLocator) -> CanonicalEvidenceSpan:
        """Retourne le span canonique exact, sans voisinage implicite."""


class ClaimRepository(Protocol):
    """Port de stockage des aggregates Claim EG."""

    def claim_for_id(self, claim_id: str) -> Claim:
        """Retourne un claim existant."""

    def save(self, claim: Claim) -> Claim:
        """Enregistre l'etat courant du claim."""


@dataclass(frozen=True)
class AttachEvidenceToClaimCommand:
    """Commande explicite d'attachement d'une preuve a un claim."""

    claim_id: str
    evidence_ref: EvidenceRef
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        if not isinstance(self.evidence_ref, EvidenceRef):
            raise ValueError("evidence_ref invalide")
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))


@dataclass(frozen=True)
class AttachEvidenceToClaimResult:
    """Resultat observable d'un attachement accepte."""

    status: str
    claim: Claim
    events: Sequence[EvidenceAttachedToClaim]

    def __post_init__(self) -> None:
        status = _ensure_text(self.status, "status")
        if status != "CLAIM_EVIDENCE_ATTACHED":
            raise ValueError("status attachement invalide")
        object.__setattr__(self, "status", status)
        if not isinstance(self.claim, Claim):
            raise ValueError("claim invalide")
        object.__setattr__(self, "events", _ensure_events(self.events))


@dataclass(frozen=True)
class AttachEvidenceToClaimHandler:
    """Orchestre l'attachement sans verifier le claim."""

    claim_repository: ClaimRepository
    canonical_evidence_reader: CanonicalEvidenceReader
    evidence_admissibility_policy: EvidenceAdmissibilityPolicy

    def __init__(
        self,
        *,
        claim_repository: ClaimRepository,
        canonical_evidence_reader: CanonicalEvidenceReader,
    ) -> None:
        if not callable(getattr(claim_repository, "claim_for_id", None)):
            raise ValueError("claim_repository sans claim_for_id")
        if not callable(getattr(claim_repository, "save", None)):
            raise ValueError("claim_repository sans save")
        if not callable(getattr(canonical_evidence_reader, "resolve", None)):
            raise ValueError("canonical_evidence_reader sans resolve")
        object.__setattr__(self, "claim_repository", claim_repository)
        object.__setattr__(self, "canonical_evidence_reader", canonical_evidence_reader)
        object.__setattr__(
            self,
            "evidence_admissibility_policy",
            EvidenceAdmissibilityPolicy(),
        )

    def attach(self, command: AttachEvidenceToClaimCommand) -> AttachEvidenceToClaimResult:
        parsed_command = _ensure_command(command)
        claim = self.claim_repository.claim_for_id(parsed_command.claim_id)
        self.evidence_admissibility_policy.association_for(
            evidence_ref=parsed_command.evidence_ref,
            canonical_evidence_reader=self.canonical_evidence_reader,
        )
        updated_claim, event = claim.propose_evidence(
            evidence_ref=parsed_command.evidence_ref,
            canonical_evidence_reader=self.canonical_evidence_reader,
            occurred_at=parsed_command.occurred_at,
        )
        saved_claim = self.claim_repository.save(updated_claim)
        return AttachEvidenceToClaimResult(
            status="CLAIM_EVIDENCE_ATTACHED",
            claim=saved_claim,
            events=(event,),
        )


def _ensure_command(value: AttachEvidenceToClaimCommand) -> AttachEvidenceToClaimCommand:
    if not isinstance(value, AttachEvidenceToClaimCommand):
        raise ValueError("command attachement invalide")
    return value


def _ensure_events(
    value: Sequence[EvidenceAttachedToClaim],
) -> tuple[EvidenceAttachedToClaim, ...]:
    if value is None:
        raise ValueError("events absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, EvidenceAttachedToClaim):
            raise ValueError("event claim invalide")
    return events


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


def _ensure_utc_instant(value: object) -> str:
    text = _ensure_text(value, "occurred_at")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError("occurred_at invalide")
    return text


__all__ = [
    "AttachEvidenceToClaimCommand",
    "AttachEvidenceToClaimHandler",
    "AttachEvidenceToClaimResult",
    "CanonicalEvidenceReader",
    "ClaimRepository",
]
