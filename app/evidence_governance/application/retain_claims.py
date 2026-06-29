"""Cas d'usage EG de conservation des versions de claims."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.evidence_governance.application.attach_evidence import ClaimRepository
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus, ClaimSuperseded
from app.evidence_governance.domain.claim_extraction import (
    CanonicalProposition,
    ClaimCondition,
    ClaimScope,
    Limitation,
)


@dataclass(frozen=True)
class SupersedeClaim:
    """Commande explicite de remplacement d'une version de claim."""

    superseded_claim_id: str
    superseded_claim_version: int
    superseding_claim_version: int
    canonical_proposition: CanonicalProposition
    scope: ClaimScope
    conditions: Sequence[ClaimCondition]
    limitations: Sequence[Limitation]
    supersession_reason: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "superseded_claim_id",
            _ensure_claim_id(self.superseded_claim_id),
        )
        object.__setattr__(
            self,
            "superseded_claim_version",
            _ensure_positive_integer(self.superseded_claim_version, "superseded_claim_version"),
        )
        object.__setattr__(
            self,
            "superseding_claim_version",
            _ensure_positive_integer(self.superseding_claim_version, "superseding_claim_version"),
        )
        if self.superseding_claim_version != self.superseded_claim_version + 1:
            raise ValueError("claim_version supersession invalide")
        if not isinstance(self.canonical_proposition, CanonicalProposition):
            raise ValueError("canonical_proposition invalide")
        if not isinstance(self.scope, ClaimScope):
            raise ValueError("scope invalide")
        object.__setattr__(self, "conditions", _ensure_conditions(self.conditions))
        object.__setattr__(self, "limitations", _ensure_limitations(self.limitations))
        object.__setattr__(
            self,
            "supersession_reason",
            _ensure_text(self.supersession_reason, "supersession_reason"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))


@dataclass(frozen=True)
class SupersedeClaimResult:
    """Résultat observable d'une supersession conservée."""

    status: str
    old_claim: Claim
    new_claim: Claim
    events: Sequence[ClaimSuperseded]

    def __post_init__(self) -> None:
        status = _ensure_text(self.status, "status")
        if status != "CLAIM_SUPERSEDED":
            raise ValueError("status supersession invalide")
        object.__setattr__(self, "status", status)
        if not isinstance(self.old_claim, Claim):
            raise ValueError("old_claim invalide")
        if not isinstance(self.new_claim, Claim):
            raise ValueError("new_claim invalide")
        object.__setattr__(self, "events", _ensure_events(self.events))


@dataclass(frozen=True)
class SupersedeClaimHandler:
    """Orchestre une supersession sans effacer la version remplacée."""

    claim_repository: ClaimRepository

    def __init__(self, *, claim_repository: ClaimRepository) -> None:
        if not callable(getattr(claim_repository, "claim_for_version", None)):
            raise ValueError("claim_repository sans claim_for_version")
        if not callable(getattr(claim_repository, "save", None)):
            raise ValueError("claim_repository sans save")
        object.__setattr__(self, "claim_repository", claim_repository)

    def supersede(self, command: SupersedeClaim) -> SupersedeClaimResult:
        parsed_command = _ensure_command(command)
        old_claim = self.claim_repository.claim_for_version(
            parsed_command.superseded_claim_id,
            parsed_command.superseded_claim_version,
        )
        new_claim = Claim(
            claim_id=old_claim.claim_id,
            claim_version=parsed_command.superseding_claim_version,
            status=_initial_status_for_superseding_claim(old_claim),
            claim_type=old_claim.claim_type,
            canonical_proposition=parsed_command.canonical_proposition,
            scope=parsed_command.scope,
            conditions=parsed_command.conditions,
            limitations=parsed_command.limitations,
            evidence_associations=old_claim.evidence_associations,
        )
        superseded_claim, event = old_claim.supersede_with(
            superseding_claim=new_claim,
            supersession_reason=parsed_command.supersession_reason,
            occurred_at=parsed_command.occurred_at,
        )
        saved_old_claim = self.claim_repository.save(superseded_claim)
        saved_new_claim = self.claim_repository.save(new_claim)
        return SupersedeClaimResult(
            status="CLAIM_SUPERSEDED",
            old_claim=saved_old_claim,
            new_claim=saved_new_claim,
            events=(event,),
        )


def _initial_status_for_superseding_claim(old_claim: Claim) -> ClaimStatus:
    if old_claim.evidence_associations:
        return ClaimStatus.EVIDENCE_ATTACHED
    return ClaimStatus.DRAFT


def _ensure_command(value: SupersedeClaim) -> SupersedeClaim:
    if not isinstance(value, SupersedeClaim):
        raise ValueError("command supersession invalide")
    return value


def _ensure_events(value: Sequence[ClaimSuperseded]) -> tuple[ClaimSuperseded, ...]:
    if value is None:
        raise ValueError("events absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, ClaimSuperseded):
            raise ValueError("event supersession invalide")
    return events


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


def _ensure_claim_id(value: object) -> str:
    text = _ensure_text(value, "claim_id")
    if not text.startswith("CLM-"):
        raise ValueError("claim_id invalide")
    return text


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


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
    "SupersedeClaim",
    "SupersedeClaimHandler",
    "SupersedeClaimResult",
]
