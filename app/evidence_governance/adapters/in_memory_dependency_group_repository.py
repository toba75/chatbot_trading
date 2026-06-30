"""Repository mémoire strict des groupes de dépendance EG."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.evidence_governance.domain.dependency_group import (
    ClaimDependencyAssignment,
    DependencyGroup,
)


class InMemoryDependencyGroupRepository:
    """Double strict du port DependencyGroupRepository."""

    def __init__(self, *, dependency_groups: Sequence[DependencyGroup]) -> None:
        self._lock = threading.Lock()
        self._groups_by_id: dict[str, DependencyGroup] = {}
        for dependency_group in _ensure_dependency_groups(dependency_groups):
            self.save(dependency_group)

    @classmethod
    def empty(cls) -> "InMemoryDependencyGroupRepository":
        return cls(dependency_groups=())

    def save(self, dependency_group: DependencyGroup) -> DependencyGroup:
        parsed_group = _ensure_dependency_group(dependency_group)
        with self._lock:
            existing = self._groups_by_id.get(parsed_group.dependency_group_id)
            if existing is not None:
                if existing.origin_label != parsed_group.origin_label:
                    raise ValueError("dependency_group origin_label incoherent")
                if existing.created_at != parsed_group.created_at:
                    raise ValueError("dependency_group created_at incoherent")
                if not set(existing.assignments).issubset(set(parsed_group.assignments)):
                    raise ValueError("dependency_group suppression interdite")
            self._groups_by_id[parsed_group.dependency_group_id] = parsed_group
            return parsed_group

    def group_for_id(self, dependency_group_id: str) -> DependencyGroup:
        parsed_group_id = _ensure_dependency_group_id(dependency_group_id)
        with self._lock:
            group = self._groups_by_id.get(parsed_group_id)
            if group is None:
                raise ValueError(f"dependency_group inconnu: {parsed_group_id}")
            return group

    def groups_for_claim(self, claim_id: str) -> tuple[DependencyGroup, ...]:
        parsed_claim_id = _ensure_claim_id(claim_id)
        with self._lock:
            return tuple(
                group
                for group in self._groups_by_id.values()
                if len(group.assignments_for_claim(parsed_claim_id)) > 0
            )

    def assignment_for_claim_evidence(
        self,
        *,
        claim_id: str,
        claim_version: int,
        evidence_id: str,
    ) -> ClaimDependencyAssignment | None:
        parsed_claim_id = _ensure_claim_id(claim_id)
        parsed_claim_version = _ensure_positive_integer(claim_version, "claim_version")
        parsed_evidence_id = _ensure_evidence_id(evidence_id)
        matches: list[ClaimDependencyAssignment] = []
        with self._lock:
            for group in self._groups_by_id.values():
                for assignment in group.assignments:
                    if (
                        assignment.claim_id == parsed_claim_id
                        and assignment.claim_version == parsed_claim_version
                        and assignment.evidence_id == parsed_evidence_id
                    ):
                        matches.append(assignment)
        if len(matches) > 1:
            raise ValueError(f"dependency_assignment duplique pour evidence_id: {parsed_evidence_id}")
        if len(matches) == 0:
            return None
        return matches[0]

    def group_count(self) -> int:
        with self._lock:
            return len(self._groups_by_id)


def _ensure_dependency_groups(
    value: Sequence[DependencyGroup],
) -> tuple[DependencyGroup, ...]:
    if value is None:
        raise ValueError("dependency_groups absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("dependency_groups invalides")
    groups = tuple(value)
    group_ids: list[str] = []
    for group in groups:
        parsed_group = _ensure_dependency_group(group)
        if parsed_group.dependency_group_id in group_ids:
            raise ValueError("dependency_group duplique")
        group_ids.append(parsed_group.dependency_group_id)
    return groups


def _ensure_dependency_group(value: DependencyGroup) -> DependencyGroup:
    if not isinstance(value, DependencyGroup):
        raise ValueError("dependency_group invalide")
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


def _ensure_evidence_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("evidence_id non textuel")
    if value.strip() == "":
        raise ValueError("evidence_id vide")
    if value != value.strip():
        raise ValueError("evidence_id non normalise")
    if not value.startswith("EVS-"):
        raise ValueError("evidence_id invalide")
    return value


def _ensure_dependency_group_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("dependency_group_id non textuel")
    if value.strip() == "":
        raise ValueError("dependency_group_id vide")
    if value != value.strip():
        raise ValueError("dependency_group_id non normalise")
    if not value.startswith("DEP-"):
        raise ValueError("dependency_group_id invalide")
    return value


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = ["InMemoryDependencyGroupRepository"]
