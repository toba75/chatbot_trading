"""Repository memoire strict des claims EG."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.evidence_governance.domain.claim_evidence import Claim


class InMemoryClaimRepository:
    """Repository non durable utilise par les tests EG."""

    def __init__(self, *, claims: Sequence[Claim]) -> None:
        self._lock = threading.Lock()
        self._claims_by_id: dict[str, Claim] = {}
        for claim in _ensure_claims(claims):
            self.save(claim)

    @classmethod
    def empty(cls) -> "InMemoryClaimRepository":
        return cls(claims=())

    def save(self, claim: Claim) -> Claim:
        parsed_claim = _ensure_claim(claim)
        with self._lock:
            existing = self._claims_by_id.get(parsed_claim.claim_id)
            if existing is not None and existing.claim_version != parsed_claim.claim_version:
                raise ValueError("claim_version incoherente")
            self._claims_by_id[parsed_claim.claim_id] = parsed_claim
            return parsed_claim

    def claim_for_id(self, claim_id: str) -> Claim:
        parsed_claim_id = _ensure_claim_id(claim_id)
        with self._lock:
            claim = self._claims_by_id.get(parsed_claim_id)
            if claim is None:
                raise ValueError(f"claim inconnu: {parsed_claim_id}")
            return claim

    def claim_count(self) -> int:
        with self._lock:
            return len(self._claims_by_id)


def _ensure_claims(value: Sequence[Claim]) -> tuple[Claim, ...]:
    if value is None:
        raise ValueError("claims absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("claims invalides")
    claims = tuple(value)
    for claim in claims:
        _ensure_claim(claim)
    claim_ids = tuple(claim.claim_id for claim in claims)
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("claim duplique")
    return claims


def _ensure_claim(value: Claim) -> Claim:
    if not isinstance(value, Claim):
        raise ValueError("claim invalide")
    return value


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


__all__ = ["InMemoryClaimRepository"]
