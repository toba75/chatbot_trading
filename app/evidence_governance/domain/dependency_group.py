"""Groupes de dépendance explicites pour les confirmations EG."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_EVIDENCE_ID_PATTERN = re.compile(r"^EVS-[A-Z0-9][A-Z0-9-]*$")
_DEPENDENCY_GROUP_ID_PATTERN = re.compile(r"^DEP-[A-Z0-9][A-Z0-9-]*$")
_ALLOWED_DEPENDENCY_KINDS = frozenset({"PRIMARY_STUDY", "SECONDARY_REPRISE"})


@dataclass(frozen=True)
class ClaimDependencyAssignment:
    """Affectation explicite d'une preuve de claim à une origine commune."""

    claim_id: str
    claim_version: int
    evidence_id: str
    dependency_group_id: str
    dependency_kind: str
    assigned_at: str

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
            _ensure_dependency_kind(self.dependency_kind),
        )
        object.__setattr__(self, "assigned_at", _ensure_utc_instant(self.assigned_at))

    def to_payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_version": self.claim_version,
            "evidence_id": self.evidence_id,
            "dependency_group_id": self.dependency_group_id,
            "dependency_kind": self.dependency_kind,
            "assigned_at": self.assigned_at,
        }


@dataclass(frozen=True)
class ClaimDependencyAssigned:
    """Événement publié quand une preuve est rattachée à un groupe explicite."""

    claim_id: str
    claim_version: int
    evidence_id: str
    dependency_group_id: str
    dependency_kind: str
    occurred_at: str

    @classmethod
    def from_assignment(
        cls,
        assignment: ClaimDependencyAssignment,
        *,
        occurred_at: str,
    ) -> "ClaimDependencyAssigned":
        parsed_assignment = _ensure_assignment(assignment)
        return cls(
            claim_id=parsed_assignment.claim_id,
            claim_version=parsed_assignment.claim_version,
            evidence_id=parsed_assignment.evidence_id,
            dependency_group_id=parsed_assignment.dependency_group_id,
            dependency_kind=parsed_assignment.dependency_kind,
            occurred_at=occurred_at,
        )

    @property
    def event_type(self) -> str:
        return "ClaimDependencyAssigned"

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
            _ensure_dependency_kind(self.dependency_kind),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "claim_id": self.claim_id,
                "claim_version": self.claim_version,
                "evidence_id": self.evidence_id,
                "dependency_group_id": self.dependency_group_id,
                "dependency_kind": self.dependency_kind,
            },
        }


@dataclass(frozen=True)
class DependencyGroup:
    """Origine intellectuelle ou empirique commune documentée explicitement."""

    dependency_group_id: str
    origin_label: str
    created_at: str
    assignments: Sequence[ClaimDependencyAssignment]

    @classmethod
    def create(
        cls,
        *,
        dependency_group_id: str,
        origin_label: str,
        created_at: str,
    ) -> "DependencyGroup":
        return cls(
            dependency_group_id=dependency_group_id,
            origin_label=origin_label,
            created_at=created_at,
            assignments=(),
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dependency_group_id",
            _ensure_dependency_group_id(self.dependency_group_id),
        )
        object.__setattr__(self, "origin_label", _ensure_text(self.origin_label, "origin_label"))
        object.__setattr__(self, "created_at", _ensure_utc_instant(self.created_at))
        object.__setattr__(
            self,
            "assignments",
            _ensure_assignments(self.assignments, self.dependency_group_id),
        )

    def assign_claim_evidence(
        self,
        *,
        claim_id: str,
        claim_version: int,
        evidence_id: str,
        dependency_kind: str,
        occurred_at: str,
    ) -> tuple["DependencyGroup", ClaimDependencyAssigned]:
        assignment = ClaimDependencyAssignment(
            claim_id=claim_id,
            claim_version=claim_version,
            evidence_id=evidence_id,
            dependency_group_id=self.dependency_group_id,
            dependency_kind=dependency_kind,
            assigned_at=occurred_at,
        )
        if self.has_assignment_for(
            claim_id=assignment.claim_id,
            claim_version=assignment.claim_version,
            evidence_id=assignment.evidence_id,
        ):
            raise ValueError("dependency_assignment duplique")
        updated_group = DependencyGroup(
            dependency_group_id=self.dependency_group_id,
            origin_label=self.origin_label,
            created_at=self.created_at,
            assignments=(*self.assignments, assignment),
        )
        return (
            updated_group,
            ClaimDependencyAssigned.from_assignment(
                assignment,
                occurred_at=occurred_at,
            ),
        )

    def has_assignment_for(
        self,
        *,
        claim_id: str,
        claim_version: int,
        evidence_id: str,
    ) -> bool:
        parsed_claim_id = _ensure_claim_id(claim_id)
        parsed_claim_version = _ensure_positive_integer(claim_version, "claim_version")
        parsed_evidence_id = _ensure_evidence_id(evidence_id)
        return any(
            assignment.claim_id == parsed_claim_id
            and assignment.claim_version == parsed_claim_version
            and assignment.evidence_id == parsed_evidence_id
            for assignment in self.assignments
        )

    def assignments_for_claim(self, claim_id: str) -> tuple[ClaimDependencyAssignment, ...]:
        parsed_claim_id = _ensure_claim_id(claim_id)
        return tuple(
            assignment
            for assignment in self.assignments
            if assignment.claim_id == parsed_claim_id
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "dependency_group_id": self.dependency_group_id,
            "origin_label": self.origin_label,
            "created_at": self.created_at,
            "assignments": tuple(assignment.to_payload() for assignment in self.assignments),
        }


@dataclass(frozen=True)
class IndependentSupportCount:
    """Résultat métier du comptage de confirmations indépendantes."""

    status: str
    claim_id: str
    accepted_evidence_ids: Sequence[str]
    dependency_group_ids: Sequence[str]
    independent_confirmation_count: int

    def __post_init__(self) -> None:
        status = _ensure_text(self.status, "status")
        if status != "CLAIM_INDEPENDENT_SUPPORT_COUNTED":
            raise ValueError("status support independant invalide")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "claim_id", _ensure_claim_id(self.claim_id))
        object.__setattr__(
            self,
            "accepted_evidence_ids",
            _ensure_evidence_ids(self.accepted_evidence_ids),
        )
        object.__setattr__(
            self,
            "dependency_group_ids",
            _ensure_dependency_group_ids(self.dependency_group_ids),
        )
        object.__setattr__(
            self,
            "independent_confirmation_count",
            _ensure_non_negative_integer(
                self.independent_confirmation_count,
                "independent_confirmation_count",
            ),
        )
        if self.independent_confirmation_count != len(self.dependency_group_ids):
            raise ValueError("independent_confirmation_count incoherent")


class SourceIndependencePolicy:
    """Politique qui compte uniquement les groupes documentés explicitement."""

    def count_independent_support(
        self,
        *,
        claim_id: str,
        accepted_evidence_ids: Sequence[str],
        dependency_groups: Sequence[DependencyGroup],
    ) -> IndependentSupportCount:
        parsed_claim_id = _ensure_claim_id(claim_id)
        parsed_evidence_ids = _ensure_evidence_ids(accepted_evidence_ids)
        parsed_groups = _ensure_dependency_groups(dependency_groups)
        assignments_by_evidence: dict[str, ClaimDependencyAssignment] = {}

        for group in parsed_groups:
            for assignment in group.assignments_for_claim(parsed_claim_id):
                if assignment.evidence_id not in parsed_evidence_ids:
                    continue
                existing = assignments_by_evidence.get(assignment.evidence_id)
                if existing is not None and existing != assignment:
                    raise ValueError(
                        f"dependency_assignment duplique pour evidence_id: {assignment.evidence_id}"
                    )
                assignments_by_evidence[assignment.evidence_id] = assignment

        dependency_group_ids: list[str] = []
        for evidence_id in parsed_evidence_ids:
            assignment = assignments_by_evidence.get(evidence_id)
            if assignment is None:
                raise ValueError(f"dependency_group absent pour evidence_id: {evidence_id}")
            if assignment.dependency_group_id not in dependency_group_ids:
                dependency_group_ids.append(assignment.dependency_group_id)

        return IndependentSupportCount(
            status="CLAIM_INDEPENDENT_SUPPORT_COUNTED",
            claim_id=parsed_claim_id,
            accepted_evidence_ids=parsed_evidence_ids,
            dependency_group_ids=tuple(dependency_group_ids),
            independent_confirmation_count=len(dependency_group_ids),
        )


def _ensure_assignment(value: ClaimDependencyAssignment) -> ClaimDependencyAssignment:
    if not isinstance(value, ClaimDependencyAssignment):
        raise ValueError("dependency_assignment invalide")
    return value


def _ensure_assignments(
    value: Sequence[ClaimDependencyAssignment],
    dependency_group_id: str,
) -> tuple[ClaimDependencyAssignment, ...]:
    if value is None:
        raise ValueError("assignments absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("assignments invalides")
    assignments = tuple(value)
    keys: list[tuple[str, int, str]] = []
    for assignment in assignments:
        parsed_assignment = _ensure_assignment(assignment)
        if parsed_assignment.dependency_group_id != dependency_group_id:
            raise ValueError("dependency_assignment groupe incoherent")
        key = (
            parsed_assignment.claim_id,
            parsed_assignment.claim_version,
            parsed_assignment.evidence_id,
        )
        if key in keys:
            raise ValueError("dependency_assignment duplique")
        keys.append(key)
    return assignments


def _ensure_dependency_groups(value: Sequence[DependencyGroup]) -> tuple[DependencyGroup, ...]:
    if value is None:
        raise ValueError("dependency_groups absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("dependency_groups invalides")
    groups = tuple(value)
    group_ids: list[str] = []
    for group in groups:
        if not isinstance(group, DependencyGroup):
            raise ValueError("dependency_group invalide")
        if group.dependency_group_id in group_ids:
            raise ValueError("dependency_group duplique")
        group_ids.append(group.dependency_group_id)
    return groups


def _ensure_evidence_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("accepted_evidence_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("accepted_evidence_ids invalides")
    evidence_ids = tuple(_ensure_evidence_id(item) for item in value)
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("accepted_evidence_ids dupliques")
    return evidence_ids


def _ensure_dependency_group_ids(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("dependency_group_ids absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("dependency_group_ids invalides")
    dependency_group_ids = tuple(_ensure_dependency_group_id(item) for item in value)
    if len(dependency_group_ids) != len(set(dependency_group_ids)):
        raise ValueError("dependency_group_ids dupliques")
    return dependency_group_ids


def _ensure_claim_id(value: Any) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_evidence_id(value: Any) -> str:
    text = _ensure_text(value, "evidence_id")
    if _EVIDENCE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("evidence_id invalide")
    return text


def _ensure_dependency_group_id(value: Any) -> str:
    text = _ensure_text(value, "dependency_group_id")
    if _DEPENDENCY_GROUP_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("dependency_group_id invalide")
    return text


def _ensure_dependency_kind(value: Any) -> str:
    text = _ensure_text(value, "dependency_kind")
    if text not in _ALLOWED_DEPENDENCY_KINDS:
        raise ValueError("dependency_kind non autorise")
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


def _ensure_non_negative_integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: Any) -> str:
    text = _ensure_text(value, "occurred_at")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError("occurred_at invalide")
    return text


__all__ = [
    "ClaimDependencyAssigned",
    "ClaimDependencyAssignment",
    "DependencyGroup",
    "IndependentSupportCount",
    "SourceIndependencePolicy",
]
