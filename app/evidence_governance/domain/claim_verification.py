"""Verification stricte des claims EG."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from app.contracts.evidence_claims import (
    SUPPORTS_DIRECTLY_RELATION,
    VERIFIED_CLAIM_STATUS,
    VerifiedClaimRef,
)
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus, EvidenceAssociation
from app.evidence_governance.domain.claim_extraction import ClaimScope


_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_VERIFICATION_CASE_ID_PATTERN = re.compile(r"^VER-[A-Z0-9][A-Z0-9-]*$")
_DEPENDENCY_GROUP_ID_PATTERN = re.compile(r"^DEP-[A-Z0-9][A-Z0-9-]*$")


class VerificationVerdict(str, Enum):
    """Verdict explicite propose par un verificateur independant."""

    ENTAILED = "ENTAILED"
    PARTIALLY_ENTAILED = "PARTIALLY_ENTAILED"
    NOT_ENTAILED = "NOT_ENTAILED"


class ReasonCode(str, Enum):
    """Raison publique de decision de verification."""

    INSUFFICIENT_DIRECT_EVIDENCE = "INSUFFICIENT_DIRECT_EVIDENCE"
    CLAIM_SCOPE_EXCEEDS_EVIDENCE = "CLAIM_SCOPE_EXCEEDS_EVIDENCE"
    VERDICT_NOT_AUTHORIZED = "VERDICT_NOT_AUTHORIZED"
    CLAIM_VERIFICATION_POLICY_MISSING = "CLAIM_VERIFICATION_POLICY_MISSING"


@dataclass(frozen=True)
class IndependentVerificationReport:
    """Rapport structure propose par un verificateur sans autorite metier directe."""

    verdict: VerificationVerdict
    reason_codes: Sequence[ReasonCode]
    accepted_evidence_ids: Sequence[str]
    evidence_scopes: Mapping[str, Mapping[str, Any]]
    dependency_group_ids: Sequence[str]
    model_version: str
    prompt_version: str
    policy_version: str
    verifier_profile_id: str
    calibrated_score: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, VerificationVerdict):
            raise ValueError("verdict verification invalide")
        object.__setattr__(self, "reason_codes", _ensure_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "accepted_evidence_ids",
            _ensure_evidence_ids(self.accepted_evidence_ids),
        )
        object.__setattr__(
            self,
            "evidence_scopes",
            _ensure_evidence_scope_mapping(self.evidence_scopes),
        )
        object.__setattr__(
            self,
            "dependency_group_ids",
            _ensure_dependency_group_ids(self.dependency_group_ids),
        )
        object.__setattr__(self, "model_version", _ensure_text(self.model_version, "model_version"))
        object.__setattr__(
            self,
            "prompt_version",
            _ensure_text(self.prompt_version, "prompt_version"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(
            self,
            "verifier_profile_id",
            _ensure_text(self.verifier_profile_id, "verifier_profile_id"),
        )
        object.__setattr__(
            self,
            "calibrated_score",
            _ensure_optional_score(self.calibrated_score),
        )

    def scope_for_evidence_id(self, evidence_id: str) -> ClaimScope:
        parsed_evidence_id = _ensure_evidence_id(evidence_id)
        if parsed_evidence_id not in self.evidence_scopes:
            raise ValueError("evidence_scope absent")
        return self.evidence_scopes[parsed_evidence_id]


@dataclass(frozen=True)
class VerificationDecision:
    """Decision de verification immuable enregistree dans un VerificationCase."""

    verdict: VerificationVerdict
    reason_codes: Sequence[ReasonCode]
    accepted_evidence_ids: Sequence[str]
    model_version: str
    prompt_version: str
    policy_version: str
    verifier_profile_id: str
    calibrated_score: float | None

    @classmethod
    def from_report(
        cls,
        *,
        report: IndependentVerificationReport,
        reason_codes: Sequence[ReasonCode],
    ) -> "VerificationDecision":
        parsed_report = _ensure_report(report)
        return cls(
            verdict=parsed_report.verdict,
            reason_codes=reason_codes,
            accepted_evidence_ids=parsed_report.accepted_evidence_ids,
            model_version=parsed_report.model_version,
            prompt_version=parsed_report.prompt_version,
            policy_version=parsed_report.policy_version,
            verifier_profile_id=parsed_report.verifier_profile_id,
            calibrated_score=parsed_report.calibrated_score,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, VerificationVerdict):
            raise ValueError("verdict verification invalide")
        object.__setattr__(self, "reason_codes", _ensure_reason_codes(self.reason_codes))
        object.__setattr__(
            self,
            "accepted_evidence_ids",
            _ensure_evidence_ids(self.accepted_evidence_ids),
        )
        object.__setattr__(self, "model_version", _ensure_text(self.model_version, "model_version"))
        object.__setattr__(
            self,
            "prompt_version",
            _ensure_text(self.prompt_version, "prompt_version"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(
            self,
            "verifier_profile_id",
            _ensure_text(self.verifier_profile_id, "verifier_profile_id"),
        )
        object.__setattr__(
            self,
            "calibrated_score",
            _ensure_optional_score(self.calibrated_score),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reason_codes": tuple(reason_code.value for reason_code in self.reason_codes),
            "accepted_evidence_ids": self.accepted_evidence_ids,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "policy_version": self.policy_version,
            "verifier_profile_id": self.verifier_profile_id,
            "calibrated_score": self.calibrated_score,
        }


@dataclass(frozen=True)
class VerificationCase:
    """Cas de verification independant et immuable pour une version de claim."""

    verification_case_id: str
    claim_id: str
    claim_version: int
    policy_version: str
    submitted_at: str
    decision: VerificationDecision | None

    @classmethod
    def opened(
        cls,
        *,
        verification_case_id: str,
        claim_id: str,
        claim_version: int,
        policy_version: str,
        submitted_at: str,
    ) -> "VerificationCase":
        return cls(
            verification_case_id=verification_case_id,
            claim_id=claim_id,
            claim_version=claim_version,
            policy_version=policy_version,
            submitted_at=submitted_at,
            decision=None,
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "verification_case_id",
            _ensure_verification_case_id(self.verification_case_id),
        )
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "submitted_at", _ensure_utc_instant(self.submitted_at, "submitted_at"))
        if self.decision is not None and not isinstance(self.decision, VerificationDecision):
            raise ValueError("verification_decision invalide")

    def record_decision(
        self,
        *,
        decision: VerificationDecision,
        occurred_at: str,
    ) -> tuple["VerificationCase", "VerificationDecisionRecorded"]:
        if self.decision is not None:
            raise ValueError("verification_case deja decide")
        if not isinstance(decision, VerificationDecision):
            raise ValueError("verification_decision invalide")
        recorded_case = VerificationCase(
            verification_case_id=self.verification_case_id,
            claim_id=self.claim_id,
            claim_version=self.claim_version,
            policy_version=self.policy_version,
            submitted_at=self.submitted_at,
            decision=decision,
        )
        return (
            recorded_case,
            VerificationDecisionRecorded.from_case(
                verification_case=recorded_case,
                occurred_at=occurred_at,
            ),
        )


@dataclass(frozen=True)
class ClaimSubmittedForVerification:
    """Evenement publie quand un claim passe en verification."""

    claim_id: str
    claim_version: int
    verification_case_id: str
    policy_version: str
    occurred_at: str

    @classmethod
    def from_claim(
        cls,
        *,
        claim: Claim,
        verification_case_id: str,
        policy_version: str,
        occurred_at: str,
    ) -> "ClaimSubmittedForVerification":
        parsed_claim = _ensure_claim(claim)
        if parsed_claim.status != ClaimStatus.UNDER_VERIFICATION:
            raise ValueError(f"transition claim interdite: {parsed_claim.status.value}")
        return cls(
            claim_id=parsed_claim.claim_id,
            claim_version=parsed_claim.claim_version,
            verification_case_id=verification_case_id,
            policy_version=policy_version,
            occurred_at=occurred_at,
        )

    @property
    def event_type(self) -> str:
        return "ClaimSubmittedForVerification"

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        object.__setattr__(
            self,
            "verification_case_id",
            _ensure_verification_case_id(self.verification_case_id),
        )
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "claim_id": self.claim_id,
                "claim_version": self.claim_version,
                "verification_case_id": self.verification_case_id,
                "policy_version": self.policy_version,
            },
        }


@dataclass(frozen=True)
class VerificationDecisionRecorded:
    """Evenement publie quand le verdict de verification est enregistre."""

    verification_case_id: str
    claim_id: str
    verdict: VerificationVerdict
    reason_codes: Sequence[ReasonCode]
    model_version: str
    prompt_version: str
    policy_version: str
    occurred_at: str

    @classmethod
    def from_case(
        cls,
        *,
        verification_case: VerificationCase,
        occurred_at: str,
    ) -> "VerificationDecisionRecorded":
        parsed_case = _ensure_case(verification_case)
        if parsed_case.decision is None:
            raise ValueError("verification_decision absente")
        return cls(
            verification_case_id=parsed_case.verification_case_id,
            claim_id=parsed_case.claim_id,
            verdict=parsed_case.decision.verdict,
            reason_codes=parsed_case.decision.reason_codes,
            model_version=parsed_case.decision.model_version,
            prompt_version=parsed_case.decision.prompt_version,
            policy_version=parsed_case.decision.policy_version,
            occurred_at=occurred_at,
        )

    @property
    def event_type(self) -> str:
        return "VerificationDecisionRecorded"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "verification_case_id",
            _ensure_verification_case_id(self.verification_case_id),
        )
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        if not isinstance(self.verdict, VerificationVerdict):
            raise ValueError("verdict verification invalide")
        object.__setattr__(self, "reason_codes", _ensure_reason_codes(self.reason_codes))
        object.__setattr__(self, "model_version", _ensure_text(self.model_version, "model_version"))
        object.__setattr__(
            self,
            "prompt_version",
            _ensure_text(self.prompt_version, "prompt_version"),
        )
        object.__setattr__(
            self,
            "policy_version",
            _ensure_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "verification_case_id": self.verification_case_id,
                "claim_id": self.claim_id,
                "verdict": self.verdict.value,
                "reason_codes": tuple(reason_code.value for reason_code in self.reason_codes),
                "model_version": self.model_version,
                "prompt_version": self.prompt_version,
                "policy_version": self.policy_version,
            },
        }


@dataclass(frozen=True)
class ClaimVerified:
    """Evenement publie apres verification positive controlee."""

    claim_id: str
    claim_version: int
    verified_claim_ref: VerifiedClaimRef
    accepted_verification_id: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "ClaimVerified"

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        if not isinstance(self.verified_claim_ref, VerifiedClaimRef):
            raise ValueError("verified_claim_ref invalide")
        object.__setattr__(
            self,
            "accepted_verification_id",
            _ensure_verification_case_id(self.accepted_verification_id),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "claim_id": self.claim_id,
                "claim_version": self.claim_version,
                "verified_claim_ref": self.verified_claim_ref.to_payload(),
                "accepted_verification_id": self.accepted_verification_id,
            },
        }


@dataclass(frozen=True)
class ClaimRejected:
    """Evenement publie quand la verification refuse une version de claim."""

    claim_id: str
    claim_version: int
    reason_codes: Sequence[ReasonCode]
    rejected_at: str

    @property
    def event_type(self) -> str:
        return "ClaimRejected"

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        object.__setattr__(self, "reason_codes", _ensure_non_empty_reason_codes(self.reason_codes))
        object.__setattr__(self, "rejected_at", _ensure_utc_instant(self.rejected_at, "rejected_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.rejected_at,
            "payload": {
                "claim_id": self.claim_id,
                "claim_version": self.claim_version,
                "reason_codes": tuple(reason_code.value for reason_code in self.reason_codes),
                "rejected_at": self.rejected_at,
            },
        }


@dataclass(frozen=True)
class ClaimVerificationPolicyDecision:
    """Resultat de politique separant decision enregistree et effet de publication."""

    target_status: ClaimStatus
    reason_codes: Sequence[ReasonCode]
    verified_claim_ref: VerifiedClaimRef | None
    decision: VerificationDecision

    def __post_init__(self) -> None:
        if self.target_status not in {ClaimStatus.VERIFIED, ClaimStatus.REJECTED}:
            raise ValueError("target_status verification invalide")
        object.__setattr__(self, "reason_codes", _ensure_reason_codes(self.reason_codes))
        if self.verified_claim_ref is not None and not isinstance(
            self.verified_claim_ref,
            VerifiedClaimRef,
        ):
            raise ValueError("verified_claim_ref invalide")
        if not isinstance(self.decision, VerificationDecision):
            raise ValueError("verification_decision invalide")


class ScopePreservationPolicy:
    """Politique refusant toute portee de claim plus large que les preuves."""

    def ensure_scope_preserved(
        self,
        *,
        claim_scope: ClaimScope,
        evidence_scopes: Sequence[ClaimScope],
    ) -> None:
        parsed_claim_scope = _ensure_claim_scope(claim_scope)
        parsed_evidence_scopes = _ensure_claim_scopes(evidence_scopes)
        for evidence_scope in parsed_evidence_scopes:
            if evidence_scope.to_payload() != parsed_claim_scope.to_payload():
                raise ValueError(ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE.value)


class ClaimVerificationPolicy:
    """Politique decidant VERIFIED ou REJECTED sans utiliser le score comme verite."""

    def __init__(self) -> None:
        self._scope_policy = ScopePreservationPolicy()

    def decision_for(
        self,
        *,
        claim: Claim,
        report: IndependentVerificationReport,
        expected_policy_version: str,
        verification_case_id: str | None = None,
    ) -> ClaimVerificationPolicyDecision:
        parsed_claim = _ensure_claim(claim)
        parsed_report = _ensure_report(report)
        parsed_expected_policy_version = _ensure_text(
            expected_policy_version,
            "verification_policy_version",
        )
        if parsed_report.policy_version != parsed_expected_policy_version:
            return self._rejected_decision(
                report=parsed_report,
                reason_codes=(ReasonCode.CLAIM_VERIFICATION_POLICY_MISSING,),
            )

        direct_associations = self._direct_associations_for(
            claim=parsed_claim,
            accepted_evidence_ids=parsed_report.accepted_evidence_ids,
        )
        if len(direct_associations) == 0:
            return self._rejected_decision(
                report=parsed_report,
                reason_codes=(ReasonCode.INSUFFICIENT_DIRECT_EVIDENCE,),
            )

        if parsed_report.verdict != VerificationVerdict.ENTAILED:
            reason_codes = _merge_reason_codes(
                parsed_report.reason_codes,
                self._scope_reason_if_needed(
                    claim=parsed_claim,
                    report=parsed_report,
                    direct_associations=direct_associations,
                ),
                (ReasonCode.VERDICT_NOT_AUTHORIZED,),
            )
            return self._rejected_decision(report=parsed_report, reason_codes=reason_codes)

        try:
            evidence_scopes = tuple(
                parsed_report.scope_for_evidence_id(association.evidence_ref.evidence_id)
                for association in direct_associations
            )
            self._scope_policy.ensure_scope_preserved(
                claim_scope=parsed_claim.scope,
                evidence_scopes=evidence_scopes,
            )
        except ValueError as exc:
            if ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE.value not in str(exc):
                raise
            return self._rejected_decision(
                report=parsed_report,
                reason_codes=(ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE,),
            )

        verified_claim_ref = _verified_claim_ref_for(
            claim=parsed_claim,
            verification_case_id=_ensure_verification_case_id(verification_case_id),
            direct_associations=direct_associations,
            dependency_group_ids=parsed_report.dependency_group_ids,
        )
        return ClaimVerificationPolicyDecision(
            target_status=ClaimStatus.VERIFIED,
            reason_codes=(),
            verified_claim_ref=verified_claim_ref,
            decision=VerificationDecision.from_report(report=parsed_report, reason_codes=()),
        )

    def _direct_associations_for(
        self,
        *,
        claim: Claim,
        accepted_evidence_ids: Sequence[str],
    ) -> tuple[EvidenceAssociation, ...]:
        parsed_accepted_ids = _ensure_evidence_ids(accepted_evidence_ids)
        associations = tuple(
            association
            for association in claim.evidence_associations
            if association.evidence_ref.evidence_id in parsed_accepted_ids
            and association.relation == SUPPORTS_DIRECTLY_RELATION
        )
        return associations

    def _scope_reason_if_needed(
        self,
        *,
        claim: Claim,
        report: IndependentVerificationReport,
        direct_associations: Sequence[EvidenceAssociation],
    ) -> tuple[ReasonCode, ...]:
        try:
            self._scope_policy.ensure_scope_preserved(
                claim_scope=claim.scope,
                evidence_scopes=tuple(
                    report.scope_for_evidence_id(association.evidence_ref.evidence_id)
                    for association in direct_associations
                ),
            )
        except ValueError as exc:
            if ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE.value not in str(exc):
                raise
            return (ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE,)
        return ()

    def _rejected_decision(
        self,
        *,
        report: IndependentVerificationReport,
        reason_codes: Sequence[ReasonCode],
    ) -> ClaimVerificationPolicyDecision:
        parsed_reason_codes = _ensure_non_empty_reason_codes(reason_codes)
        return ClaimVerificationPolicyDecision(
            target_status=ClaimStatus.REJECTED,
            reason_codes=parsed_reason_codes,
            verified_claim_ref=None,
            decision=VerificationDecision.from_report(
                report=report,
                reason_codes=parsed_reason_codes,
            ),
        )


def _verified_claim_ref_for(
    *,
    claim: Claim,
    verification_case_id: str,
    direct_associations: Sequence[EvidenceAssociation],
    dependency_group_ids: Sequence[str],
) -> VerifiedClaimRef:
    parsed_claim = _ensure_claim(claim)
    parsed_direct_associations = _ensure_direct_associations(direct_associations)
    return VerifiedClaimRef(
        schema_version="1.0",
        claim_id=parsed_claim.claim_id,
        claim_version=parsed_claim.claim_version,
        canonical_text=parsed_claim.canonical_proposition.text,
        scope=parsed_claim.scope.to_payload(),
        status=VERIFIED_CLAIM_STATUS,
        verification_id=verification_case_id,
        evidence_refs=tuple(association.evidence_ref for association in parsed_direct_associations),
        dependency_group_ids=_ensure_dependency_group_ids(dependency_group_ids),
    )


def transition_claim_to(
    *,
    claim: Claim,
    status: ClaimStatus,
) -> Claim:
    parsed_claim = _ensure_claim(claim)
    if not isinstance(status, ClaimStatus):
        raise ValueError("status claim invalide")
    if status == ClaimStatus.UNDER_VERIFICATION and parsed_claim.status != ClaimStatus.EVIDENCE_ATTACHED:
        raise ValueError(f"transition claim interdite: {parsed_claim.status.value}")
    if status in {ClaimStatus.VERIFIED, ClaimStatus.REJECTED} and parsed_claim.status != ClaimStatus.UNDER_VERIFICATION:
        raise ValueError(f"transition claim interdite: {parsed_claim.status.value}")
    return Claim(
        claim_id=parsed_claim.claim_id,
        claim_version=parsed_claim.claim_version,
        status=status,
        claim_type=parsed_claim.claim_type,
        canonical_proposition=parsed_claim.canonical_proposition,
        scope=parsed_claim.scope,
        conditions=parsed_claim.conditions,
        limitations=parsed_claim.limitations,
        evidence_associations=parsed_claim.evidence_associations,
    )


def _ensure_report(value: IndependentVerificationReport) -> IndependentVerificationReport:
    if not isinstance(value, IndependentVerificationReport):
        raise ValueError("verification_report invalide")
    return value


def _ensure_case(value: VerificationCase) -> VerificationCase:
    if not isinstance(value, VerificationCase):
        raise ValueError("verification_case invalide")
    return value


def _ensure_claim(value: Claim) -> Claim:
    if not isinstance(value, Claim):
        raise ValueError("claim invalide")
    return value


def _ensure_claim_scope(value: ClaimScope) -> ClaimScope:
    if not isinstance(value, ClaimScope):
        raise ValueError("claim_scope invalide")
    return value


def _ensure_claim_scopes(value: Sequence[ClaimScope]) -> tuple[ClaimScope, ...]:
    if value is None:
        raise ValueError(ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE.value)
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_scopes invalides")
    scopes = tuple(value)
    if len(scopes) == 0:
        raise ValueError(ReasonCode.CLAIM_SCOPE_EXCEEDS_EVIDENCE.value)
    for scope in scopes:
        _ensure_claim_scope(scope)
    return scopes


def _ensure_direct_associations(
    value: Sequence[EvidenceAssociation],
) -> tuple[EvidenceAssociation, ...]:
    if value is None:
        raise ValueError("evidence_associations absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_associations invalides")
    associations = tuple(value)
    if len(associations) == 0:
        raise ValueError(ReasonCode.INSUFFICIENT_DIRECT_EVIDENCE.value)
    for association in associations:
        if not isinstance(association, EvidenceAssociation):
            raise ValueError("evidence_association invalide")
        if association.relation != SUPPORTS_DIRECTLY_RELATION:
            raise ValueError(ReasonCode.INSUFFICIENT_DIRECT_EVIDENCE.value)
    return associations


def _ensure_evidence_scope_mapping(
    value: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, ClaimScope]:
    if not isinstance(value, Mapping):
        raise ValueError("evidence_scopes non objet")
    parsed: dict[str, ClaimScope] = {}
    for evidence_id, scope_payload in value.items():
        parsed[_ensure_evidence_id(evidence_id)] = ClaimScope.from_payload(scope_payload)
    return MappingProxyType(parsed)


def _ensure_reason_codes(value: Sequence[ReasonCode]) -> tuple[ReasonCode, ...]:
    if value is None:
        raise ValueError("reason_codes absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("reason_codes invalides")
    reason_codes = tuple(value)
    for reason_code in reason_codes:
        if not isinstance(reason_code, ReasonCode):
            raise ValueError("reason_code invalide")
    return reason_codes


def _ensure_non_empty_reason_codes(value: Sequence[ReasonCode]) -> tuple[ReasonCode, ...]:
    reason_codes = _ensure_reason_codes(value)
    if len(reason_codes) == 0:
        raise ValueError("reason_codes vides")
    return reason_codes


def _merge_reason_codes(*groups: Sequence[ReasonCode]) -> tuple[ReasonCode, ...]:
    merged: list[ReasonCode] = []
    for group in groups:
        for reason_code in _ensure_reason_codes(group):
            if reason_code not in merged:
                merged.append(reason_code)
    if len(merged) == 0:
        raise ValueError("reason_codes vides")
    return tuple(merged)


def _ensure_evidence_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("accepted_evidence_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("accepted_evidence_ids invalides")
    evidence_ids = tuple(_ensure_evidence_id(item) for item in value)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("accepted_evidence_ids dupliques")
    return evidence_ids


def _ensure_evidence_id(value: Any) -> str:
    text = _ensure_text(value, "evidence_id")
    if not text.startswith("EVS-"):
        raise ValueError("evidence_id invalide")
    return text


def _ensure_dependency_group_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("dependency_group_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("dependency_group_ids invalides")
    dependency_group_ids = tuple(_ensure_dependency_group_id(item) for item in value)
    if len(dependency_group_ids) == 0:
        raise ValueError("dependency_group_ids vides")
    if len(dependency_group_ids) != len(set(dependency_group_ids)):
        raise ValueError("dependency_group_ids dupliques")
    return dependency_group_ids


def _ensure_dependency_group_id(value: Any) -> str:
    text = _ensure_text(value, "dependency_group_id")
    if _DEPENDENCY_GROUP_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("dependency_group_id invalide")
    return text


def _ensure_claim_id(value: Any) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_verification_case_id(value: Any) -> str:
    text = _ensure_text(value, "verification_case_id")
    if _VERIFICATION_CASE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("verification_case_id invalide")
    return text


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_optional_score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("calibrated_score invalide")
    return float(value)


def _ensure_utc_instant(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


__all__ = [
    "ClaimRejected",
    "ClaimSubmittedForVerification",
    "ClaimVerificationPolicy",
    "ClaimVerificationPolicyDecision",
    "ClaimVerified",
    "IndependentVerificationReport",
    "ReasonCode",
    "ScopePreservationPolicy",
    "VerificationCase",
    "VerificationDecision",
    "VerificationDecisionRecorded",
    "VerificationVerdict",
    "transition_claim_to",
]
