"""Repository memoire strict des claims EG."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus, SupersededBy


class InMemoryClaimRepository:
    """Repository non durable utilise par les tests EG."""

    def __init__(self, *, claims: Sequence[Claim]) -> None:
        self._lock = threading.Lock()
        self._claims_by_ref: dict[tuple[str, int], Claim] = {}
        for claim in _ensure_claims(claims):
            self.save(claim)

    @classmethod
    def empty(cls) -> "InMemoryClaimRepository":
        return cls(claims=())

    def save(self, claim: Claim) -> Claim:
        parsed_claim = _ensure_claim(claim)
        with self._lock:
            claim_ref = (parsed_claim.claim_id, parsed_claim.claim_version)
            existing = self._claims_by_ref.get(claim_ref)
            if existing is not None:
                _ensure_existing_version_can_be_replaced(
                    existing=existing,
                    replacement=parsed_claim,
                )
            else:
                _ensure_new_version_is_linked(
                    claims_by_ref=self._claims_by_ref,
                    claim=parsed_claim,
                )
            self._claims_by_ref[claim_ref] = parsed_claim
            return parsed_claim

    def claim_for_id(self, claim_id: str) -> Claim:
        parsed_claim_id = _ensure_claim_id(claim_id)
        with self._lock:
            versions = tuple(
                claim_version
                for current_claim_id, claim_version in self._claims_by_ref
                if current_claim_id == parsed_claim_id
            )
            if len(versions) == 0:
                raise ValueError(f"claim inconnu: {parsed_claim_id}")
            latest_version = max(versions)
            return self._claims_by_ref[(parsed_claim_id, latest_version)]

    def claim_for_version(self, claim_id: str, claim_version: int) -> Claim:
        parsed_claim_id = _ensure_claim_id(claim_id)
        parsed_claim_version = _ensure_positive_integer(claim_version, "claim_version")
        with self._lock:
            claim = self._claims_by_ref.get((parsed_claim_id, parsed_claim_version))
            if claim is None:
                raise ValueError(f"claim inconnu: {parsed_claim_id} v{parsed_claim_version}")
            return claim

    def claim_history_for_id(self, claim_id: str) -> tuple[Claim, ...]:
        parsed_claim_id = _ensure_claim_id(claim_id)
        with self._lock:
            history = tuple(
                self._claims_by_ref[(current_claim_id, claim_version)]
                for current_claim_id, claim_version in sorted(self._claims_by_ref)
                if current_claim_id == parsed_claim_id
            )
            if len(history) == 0:
                raise ValueError(f"claim inconnu: {parsed_claim_id}")
            return history

    def delete_claim_version(self, claim_id: str, claim_version: int) -> None:
        _ensure_claim_id(claim_id)
        _ensure_positive_integer(claim_version, "claim_version")
        raise ValueError("suppression claim interdite")

    def claim_count(self) -> int:
        with self._lock:
            return len(self._claims_by_ref)


def _ensure_claims(value: Sequence[Claim]) -> tuple[Claim, ...]:
    if value is None:
        raise ValueError("claims absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("claims invalides")
    claims = tuple(value)
    for claim in claims:
        _ensure_claim(claim)
    claim_refs = tuple((claim.claim_id, claim.claim_version) for claim in claims)
    if len(claim_refs) != len(set(claim_refs)):
        raise ValueError("claim duplique")
    return claims


def _ensure_existing_version_can_be_replaced(*, existing: Claim, replacement: Claim) -> None:
    if _claim_identity_payload(existing) != _claim_identity_payload(replacement):
        if existing.status in {
            ClaimStatus.REJECTED,
            ClaimStatus.SUPERSEDED,
            ClaimStatus.VERIFIED,
        }:
            raise ValueError("claim_decision immuable")
        raise ValueError("claim_version immuable")

    if existing.status in {ClaimStatus.REJECTED, ClaimStatus.SUPERSEDED} and replacement != existing:
        raise ValueError("claim_decision immuable")

    if existing.status == ClaimStatus.VERIFIED:
        if replacement == existing:
            return
        if replacement.status != ClaimStatus.SUPERSEDED:
            raise ValueError("claim_decision immuable")
        if replacement.superseded_by is None:
            raise ValueError("superseded_by absent")


def _ensure_new_version_is_linked(
    *,
    claims_by_ref: dict[tuple[str, int], Claim],
    claim: Claim,
) -> None:
    if claim.claim_version == 1:
        return

    existing_versions = tuple(
        claim_version
        for current_claim_id, claim_version in claims_by_ref
        if current_claim_id == claim.claim_id
    )
    if len(existing_versions) == 0:
        return

    previous_version = claim.claim_version - 1
    previous_claim = claims_by_ref.get((claim.claim_id, previous_version))
    if previous_claim is None:
        raise ValueError("claim_version precedente absente")
    if previous_claim.status != ClaimStatus.SUPERSEDED:
        raise ValueError("supersession explicite absente")
    expected_link = SupersededBy(claim_id=claim.claim_id, claim_version=claim.claim_version)
    if previous_claim.superseded_by != expected_link:
        raise ValueError("supersession explicite absente")


def _claim_identity_payload(claim: Claim) -> tuple[object, ...]:
    return (
        claim.claim_id,
        claim.claim_version,
        claim.claim_type,
        claim.canonical_proposition,
        claim.scope,
        claim.conditions,
        claim.limitations,
    )


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


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = ["InMemoryClaimRepository"]
