"""Attachement de preuves admissibles aux claims EG."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.contracts.evidence_claims import EvidenceRef, SUPPORTS_DIRECTLY_RELATION
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

    def to_payload(self) -> dict[str, Any]:
        return {
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

    def _has_evidence_association(self, association: EvidenceAssociation) -> bool:
        return any(
            existing.evidence_ref.evidence_id == association.evidence_ref.evidence_id
            or (
                existing.source_locator == association.source_locator
                and existing.quoted_span_hash == association.quoted_span_hash
            )
            for existing in self.evidence_associations
        )


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
    "ClaimStatus",
    "EvidenceAdmissibilityPolicy",
    "EvidenceAssociation",
    "EvidenceAttachedToClaim",
]
