"""Cas d'usage EG de vérification de claims."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.contracts.evidence_claims import VerifiedClaimRef
from app.evidence_governance.application.attach_evidence import ClaimRepository
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus
from app.evidence_governance.domain.claim_verification import (
    ClaimRejected,
    ClaimSubmittedForVerification,
    ClaimVerificationPolicy,
    ClaimVerified,
    IndependentVerificationReport,
    VerificationCase,
    VerificationDecisionRecorded,
    transition_claim_to,
    transition_claim_to_rejected,
    transition_claim_to_verified,
)


@runtime_checkable
class IndependentClaimVerifier(Protocol):
    """Port de proposition de verdict sans mutation de l'etat metier."""

    def verify(
        self,
        *,
        claim: Claim,
        verification_case: VerificationCase,
        policy_version: str,
        verifier_profile_id: str,
    ) -> IndependentVerificationReport:
        """Produit un rapport de verification independant."""


class VerificationCaseRepository(Protocol):
    """Port de stockage des cas de verification immuables."""

    def save(self, verification_case: VerificationCase) -> VerificationCase:
        """Enregistre un cas de verification."""

    def case_for_id(self, verification_case_id: str) -> VerificationCase:
        """Retourne un cas de verification existant."""


@dataclass(frozen=True)
class SubmitClaimForVerification:
    """Commande explicite de soumission d'un claim a verification."""

    claim_id: str
    verification_case_id: str
    verification_policy_version: str
    verifier_profile_id: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "verification_case_id",
            _ensure_verification_case_id(self.verification_case_id),
        )
        object.__setattr__(
            self,
            "verification_policy_version",
            _ensure_text(self.verification_policy_version, "verification_policy_version"),
        )
        object.__setattr__(
            self,
            "verifier_profile_id",
            _ensure_text(self.verifier_profile_id, "verifier_profile_id"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))


@dataclass(frozen=True)
class VerifyClaimResult:
    """Resultat observable d'une verification de claim."""

    status: str
    claim: Claim
    verification_case: VerificationCase
    verified_claim_ref: VerifiedClaimRef | None
    events: Sequence[object]

    def __post_init__(self) -> None:
        status = _ensure_text(self.status, "status")
        if status != "CLAIM_VERIFICATION_RECORDED":
            raise ValueError("status verification invalide")
        object.__setattr__(self, "status", status)
        if not isinstance(self.claim, Claim):
            raise ValueError("claim invalide")
        if not isinstance(self.verification_case, VerificationCase):
            raise ValueError("verification_case invalide")
        if self.verified_claim_ref is not None and not isinstance(
            self.verified_claim_ref,
            VerifiedClaimRef,
        ):
            raise ValueError("verified_claim_ref invalide")
        object.__setattr__(self, "events", _ensure_events(self.events))


@dataclass(frozen=True)
class VerifyClaimHandler:
    """Orchestre la verification sans laisser le verificateur decider l'etat."""

    claim_repository: ClaimRepository
    verification_case_repository: VerificationCaseRepository
    verifier: IndependentClaimVerifier
    policy: ClaimVerificationPolicy

    def __init__(
        self,
        *,
        claim_repository: ClaimRepository,
        verification_case_repository: VerificationCaseRepository,
        verifier: IndependentClaimVerifier,
    ) -> None:
        if not callable(getattr(claim_repository, "claim_for_id", None)):
            raise ValueError("claim_repository sans claim_for_id")
        if not callable(getattr(claim_repository, "save", None)):
            raise ValueError("claim_repository sans save")
        if not callable(getattr(verification_case_repository, "save", None)):
            raise ValueError("verification_case_repository sans save")
        if not callable(getattr(verification_case_repository, "case_for_id", None)):
            raise ValueError("verification_case_repository sans case_for_id")
        if not callable(getattr(verifier, "verify", None)):
            raise ValueError("verifier sans verify")
        object.__setattr__(self, "claim_repository", claim_repository)
        object.__setattr__(self, "verification_case_repository", verification_case_repository)
        object.__setattr__(self, "verifier", verifier)
        object.__setattr__(self, "policy", ClaimVerificationPolicy())

    def verify(self, command: SubmitClaimForVerification) -> VerifyClaimResult:
        parsed_command = _ensure_command(command)
        claim = self.claim_repository.claim_for_id(parsed_command.claim_id)
        under_verification_claim = transition_claim_to(
            claim=claim,
            status=ClaimStatus.UNDER_VERIFICATION,
        )
        saved_under_verification_claim = self.claim_repository.save(under_verification_claim)
        submitted_event = ClaimSubmittedForVerification.from_claim(
            claim=saved_under_verification_claim,
            verification_case_id=parsed_command.verification_case_id,
            policy_version=parsed_command.verification_policy_version,
            occurred_at=parsed_command.occurred_at,
        )
        opened_case = self.verification_case_repository.save(
            VerificationCase.opened(
                verification_case_id=parsed_command.verification_case_id,
                claim_id=saved_under_verification_claim.claim_id,
                claim_version=saved_under_verification_claim.claim_version,
                policy_version=parsed_command.verification_policy_version,
                submitted_at=parsed_command.occurred_at,
            )
        )
        report = self.verifier.verify(
            claim=saved_under_verification_claim,
            verification_case=opened_case,
            policy_version=parsed_command.verification_policy_version,
            verifier_profile_id=parsed_command.verifier_profile_id,
        )
        policy_decision = self.policy.decision_for(
            claim=saved_under_verification_claim,
            report=report,
            expected_policy_version=parsed_command.verification_policy_version,
            verification_case_id=parsed_command.verification_case_id,
        )
        recorded_case, decision_event = opened_case.record_decision(
            decision=policy_decision.decision,
            occurred_at=parsed_command.occurred_at,
        )
        saved_case = self.verification_case_repository.save(recorded_case)
        if policy_decision.target_status == ClaimStatus.VERIFIED:
            if policy_decision.verified_claim_ref is None:
                raise ValueError("verified_claim_ref absent")
            final_claim = self.claim_repository.save(
                transition_claim_to_verified(
                    claim=saved_under_verification_claim,
                    verified_claim_ref=policy_decision.verified_claim_ref,
                    accepted_verification_id=parsed_command.verification_case_id,
                )
            )
            final_event = ClaimVerified(
                claim_id=final_claim.claim_id,
                claim_version=final_claim.claim_version,
                verified_claim_ref=policy_decision.verified_claim_ref,
                accepted_verification_id=parsed_command.verification_case_id,
                occurred_at=parsed_command.occurred_at,
            )
        else:
            final_claim = self.claim_repository.save(
                transition_claim_to_rejected(
                    claim=saved_under_verification_claim,
                    reason_codes=policy_decision.reason_codes,
                    rejected_at=parsed_command.occurred_at,
                )
            )
            final_event = ClaimRejected(
                claim_id=final_claim.claim_id,
                claim_version=final_claim.claim_version,
                reason_codes=policy_decision.reason_codes,
                rejected_at=parsed_command.occurred_at,
            )

        return VerifyClaimResult(
            status="CLAIM_VERIFICATION_RECORDED",
            claim=final_claim,
            verification_case=saved_case,
            verified_claim_ref=policy_decision.verified_claim_ref,
            events=(submitted_event, decision_event, final_event),
        )


def _ensure_command(value: SubmitClaimForVerification) -> SubmitClaimForVerification:
    if not isinstance(value, SubmitClaimForVerification):
        raise ValueError("command verification invalide")
    return value


def _ensure_events(value: Sequence[object]) -> tuple[object, ...]:
    if value is None:
        raise ValueError("events absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        event_type = getattr(event, "event_type", None)
        if event_type not in {
            "ClaimSubmittedForVerification",
            "VerificationDecisionRecorded",
            "ClaimVerified",
            "ClaimRejected",
        }:
            raise ValueError("event verification invalide")
    return events


def _ensure_claim_id(value: object) -> str:
    text = _ensure_text(value, "claim_id")
    if not text.startswith("CLM-"):
        raise ValueError("claim_id invalide")
    return text


def _ensure_verification_case_id(value: object) -> str:
    text = _ensure_text(value, "verification_case_id")
    if not text.startswith("VER-"):
        raise ValueError("verification_case_id invalide")
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
    "IndependentClaimVerifier",
    "SubmitClaimForVerification",
    "VerificationCaseRepository",
    "VerifyClaimHandler",
    "VerifyClaimResult",
]
