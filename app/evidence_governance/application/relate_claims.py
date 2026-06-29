"""Cas d'usage EG de relation entre versions de claims."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.evidence_governance.application.attach_evidence import ClaimRepository
from app.evidence_governance.domain.claim_evidence import Claim
from app.evidence_governance.domain.claim_relation import (
    ClaimRelation,
    ClaimRelationPolicy,
    ClaimRelationRecorded,
    ClaimRelationType,
    ClaimVersionRef,
)


_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_RELATION_ID_PATTERN = re.compile(r"^REL-[A-Z0-9][A-Z0-9-]*$")


class ClaimRelationRepository(Protocol):
    """Port de stockage des relations entre versions de claims."""

    def save(self, claim_relation: ClaimRelation) -> ClaimRelation:
        """Enregistre une relation immutable."""

    def relations_between(
        self,
        *,
        source_claim_id: str,
        target_claim_id: str,
    ) -> tuple[ClaimRelation, ...]:
        """Retourne les relations connues entre deux claims."""

    def has_path(
        self,
        *,
        source_claim_ref: ClaimVersionRef,
        target_claim_ref: ClaimVersionRef,
    ) -> bool:
        """Indique si un chemin relationnel existe deja."""


@dataclass(frozen=True)
class RelateClaims:
    """Commande explicite de relation entre deux versions de claims."""

    relation_id: str
    source_claim_id: str
    source_claim_version: int
    target_claim_id: str
    target_claim_version: int
    requested_relation_type: ClaimRelationType
    relation_basis: str
    policy_version: str
    occurred_at: str
    cycle_justification: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", _ensure_relation_id(self.relation_id))
        object.__setattr__(self, "source_claim_id", _ensure_claim_id(self.source_claim_id))
        object.__setattr__(
            self,
            "source_claim_version",
            _ensure_positive_integer(self.source_claim_version, "source_claim_version"),
        )
        object.__setattr__(self, "target_claim_id", _ensure_claim_id(self.target_claim_id))
        object.__setattr__(
            self,
            "target_claim_version",
            _ensure_positive_integer(self.target_claim_version, "target_claim_version"),
        )
        if not isinstance(self.requested_relation_type, ClaimRelationType):
            raise ValueError("relation_type invalide")
        object.__setattr__(self, "relation_basis", _ensure_text(self.relation_basis, "relation_basis"))
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))
        if self.cycle_justification is not None:
            object.__setattr__(
                self,
                "cycle_justification",
                _ensure_text(self.cycle_justification, "cycle_justification"),
            )


@dataclass(frozen=True)
class RelateClaimsResult:
    """Resultat observable d'une relation enregistree."""

    status: str
    relation: ClaimRelation
    events: Sequence[ClaimRelationRecorded]

    def __post_init__(self) -> None:
        status = _ensure_text(self.status, "status")
        if status != "CLAIM_RELATION_RECORDED":
            raise ValueError("status relation claim invalide")
        object.__setattr__(self, "status", status)
        if not isinstance(self.relation, ClaimRelation):
            raise ValueError("claim_relation invalide")
        object.__setattr__(self, "events", _ensure_events(self.events))


@dataclass(frozen=True)
class RelateClaimsHandler:
    """Orchestre les relations sans inferer par similarite textuelle."""

    claim_repository: ClaimRepository
    claim_relation_repository: ClaimRelationRepository
    policy: ClaimRelationPolicy

    def __init__(
        self,
        *,
        claim_repository: ClaimRepository,
        claim_relation_repository: ClaimRelationRepository,
    ) -> None:
        if not callable(getattr(claim_repository, "claim_for_id", None)):
            raise ValueError("claim_repository sans claim_for_id")
        if not callable(getattr(claim_relation_repository, "save", None)):
            raise ValueError("claim_relation_repository sans save")
        if not callable(getattr(claim_relation_repository, "relations_between", None)):
            raise ValueError("claim_relation_repository sans relations_between")
        if not callable(getattr(claim_relation_repository, "has_path", None)):
            raise ValueError("claim_relation_repository sans has_path")
        object.__setattr__(self, "claim_repository", claim_repository)
        object.__setattr__(self, "claim_relation_repository", claim_relation_repository)
        object.__setattr__(self, "policy", ClaimRelationPolicy())

    def relate(self, command: RelateClaims) -> RelateClaimsResult:
        parsed_command = _ensure_command(command)
        source_claim = self.claim_repository.claim_for_id(parsed_command.source_claim_id)
        target_claim = self.claim_repository.claim_for_id(parsed_command.target_claim_id)
        _ensure_claim_version(source_claim, parsed_command.source_claim_version)
        _ensure_claim_version(target_claim, parsed_command.target_claim_version)

        source_ref = ClaimVersionRef(
            claim_id=source_claim.claim_id,
            claim_version=source_claim.claim_version,
        )
        target_ref = ClaimVersionRef(
            claim_id=target_claim.claim_id,
            claim_version=target_claim.claim_version,
        )
        if (
            self.claim_relation_repository.has_path(
                source_claim_ref=target_ref,
                target_claim_ref=source_ref,
            )
            and parsed_command.cycle_justification is None
        ):
            raise ValueError("cycle relation claim interdit")

        decision = self.policy.evaluate(
            source_claim=source_claim,
            target_claim=target_claim,
            requested_relation_type=parsed_command.requested_relation_type,
            relation_basis=parsed_command.relation_basis,
        )
        relation = ClaimRelation(
            relation_id=parsed_command.relation_id,
            source_claim_ref=source_ref,
            target_claim_ref=target_ref,
            relation_type=decision.relation_type,
            scope_compatibility=decision.scope_compatibility,
            relation_basis=parsed_command.relation_basis,
            policy_version=parsed_command.policy_version,
            recorded_at=parsed_command.occurred_at,
            cycle_justification=parsed_command.cycle_justification,
        )
        saved_relation = self.claim_relation_repository.save(relation)
        return RelateClaimsResult(
            status="CLAIM_RELATION_RECORDED",
            relation=saved_relation,
            events=(ClaimRelationRecorded.from_relation(saved_relation),),
        )


def _ensure_command(value: RelateClaims) -> RelateClaims:
    if not isinstance(value, RelateClaims):
        raise ValueError("command relation claim invalide")
    return value


def _ensure_claim_version(claim: Claim, claim_version: int) -> None:
    if not isinstance(claim, Claim):
        raise ValueError("claim invalide")
    parsed_version = _ensure_positive_integer(claim_version, "claim_version")
    if claim.claim_version != parsed_version:
        raise ValueError("claim_version incoherente")


def _ensure_events(value: Sequence[ClaimRelationRecorded]) -> tuple[ClaimRelationRecorded, ...]:
    if value is None:
        raise ValueError("events absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, ClaimRelationRecorded):
            raise ValueError("event relation claim invalide")
    return events


def _ensure_claim_id(value: object) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_relation_id(value: object) -> str:
    text = _ensure_text(value, "relation_id")
    if _RELATION_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("relation_id invalide")
    return text


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: object) -> str:
    text = _ensure_text(value, "occurred_at")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError("occurred_at invalide")
    return text


__all__ = [
    "ClaimRelationRepository",
    "RelateClaims",
    "RelateClaimsHandler",
    "RelateClaimsResult",
]
