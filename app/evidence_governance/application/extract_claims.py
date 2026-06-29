"""Cas d'usage EG d'extraction de brouillons de claims."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.evidence_governance.domain.claim_extraction import (
    ClaimAtomicityPolicy,
    ClaimCanonicalizationPolicy,
    ClaimDrafted,
    ClaimExtractionProposal,
    DraftClaim,
    claim_id_for,
)


_ALLOWED_REQUESTING_CONTEXTS = frozenset({"EG"})


@runtime_checkable
class ClaimExtractor(Protocol):
    """Port de proposition structurée de claims depuis des preuves candidates."""

    extractor_version: str

    def extract_claims(
        self,
        *,
        evidence_candidates: Sequence[object],
        extraction_schema_version: str,
        requested_by_context: str,
    ) -> tuple[ClaimExtractionProposal, ...]:
        """Produit des propositions sans les approuver."""


class ClaimDraftRepository(Protocol):
    """Port de stockage des brouillons EG de la tâche T-003."""

    def save_many(self, drafts: Sequence[DraftClaim]) -> tuple[DraftClaim, ...]:
        """Enregistre des brouillons de claims."""


@dataclass(frozen=True)
class ExtractClaimsFromEvidenceCommand:
    """Commande d'extraction de claims candidats depuis des preuves KA."""

    evidence_candidates: Sequence[object]
    extraction_schema_version: str
    requested_by_context: str
    idempotency_key: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_candidates",
            _ensure_evidence_candidates(self.evidence_candidates),
        )
        object.__setattr__(
            self,
            "extraction_schema_version",
            _ensure_text(self.extraction_schema_version, "extraction_schema_version"),
        )
        requested_by_context = _ensure_text(self.requested_by_context, "requested_by_context")
        if requested_by_context not in _ALLOWED_REQUESTING_CONTEXTS:
            raise ValueError("requested_by_context inconnu")
        object.__setattr__(self, "requested_by_context", requested_by_context)
        object.__setattr__(
            self,
            "idempotency_key",
            _ensure_text(self.idempotency_key, "idempotency_key"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))


@dataclass(frozen=True)
class ClaimExtractionResult:
    """Résultat observable d'une extraction acceptée."""

    status: str
    draft_claims: Sequence[DraftClaim]
    events: Sequence[ClaimDrafted]

    def __post_init__(self) -> None:
        status = _ensure_text(self.status, "status")
        if status != "CLAIM_EXTRACTION_ACCEPTED":
            raise ValueError("status extraction invalide")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "draft_claims", _ensure_draft_claims(self.draft_claims))
        object.__setattr__(self, "events", _ensure_events(self.events))
        if len(self.draft_claims) != len(self.events):
            raise ValueError("events incoherents avec draft_claims")


@dataclass(frozen=True)
class ExtractClaimsFromEvidenceHandler:
    """Orchestre l'extraction sans vérification automatique."""

    extractor: ClaimExtractor
    draft_repository: ClaimDraftRepository
    atomicity_policy: ClaimAtomicityPolicy
    canonicalization_policy: ClaimCanonicalizationPolicy

    def __init__(
        self,
        *,
        extractor: ClaimExtractor,
        draft_repository: ClaimDraftRepository,
    ) -> None:
        if not callable(getattr(extractor, "extract_claims", None)):
            raise ValueError("extractor sans extract_claims")
        if not callable(getattr(draft_repository, "save_many", None)):
            raise ValueError("draft_repository sans save_many")
        object.__setattr__(self, "extractor", extractor)
        object.__setattr__(self, "draft_repository", draft_repository)
        object.__setattr__(self, "atomicity_policy", ClaimAtomicityPolicy())
        object.__setattr__(self, "canonicalization_policy", ClaimCanonicalizationPolicy())

    def extract(self, command: ExtractClaimsFromEvidenceCommand) -> ClaimExtractionResult:
        parsed_command = _ensure_command(command)
        proposals = self.extractor.extract_claims(
            evidence_candidates=parsed_command.evidence_candidates,
            extraction_schema_version=parsed_command.extraction_schema_version,
            requested_by_context=parsed_command.requested_by_context,
        )
        parsed_proposals = _ensure_proposals(proposals)
        drafts = []
        for proposal in parsed_proposals:
            self.atomicity_policy.ensure_atomic(proposal)
            self.canonicalization_policy.ensure_preserves_source_semantics(proposal)
            drafts.append(
                DraftClaim.from_proposal(
                    claim_id=claim_id_for(
                        idempotency_key=parsed_command.idempotency_key,
                        proposal=proposal,
                    ),
                    proposal=proposal,
                )
            )

        saved_drafts = self.draft_repository.save_many(tuple(drafts))
        events = tuple(
            draft.to_event(occurred_at=parsed_command.occurred_at) for draft in saved_drafts
        )
        return ClaimExtractionResult(
            status="CLAIM_EXTRACTION_ACCEPTED",
            draft_claims=saved_drafts,
            events=events,
        )


def _ensure_command(value: ExtractClaimsFromEvidenceCommand) -> ExtractClaimsFromEvidenceCommand:
    if not isinstance(value, ExtractClaimsFromEvidenceCommand):
        raise ValueError("command extraction invalide")
    return value


def _ensure_proposals(value: Sequence[ClaimExtractionProposal]) -> tuple[ClaimExtractionProposal, ...]:
    if value is None:
        raise ValueError("claim_proposals absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("claim_proposals invalides")
    proposals = tuple(value)
    if len(proposals) == 0:
        raise ValueError("claim_proposals absents")
    for proposal in proposals:
        if not isinstance(proposal, ClaimExtractionProposal):
            raise ValueError("claim_proposal invalide")
    return proposals


def _ensure_draft_claims(value: Sequence[DraftClaim]) -> tuple[DraftClaim, ...]:
    if value is None:
        raise ValueError("draft_claims absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("draft_claims invalides")
    drafts = tuple(value)
    for draft in drafts:
        if not isinstance(draft, DraftClaim):
            raise ValueError("draft_claim invalide")
    return drafts


def _ensure_events(value: Sequence[ClaimDrafted]) -> tuple[ClaimDrafted, ...]:
    if value is None:
        raise ValueError("events absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    for event in events:
        if not isinstance(event, ClaimDrafted):
            raise ValueError("event claim invalide")
    return events


def _ensure_evidence_candidates(value: Sequence[object]) -> tuple[object, ...]:
    if value is None:
        raise ValueError("evidence_candidates absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_candidates invalides")
    candidates = tuple(value)
    if len(candidates) == 0:
        raise ValueError("evidence_candidates absents")
    chunk_ids = []
    for candidate in candidates:
        chunk_id = _ensure_text(getattr(candidate, "chunk_id", None), "chunk_id")
        if not chunk_id.startswith("KCHK-"):
            raise ValueError("chunk_id invalide")
        chunk_ids.append(chunk_id)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("evidence_candidates dupliques")
    return candidates


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "ClaimDraftRepository",
    "ClaimExtractionResult",
    "ClaimExtractor",
    "ExtractClaimsFromEvidenceCommand",
    "ExtractClaimsFromEvidenceHandler",
]
