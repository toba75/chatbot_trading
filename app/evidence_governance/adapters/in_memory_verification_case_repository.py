"""Repository memoire strict des cas de verification EG."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.evidence_governance.domain.claim_verification import VerificationCase


class InMemoryVerificationCaseRepository:
    """Double strict du port VerificationCaseRepository."""

    def __init__(self, *, verification_cases: Sequence[VerificationCase]) -> None:
        self._lock = threading.Lock()
        self._cases_by_id: dict[str, VerificationCase] = {}
        for verification_case in _ensure_cases(verification_cases):
            self.save(verification_case)

    @classmethod
    def empty(cls) -> "InMemoryVerificationCaseRepository":
        return cls(verification_cases=())

    def save(self, verification_case: VerificationCase) -> VerificationCase:
        parsed_case = _ensure_case(verification_case)
        with self._lock:
            existing = self._cases_by_id.get(parsed_case.verification_case_id)
            if existing is not None:
                if existing.claim_id != parsed_case.claim_id:
                    raise ValueError("verification_case claim incoherent")
                if existing.claim_version != parsed_case.claim_version:
                    raise ValueError("verification_case version incoherente")
                if existing.decision is not None and existing != parsed_case:
                    raise ValueError("verification_case deja decide")
            self._cases_by_id[parsed_case.verification_case_id] = parsed_case
            return parsed_case

    def case_for_id(self, verification_case_id: str) -> VerificationCase:
        parsed_verification_case_id = _ensure_verification_case_id(verification_case_id)
        with self._lock:
            verification_case = self._cases_by_id.get(parsed_verification_case_id)
            if verification_case is None:
                raise ValueError(f"verification_case inconnu: {parsed_verification_case_id}")
            return verification_case

    def case_count(self) -> int:
        with self._lock:
            return len(self._cases_by_id)


def _ensure_cases(value: Sequence[VerificationCase]) -> tuple[VerificationCase, ...]:
    if value is None:
        raise ValueError("verification_cases absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("verification_cases invalides")
    cases = tuple(value)
    for verification_case in cases:
        _ensure_case(verification_case)
    case_ids = tuple(verification_case.verification_case_id for verification_case in cases)
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("verification_case duplique")
    return cases


def _ensure_case(value: VerificationCase) -> VerificationCase:
    if not isinstance(value, VerificationCase):
        raise ValueError("verification_case invalide")
    return value


def _ensure_verification_case_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("verification_case_id non textuel")
    if value.strip() == "":
        raise ValueError("verification_case_id vide")
    if value != value.strip():
        raise ValueError("verification_case_id non normalise")
    if not value.startswith("VER-"):
        raise ValueError("verification_case_id invalide")
    return value


__all__ = ["InMemoryVerificationCaseRepository"]
