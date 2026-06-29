"""Attachement de preuves admissibles aux claims EG."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.contracts.evidence_claims import EvidenceRef, SUPPORTS_DIRECTLY_RELATION, VerifiedClaimRef
from app.contracts.source_references import SourceLocator
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
    ClaimScope,
    DraftClaim,
    Limitation,
)


_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_HASH_HEX_ALPHABET = frozenset("0123456789abcdef")
_ATTACHABLE_STATUSES = frozenset({"DRAFT", "EVIDENCE_ATTACHED"})
_SUPERSEDABLE_STATUSES = frozenset({"EVIDENCE_ATTACHED", "VERIFIED"})


class ClaimStatus(str, Enum):
    """Etat metier public d'un claim EG."""

    DRAFT = "DRAFT"
    EVIDENCE_ATTACHED = "EVIDENCE_ATTACHED"
    UNDER_VERIFICATION = "UNDER_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True)
class CanonicalEvidenceSpan:
    """Span canonique resolu par SourceLocator."""

    source_locator: SourceLocator
    quoted_span_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        object.__setattr__(
            self,
            "quoted_span_hash",
            _ensure_sha256(self.quoted_span_hash, "quoted_span_hash"),
        )


@dataclass(frozen=True)
class EvidenceAssociation:
    """Lien explicite entre un claim et une preuve admissible."""

    evidence_ref: EvidenceRef
    relation: str
    source_locator: SourceLocator
    quoted_span_hash: str

    @classmethod
    def from_evidence_ref(cls, evidence_ref: EvidenceRef) -> "EvidenceAssociation":
        parsed_evidence_ref = _ensure_evidence_ref(evidence_ref)
        return cls(
            evidence_ref=parsed_evidence_ref,
            relation=parsed_evidence_ref.relation,
            source_locator=parsed_evidence_ref.source_locator,
            quoted_span_hash=parsed_evidence_ref.quoted_span_hash,
        )

    def __post_init__(self) -> None:
        parsed_evidence_ref = _ensure_evidence_ref(self.evidence_ref)
        object.__setattr__(self, "relation", _ensure_text(self.relation, "relation"))
        if self.relation != parsed_evidence_ref.relation:
            raise ValueError("relation incoherente avec EvidenceRef")
        if self.relation != SUPPORTS_DIRECTLY_RELATION:
            raise ValueError(f"relation non autorisee: {self.relation}")
        if not isinstance(self.source_locator, SourceLocator):
            raise ValueError("source_locator invalide")
        if self.source_locator != parsed_evidence_ref.source_locator:
            raise ValueError("source_locator incoherent avec EvidenceRef")
        object.__setattr__(
            self,
            "quoted_span_hash",
            _ensure_sha256(self.quoted_span_hash, "quoted_span_hash"),
        )
        if self.quoted_span_hash != parsed_evidence_ref.quoted_span_hash:
            raise ValueError("quoted_span_hash incoherent avec EvidenceRef")

    def to_payload(self) -> dict[str, Any]:
        return {
            "evidence_ref": self.evidence_ref.to_payload(),
            "relation": self.relation,
            "source_locator": self.source_locator.to_payload(),
            "quoted_span_hash": self.quoted_span_hash,
        }


@dataclass(frozen=True)
class SupersededBy:
    """Lien explicite vers la version qui remplace une version de claim."""

    claim_id: str
    claim_version: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_version": self.claim_version,
        }


class EvidenceAdmissibilityPolicy:
    """Politique d'admission des preuves directes et resolubles."""

    def association_for(
        self,
        *,
        evidence_ref: EvidenceRef,
        canonical_evidence_reader: Any,
    ) -> EvidenceAssociation:
        parsed_evidence_ref = _ensure_evidence_ref(evidence_ref)
        if parsed_evidence_ref.relation != SUPPORTS_DIRECTLY_RELATION:
            raise ValueError(f"relation non autorisee: {parsed_evidence_ref.relation}")
        if not callable(getattr(canonical_evidence_reader, "resolve", None)):
            raise ValueError("canonical_evidence_reader sans resolve")

        canonical_span = canonical_evidence_reader.resolve(parsed_evidence_ref.source_locator)
        if not isinstance(canonical_span, CanonicalEvidenceSpan):
            raise ValueError("span canonique invalide")
        if canonical_span.source_locator != parsed_evidence_ref.source_locator:
            raise ValueError("source_locator incoherent")
        if canonical_span.quoted_span_hash != parsed_evidence_ref.quoted_span_hash:
            raise ValueError("quoted_span_hash incoherent")

        return EvidenceAssociation.from_evidence_ref(parsed_evidence_ref)


@dataclass(frozen=True)
class Claim:
    """Agregat EG qui protege l'attachement des preuves."""

    claim_id: str
    claim_version: int
    status: ClaimStatus
    claim_type: str
    canonical_proposition: CanonicalProposition
    scope: ClaimScope
    conditions: tuple[ClaimCondition, ...]
    limitations: tuple[Limitation, ...]
    evidence_associations: tuple[EvidenceAssociation, ...]
    verified_claim_ref: VerifiedClaimRef | None = None
    accepted_verification_id: str | None = None
    rejection_reason_codes: tuple[str, ...] = ()
    rejected_at: str | None = None
    superseded_by: SupersededBy | None = None
    supersession_reason: str | None = None
    superseded_at: str | None = None

    @classmethod
    def from_draft(cls, draft_claim: DraftClaim) -> "Claim":
        if not isinstance(draft_claim, DraftClaim):
            raise ValueError("draft_claim invalide")
        return cls(
            claim_id=draft_claim.claim_id,
            claim_version=draft_claim.claim_version,
            status=ClaimStatus.DRAFT,
            claim_type=draft_claim.claim_type,
            canonical_proposition=draft_claim.canonical_proposition,
            scope=draft_claim.scope,
            conditions=draft_claim.conditions,
            limitations=draft_claim.limitations,
            evidence_associations=(),
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        if not isinstance(self.status, ClaimStatus):
            raise ValueError("status claim invalide")
        object.__setattr__(self, "claim_type", _ensure_text(self.claim_type, "claim_type"))
        if not isinstance(self.canonical_proposition, CanonicalProposition):
            raise ValueError("canonical_proposition invalide")
        if not isinstance(self.scope, ClaimScope):
            raise ValueError("scope invalide")
        object.__setattr__(self, "conditions", _ensure_conditions(self.conditions))
        object.__setattr__(self, "limitations", _ensure_limitations(self.limitations))
        object.__setattr__(
            self,
            "evidence_associations",
            _ensure_evidence_associations(self.evidence_associations),
        )
        if self.verified_claim_ref is not None and not isinstance(
            self.verified_claim_ref,
            VerifiedClaimRef,
        ):
            raise ValueError("verified_claim_ref invalide")
        if self.accepted_verification_id is not None:
            object.__setattr__(
                self,
                "accepted_verification_id",
                _ensure_verification_case_id(self.accepted_verification_id),
            )
        object.__setattr__(
            self,
            "rejection_reason_codes",
            _ensure_rejection_reason_codes(self.rejection_reason_codes),
        )
        if self.rejected_at is not None:
            object.__setattr__(self, "rejected_at", _ensure_utc_instant(self.rejected_at))
        if self.superseded_by is not None and not isinstance(self.superseded_by, SupersededBy):
            raise ValueError("superseded_by invalide")
        if self.supersession_reason is not None:
            object.__setattr__(
                self,
                "supersession_reason",
                _ensure_text(self.supersession_reason, "supersession_reason"),
            )
        if self.superseded_at is not None:
            object.__setattr__(self, "superseded_at", _ensure_utc_instant(self.superseded_at))
        self._ensure_status_decision_fields()

    def propose_evidence(
        self,
        *,
        evidence_ref: EvidenceRef,
        canonical_evidence_reader: Any,
        occurred_at: str,
    ) -> tuple["Claim", "EvidenceAttachedToClaim"]:
        if self.status.value not in _ATTACHABLE_STATUSES:
            raise ValueError(f"transition claim interdite: {self.status.value}")

        association = EvidenceAdmissibilityPolicy().association_for(
            evidence_ref=evidence_ref,
            canonical_evidence_reader=canonical_evidence_reader,
        )
        if self._has_evidence_association(association):
            raise ValueError("evidence_ref duplique")

        updated_claim = Claim(
            claim_id=self.claim_id,
            claim_version=self.claim_version,
            status=ClaimStatus.EVIDENCE_ATTACHED,
            claim_type=self.claim_type,
            canonical_proposition=self.canonical_proposition,
            scope=self.scope,
            conditions=self.conditions,
            limitations=self.limitations,
            evidence_associations=(*self.evidence_associations, association),
        )
        return (
            updated_claim,
            EvidenceAttachedToClaim.from_association(
                claim=updated_claim,
                association=association,
                occurred_at=occurred_at,
            ),
        )

    def supersede_with(
        self,
        *,
        superseding_claim: "Claim",
        supersession_reason: str,
        occurred_at: str,
    ) -> tuple["Claim", "ClaimSuperseded"]:
        if self.status.value not in _SUPERSEDABLE_STATUSES:
            raise ValueError(f"transition claim interdite: {self.status.value}")
        parsed_superseding_claim = _ensure_claim(superseding_claim)
        if parsed_superseding_claim.claim_id != self.claim_id:
            raise ValueError("claim_id supersession incoherent")
        if parsed_superseding_claim.claim_version != self.claim_version + 1:
            raise ValueError("claim_version supersession invalide")
        if parsed_superseding_claim.status in {
            ClaimStatus.REJECTED,
            ClaimStatus.SUPERSEDED,
            ClaimStatus.ABANDONED,
        }:
            raise ValueError(f"superseding_claim status invalide: {parsed_superseding_claim.status.value}")
        if (
            parsed_superseding_claim.canonical_proposition.text
            == self.canonical_proposition.text
        ):
            raise ValueError("proposition supersession identique")

        reason = _ensure_text(supersession_reason, "supersession_reason")
        instant = _ensure_utc_instant(occurred_at)
        superseded_claim = Claim(
            claim_id=self.claim_id,
            claim_version=self.claim_version,
            status=ClaimStatus.SUPERSEDED,
            claim_type=self.claim_type,
            canonical_proposition=self.canonical_proposition,
            scope=self.scope,
            conditions=self.conditions,
            limitations=self.limitations,
            evidence_associations=self.evidence_associations,
            verified_claim_ref=self.verified_claim_ref,
            accepted_verification_id=self.accepted_verification_id,
            rejection_reason_codes=self.rejection_reason_codes,
            rejected_at=self.rejected_at,
            superseded_by=SupersededBy(
                claim_id=parsed_superseding_claim.claim_id,
                claim_version=parsed_superseding_claim.claim_version,
            ),
            supersession_reason=reason,
            superseded_at=instant,
        )
        return (
            superseded_claim,
            ClaimSuperseded.from_claims(
                superseded_claim=superseded_claim,
                superseding_claim=parsed_superseding_claim,
                occurred_at=instant,
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "claim_id": self.claim_id,
            "claim_version": self.claim_version,
            "status": self.status.value,
            "claim_type": self.claim_type,
            "canonical_proposition": {
                "text": self.canonical_proposition.text,
                "hash": _sha256_text(self.canonical_proposition.text),
            },
            "scope": self.scope.to_payload(),
            "conditions": tuple(condition.text for condition in self.conditions),
            "limitations": tuple(limitation.text for limitation in self.limitations),
            "evidence_associations": tuple(
                association.to_payload() for association in self.evidence_associations
            ),
        }
        if self.verified_claim_ref is not None:
            payload["verified_claim_ref"] = self.verified_claim_ref.to_payload()
        if self.accepted_verification_id is not None:
            payload["accepted_verification_id"] = self.accepted_verification_id
        if self.rejection_reason_codes:
            payload["rejection_reason_codes"] = self.rejection_reason_codes
        if self.rejected_at is not None:
            payload["rejected_at"] = self.rejected_at
        if self.superseded_by is not None:
            payload["superseded_by"] = self.superseded_by.to_payload()
        if self.supersession_reason is not None:
            payload["supersession_reason"] = self.supersession_reason
        if self.superseded_at is not None:
            payload["superseded_at"] = self.superseded_at
        return payload

    def _has_evidence_association(self, association: EvidenceAssociation) -> bool:
        return any(
            existing.evidence_ref.evidence_id == association.evidence_ref.evidence_id
            or (
                existing.source_locator == association.source_locator
                and existing.quoted_span_hash == association.quoted_span_hash
            )
            for existing in self.evidence_associations
        )

    def _ensure_status_decision_fields(self) -> None:
        if self.status == ClaimStatus.VERIFIED:
            if (self.verified_claim_ref is None) != (self.accepted_verification_id is None):
                raise ValueError("verification acceptee incomplete")
            if self.rejection_reason_codes:
                raise ValueError("reason_codes incompatibles avec VERIFIED")
            if self.rejected_at is not None:
                raise ValueError("rejected_at incompatible avec VERIFIED")
            if self.superseded_by is not None:
                raise ValueError("superseded_by incompatible avec VERIFIED")
        elif self.status == ClaimStatus.REJECTED:
            if len(self.rejection_reason_codes) == 0:
                raise ValueError("reason_codes requis")
            if self.rejected_at is None:
                raise ValueError("rejected_at requis")
            if self.verified_claim_ref is not None or self.accepted_verification_id is not None:
                raise ValueError("verification acceptee incompatible avec REJECTED")
            if self.superseded_by is not None:
                raise ValueError("superseded_by incompatible avec REJECTED")
        elif self.status == ClaimStatus.SUPERSEDED:
            if self.superseded_by is None:
                raise ValueError("superseded_by absent")
            if self.supersession_reason is None:
                raise ValueError("supersession_reason requis")
            if self.superseded_at is None:
                raise ValueError("superseded_at requis")
        else:
            if self.verified_claim_ref is not None or self.accepted_verification_id is not None:
                raise ValueError("verification acceptee incompatible avec status courant")
            if self.rejection_reason_codes:
                raise ValueError("reason_codes incompatibles avec status courant")
            if self.rejected_at is not None:
                raise ValueError("rejected_at incompatible avec status courant")
            if self.superseded_by is not None:
                raise ValueError("superseded_by incompatible avec status courant")
            if self.supersession_reason is not None or self.superseded_at is not None:
                raise ValueError("supersession incompatible avec status courant")


@dataclass(frozen=True)
class EvidenceAttachedToClaim:
    """Evenement publie quand une preuve admissible est attachee."""

    claim_id: str
    claim_version: int
    evidence_ref: EvidenceRef
    evidence_relation: str
    occurred_at: str

    @classmethod
    def from_association(
        cls,
        *,
        claim: Claim,
        association: EvidenceAssociation,
        occurred_at: str,
    ) -> "EvidenceAttachedToClaim":
        parsed_claim = _ensure_claim(claim)
        if not isinstance(association, EvidenceAssociation):
            raise ValueError("evidence_association invalide")
        return cls(
            claim_id=parsed_claim.claim_id,
            claim_version=parsed_claim.claim_version,
            evidence_ref=association.evidence_ref,
            evidence_relation=association.relation,
            occurred_at=occurred_at,
        )

    @property
    def event_type(self) -> str:
        return "EvidenceAttachedToClaim"

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        object.__setattr__(self, "evidence_ref", _ensure_evidence_ref(self.evidence_ref))
        object.__setattr__(
            self,
            "evidence_relation",
            _ensure_text(self.evidence_relation, "evidence_relation"),
        )
        if self.evidence_relation != self.evidence_ref.relation:
            raise ValueError("evidence_relation incoherente avec EvidenceRef")
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "claim_id": self.claim_id,
                "claim_version": self.claim_version,
                "evidence_ref": self.evidence_ref.to_payload(),
                "evidence_relation": self.evidence_relation,
            },
        }


@dataclass(frozen=True)
class ClaimSuperseded:
    """Evenement publie quand une version de claim est remplacee sans effacement."""

    old_claim_ref: SupersededBy
    new_claim_ref: SupersededBy
    supersession_reason: str
    occurred_at: str

    @classmethod
    def from_claims(
        cls,
        *,
        superseded_claim: Claim,
        superseding_claim: Claim,
        occurred_at: str,
    ) -> "ClaimSuperseded":
        parsed_superseded_claim = _ensure_claim(superseded_claim)
        parsed_superseding_claim = _ensure_claim(superseding_claim)
        if parsed_superseded_claim.status != ClaimStatus.SUPERSEDED:
            raise ValueError(f"transition claim interdite: {parsed_superseded_claim.status.value}")
        if parsed_superseded_claim.superseded_by is None:
            raise ValueError("superseded_by absent")
        if parsed_superseded_claim.superseded_by != SupersededBy(
            claim_id=parsed_superseding_claim.claim_id,
            claim_version=parsed_superseding_claim.claim_version,
        ):
            raise ValueError("superseded_by incoherent")
        if parsed_superseded_claim.supersession_reason is None:
            raise ValueError("supersession_reason requis")
        return cls(
            old_claim_ref=SupersededBy(
                claim_id=parsed_superseded_claim.claim_id,
                claim_version=parsed_superseded_claim.claim_version,
            ),
            new_claim_ref=parsed_superseded_claim.superseded_by,
            supersession_reason=parsed_superseded_claim.supersession_reason,
            occurred_at=occurred_at,
        )

    @property
    def event_type(self) -> str:
        return "ClaimSuperseded"

    def __post_init__(self) -> None:
        if not isinstance(self.old_claim_ref, SupersededBy):
            raise ValueError("old_claim_ref invalide")
        if not isinstance(self.new_claim_ref, SupersededBy):
            raise ValueError("new_claim_ref invalide")
        object.__setattr__(
            self,
            "supersession_reason",
            _ensure_text(self.supersession_reason, "supersession_reason"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "old_claim_ref": self.old_claim_ref.to_payload(),
                "new_claim_ref": self.new_claim_ref.to_payload(),
                "supersession_reason": self.supersession_reason,
            },
        }


def _ensure_claim(value: Claim) -> Claim:
    if not isinstance(value, Claim):
        raise ValueError("claim invalide")
    return value


def _ensure_evidence_ref(value: EvidenceRef) -> EvidenceRef:
    if not isinstance(value, EvidenceRef):
        raise ValueError("evidence_ref invalide")
    return value


def _ensure_claim_id(value: Any) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_verification_case_id(value: Any) -> str:
    text = _ensure_text(value, "accepted_verification_id")
    if not text.startswith("VER-"):
        raise ValueError("accepted_verification_id invalide")
    return text


def _ensure_rejection_reason_codes(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("reason_codes absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("reason_codes invalides")
    reason_codes = tuple(_ensure_text(reason_code, "reason_code") for reason_code in value)
    if len(reason_codes) != len(set(reason_codes)):
        raise ValueError("reason_codes dupliques")
    return reason_codes


def _ensure_conditions(value: Sequence[ClaimCondition]) -> tuple[ClaimCondition, ...]:
    if value is None:
        raise ValueError("conditions absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("conditions invalides")
    conditions = tuple(value)
    for condition in conditions:
        if not isinstance(condition, ClaimCondition):
            raise ValueError("condition invalide")
    return conditions


def _ensure_limitations(value: Sequence[Limitation]) -> tuple[Limitation, ...]:
    if value is None:
        raise ValueError("limitations absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("limitations invalides")
    limitations = tuple(value)
    for limitation in limitations:
        if not isinstance(limitation, Limitation):
            raise ValueError("limitation invalide")
    return limitations


def _ensure_evidence_associations(
    value: Sequence[EvidenceAssociation],
) -> tuple[EvidenceAssociation, ...]:
    if value is None:
        raise ValueError("evidence_associations absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("evidence_associations invalides")
    associations = tuple(value)
    for association in associations:
        if not isinstance(association, EvidenceAssociation):
            raise ValueError("evidence_association invalide")
    evidence_ids = tuple(association.evidence_ref.evidence_id for association in associations)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("evidence_ref duplique")
    source_spans = tuple(
        (
            association.source_locator,
            association.quoted_span_hash,
        )
        for association in associations
    )
    if len(source_spans) != len(set(source_spans)):
        raise ValueError("evidence_ref duplique")
    return associations


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


def _ensure_sha256(value: Any, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if len(text) != 64:
        raise ValueError(f"{field_name} invalide")
    for character in text:
        if character not in _HASH_HEX_ALPHABET:
            raise ValueError(f"{field_name} invalide")
    return text


def _ensure_utc_instant(value: Any) -> str:
    text = _ensure_text(value, "occurred_at")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError("occurred_at invalide")
    return text


def _sha256_text(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "text").encode("utf-8")).hexdigest()


__all__ = [
    "CanonicalEvidenceSpan",
    "Claim",
    "ClaimSuperseded",
    "ClaimStatus",
    "EvidenceAdmissibilityPolicy",
    "EvidenceAssociation",
    "EvidenceAttachedToClaim",
    "SupersededBy",
]
