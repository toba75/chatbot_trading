"""Cas d'usage EG pour les groupes de dépendance de preuves."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.evidence_governance.application.attach_evidence import ClaimRepository
from app.evidence_governance.domain.claim_evidence import Claim, ClaimStatus
from app.evidence_governance.domain.dependency_group import (
    ClaimDependencyAssigned,
    ClaimDependencyAssignment,
    DependencyGroup,
    IndependentSupportCount,
    SourceIndependencePolicy,
)


_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_EVIDENCE_ID_PATTERN = re.compile(r"^EVS-[A-Z0-9][A-Z0-9-]*$")
_DEPENDENCY_GROUP_ID_PATTERN = re.compile(r"^DEP-[A-Z0-9][A-Z0-9-]*$")


@runtime_checkable
class DependencyGroupRepository(Protocol):
    """Port de stockage des groupes de dépendance EG explicites."""

    def save(self, dependency_group: DependencyGroup) -> DependencyGroup:
        """Enregistre un groupe sans suppression implicite d'affectations."""

    def group_for_id(self, dependency_group_id: str) -> DependencyGroup:
        """Retourne un groupe existant."""

    def groups_for_claim(self, claim_id: str) -> tuple[DependencyGroup, ...]:
        """Retourne les groupes explicitement affectés à un claim."""

    def assignment_for_claim_evidence(
        self,
        *,
        claim_id: str,
        claim_version: int,
        evidence_id: str,
    ) -> ClaimDependencyAssignment | None:
        """Retourne l'affectation explicite d'une preuve de claim quand elle existe."""


@dataclass(frozen=True)
class AssignClaimDependencyGroup:
    """Commande explicite d'affectation d'une preuve de claim à un DependencyGroup."""

    claim_id: str
    claim_version: int
    evidence_id: str
    dependency_group_id: str
    dependency_kind: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "claim_version",
            _ensure_positive_integer(self.claim_version, "claim_version"),
        )
        object.__setattr__(self, "evidence_id", _ensure_evidence_id(self.evidence_id))
        object.__setattr__(
            self,
            "dependency_group_id",
            _ensure_dependency_group_id(self.dependency_group_id),
        )
        object.__setattr__(
            self,
            "dependency_kind",
            _ensure_text(self.dependency_kind, "dependency_kind"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))


@dataclass(frozen=True)
class AssignClaimDependencyGroupResult:
    """Résultat observable d'une affectation acceptée."""

    status: str
    dependency_group: DependencyGroup
    events: Sequence[ClaimDependencyAssigned]

    def __post_init__(self) -> None:
        status = _ensure_text(self.status, "status")
        if status != "CLAIM_DEPENDENCY_ASSIGNED":
            raise ValueError("status dependency_group invalide")
        object.__setattr__(self, "status", status)
        if not isinstance(self.dependency_group, DependencyGroup):
            raise ValueError("dependency_group invalide")
        object.__setattr__(self, "events", _ensure_events(self.events))


@dataclass(frozen=True)
class AssignClaimDependencyGroupHandler:
    """Orchestre l'affectation sans inférer de dépendance documentaire."""

    claim_repository: ClaimRepository
    dependency_group_repository: DependencyGroupRepository

    def __init__(
        self,
        *,
        claim_repository: ClaimRepository,
        dependency_group_repository: DependencyGroupRepository,
    ) -> None:
        if not callable(getattr(claim_repository, "claim_for_id", None)):
            raise ValueError("claim_repository sans claim_for_id")
        if not callable(getattr(dependency_group_repository, "save", None)):
            raise ValueError("dependency_group_repository sans save")
        if not callable(getattr(dependency_group_repository, "group_for_id", None)):
            raise ValueError("dependency_group_repository sans group_for_id")
        if not callable(getattr(dependency_group_repository, "groups_for_claim", None)):
            raise ValueError("dependency_group_repository sans groups_for_claim")
        if not callable(
            getattr(dependency_group_repository, "assignment_for_claim_evidence", None)
        ):
            raise ValueError("dependency_group_repository sans assignment_for_claim_evidence")
        object.__setattr__(self, "claim_repository", claim_repository)
        object.__setattr__(self, "dependency_group_repository", dependency_group_repository)

    def assign(self, command: AssignClaimDependencyGroup) -> AssignClaimDependencyGroupResult:
        parsed_command = _ensure_command(command)
        claim = self.claim_repository.claim_for_id(parsed_command.claim_id)
        _ensure_claim_version(claim, parsed_command.claim_version)
        if claim.status == ClaimStatus.VERIFIED:
            raise ValueError("claim verifie non modifiable")
        _ensure_evidence_attached(claim, parsed_command.evidence_id)

        dependency_group = self.dependency_group_repository.group_for_id(
            parsed_command.dependency_group_id
        )
        if _dependency_group_used_by_verified_claim(
            dependency_group,
            claim_repository=self.claim_repository,
        ):
            raise ValueError(
                f"dependency_group utilise par claim verifie: {dependency_group.dependency_group_id}"
            )

        existing_assignment = self.dependency_group_repository.assignment_for_claim_evidence(
            claim_id=parsed_command.claim_id,
            claim_version=parsed_command.claim_version,
            evidence_id=parsed_command.evidence_id,
        )
        if existing_assignment is not None:
            raise ValueError("dependency_assignment duplique")

        updated_group, event = dependency_group.assign_claim_evidence(
            claim_id=parsed_command.claim_id,
            claim_version=parsed_command.claim_version,
            evidence_id=parsed_command.evidence_id,
            dependency_kind=parsed_command.dependency_kind,
            occurred_at=parsed_command.occurred_at,
        )
        saved_group = self.dependency_group_repository.save(updated_group)
        return AssignClaimDependencyGroupResult(
            status="CLAIM_DEPENDENCY_ASSIGNED",
            dependency_group=saved_group,
            events=(event,),
        )


@dataclass(frozen=True)
class CountIndependentSupport:
    """Requête applicative de comptage des confirmations indépendantes."""

    claim_repository: ClaimRepository
    dependency_group_repository: DependencyGroupRepository
    source_independence_policy: SourceIndependencePolicy

    def __init__(
        self,
        *,
        claim_repository: ClaimRepository,
        dependency_group_repository: DependencyGroupRepository,
    ) -> None:
        if not callable(getattr(claim_repository, "claim_for_id", None)):
            raise ValueError("claim_repository sans claim_for_id")
        if not callable(getattr(dependency_group_repository, "groups_for_claim", None)):
            raise ValueError("dependency_group_repository sans groups_for_claim")
        object.__setattr__(self, "claim_repository", claim_repository)
        object.__setattr__(self, "dependency_group_repository", dependency_group_repository)
        object.__setattr__(self, "source_independence_policy", SourceIndependencePolicy())

    def count(
        self,
        *,
        claim_id: str,
        accepted_evidence_ids: Sequence[str],
    ) -> IndependentSupportCount:
        parsed_claim_id = _ensure_claim_id(claim_id)
        parsed_evidence_ids = _ensure_evidence_ids(accepted_evidence_ids)
        claim = self.claim_repository.claim_for_id(parsed_claim_id)
        for evidence_id in parsed_evidence_ids:
            _ensure_evidence_attached(claim, evidence_id)
        return self.source_independence_policy.count_independent_support(
            claim_id=parsed_claim_id,
            accepted_evidence_ids=parsed_evidence_ids,
            dependency_groups=self.dependency_group_repository.groups_for_claim(parsed_claim_id),
        )


def _dependency_group_used_by_verified_claim(
    dependency_group: DependencyGroup,
    *,
    claim_repository: ClaimRepository,
) -> bool:
    parsed_group = _ensure_dependency_group(dependency_group)
    checked_claim_ids: list[str] = []
    for assignment in parsed_group.assignments:
        if assignment.claim_id in checked_claim_ids:
            continue
        checked_claim_ids.append(assignment.claim_id)
        assigned_claim = claim_repository.claim_for_id(assignment.claim_id)
        if assigned_claim.status == ClaimStatus.VERIFIED:
            return True
    return False


def _ensure_command(value: AssignClaimDependencyGroup) -> AssignClaimDependencyGroup:
    if not isinstance(value, AssignClaimDependencyGroup):
        raise ValueError("command dependency_group invalide")
    return value


def _ensure_dependency_group(value: DependencyGroup) -> DependencyGroup:
    if not isinstance(value, DependencyGroup):
        raise ValueError("dependency_group invalide")
    return value


def _ensure_claim_version(claim: Claim, claim_version: int) -> None:
    if not isinstance(claim, Claim):
        raise ValueError("claim invalide")
    parsed_claim_version = _ensure_positive_integer(claim_version, "claim_version")
    if claim.claim_version != parsed_claim_version:
        raise ValueError("claim_version incoherente")


def _ensure_evidence_attached(claim: Claim, evidence_id: str) -> None:
    parsed_evidence_id = _ensure_evidence_id(evidence_id)
    if not any(
        association.evidence_ref.evidence_id == parsed_evidence_id
        for association in claim.evidence_associations
    ):
        raise ValueError("evidence_ref non attachee au claim")


def _ensure_events(
    value: Sequence[ClaimDependencyAssigned],
) -> tuple[ClaimDependencyAssigned, ...]:
    if value is None:
        raise ValueError("events absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("events invalides")
    events = tuple(value)
    if len(events) == 0:
        raise ValueError("events absents")
    for event in events:
        if not isinstance(event, ClaimDependencyAssigned):
            raise ValueError("event dependency_group invalide")
    return events


def _ensure_evidence_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("accepted_evidence_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("accepted_evidence_ids invalides")
    evidence_ids = tuple(_ensure_evidence_id(item) for item in value)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("accepted_evidence_ids dupliques")
    return evidence_ids


def _ensure_claim_id(value: object) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_evidence_id(value: object) -> str:
    text = _ensure_text(value, "evidence_id")
    if _EVIDENCE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("evidence_id invalide")
    return text


def _ensure_dependency_group_id(value: object) -> str:
    text = _ensure_text(value, "dependency_group_id")
    if _DEPENDENCY_GROUP_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("dependency_group_id invalide")
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
    "AssignClaimDependencyGroup",
    "AssignClaimDependencyGroupHandler",
    "AssignClaimDependencyGroupResult",
    "CountIndependentSupport",
    "DependencyGroupRepository",
]
