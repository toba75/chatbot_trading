"""Repository mémoire strict des brouillons de claims EG."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.evidence_governance.domain.claim_extraction import DraftClaim


class InMemoryClaimDraftRepository:
    """Repository non durable utilisé pour T-003 et les tests d'acceptation."""

    def __init__(self, *, drafts: Sequence[DraftClaim]) -> None:
        self._lock = threading.Lock()
        self._drafts_by_id: dict[str, DraftClaim] = {}
        for draft in _ensure_drafts(drafts, allow_empty=True):
            self.save_many((draft,))

    @classmethod
    def empty(cls) -> "InMemoryClaimDraftRepository":
        return cls(drafts=())

    def save_many(self, drafts: Sequence[DraftClaim]) -> tuple[DraftClaim, ...]:
        parsed_drafts = _ensure_drafts(drafts, allow_empty=False)
        with self._lock:
            saved: list[DraftClaim] = []
            for draft in parsed_drafts:
                existing = self._drafts_by_id.get(draft.claim_id)
                if existing is not None:
                    if existing.to_payload() != draft.to_payload():
                        raise ValueError(f"draft_claim duplique incoherent: {draft.claim_id}")
                    saved.append(existing)
                    continue
                self._drafts_by_id[draft.claim_id] = draft
                saved.append(draft)
            return tuple(saved)

    def draft_for_id(self, claim_id: str) -> DraftClaim:
        parsed_claim_id = _ensure_claim_id(claim_id)
        with self._lock:
            draft = self._drafts_by_id.get(parsed_claim_id)
            if draft is None:
                raise ValueError(f"draft_claim inconnu: {parsed_claim_id}")
            return draft

    def draft_count(self) -> int:
        with self._lock:
            return len(self._drafts_by_id)


def _ensure_drafts(
    value: Sequence[DraftClaim],
    *,
    allow_empty: bool,
) -> tuple[DraftClaim, ...]:
    if value is None:
        raise ValueError("draft_claims absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("draft_claims invalides")
    drafts = tuple(value)
    if not allow_empty and len(drafts) == 0:
        raise ValueError("draft_claims absents")
    for draft in drafts:
        if not isinstance(draft, DraftClaim):
            raise ValueError("draft_claim invalide")
    claim_ids = tuple(draft.claim_id for draft in drafts)
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("draft_claim duplique")
    return drafts


def _ensure_claim_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("claim_id non textuel")
    if value.strip() == "":
        raise ValueError("claim_id vide")
    if value != value.strip():
        raise ValueError("claim_id non normalise")
    if not value.startswith("CLM-"):
        raise ValueError("claim_id invalide")
    return value


__all__ = ["InMemoryClaimDraftRepository"]
