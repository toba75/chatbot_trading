"""Repository memoire strict des relations de claims EG."""

from __future__ import annotations

import threading
from collections.abc import Sequence

from app.evidence_governance.domain.claim_relation import ClaimRelation, ClaimVersionRef


class InMemoryClaimRelationRepository:
    """Double strict du port ClaimRelationRepository."""

    def __init__(self, *, claim_relations: Sequence[ClaimRelation]) -> None:
        self._lock = threading.Lock()
        self._relations_by_id: dict[str, ClaimRelation] = {}
        for relation in _ensure_claim_relations(claim_relations):
            self.save(relation)

    @classmethod
    def empty(cls) -> "InMemoryClaimRelationRepository":
        return cls(claim_relations=())

    def save(self, claim_relation: ClaimRelation) -> ClaimRelation:
        parsed_relation = _ensure_claim_relation(claim_relation)
        with self._lock:
            if parsed_relation.relation_id in self._relations_by_id:
                raise ValueError("claim_relation duplique")
            if parsed_relation in self._relations_by_id.values():
                raise ValueError("claim_relation duplique")
            self._relations_by_id[parsed_relation.relation_id] = parsed_relation
            return parsed_relation

    def relations_between(
        self,
        *,
        source_claim_id: str,
        target_claim_id: str,
    ) -> tuple[ClaimRelation, ...]:
        parsed_source_claim_id = _ensure_claim_id(source_claim_id, "source_claim_id")
        parsed_target_claim_id = _ensure_claim_id(target_claim_id, "target_claim_id")
        with self._lock:
            return tuple(
                relation
                for relation in self._relations_by_id.values()
                if relation.source_claim_ref.claim_id == parsed_source_claim_id
                and relation.target_claim_ref.claim_id == parsed_target_claim_id
            )

    def has_path(
        self,
        *,
        source_claim_ref: ClaimVersionRef,
        target_claim_ref: ClaimVersionRef,
    ) -> bool:
        source_ref = _ensure_claim_ref(source_claim_ref, "source_claim_ref")
        target_ref = _ensure_claim_ref(target_claim_ref, "target_claim_ref")
        with self._lock:
            adjacency: dict[ClaimVersionRef, tuple[ClaimVersionRef, ...]] = {}
            for relation in self._relations_by_id.values():
                adjacency[relation.source_claim_ref] = (
                    *adjacency.get(relation.source_claim_ref, ()),
                    relation.target_claim_ref,
                )
        return _has_path(
            source_claim_ref=source_ref,
            target_claim_ref=target_ref,
            adjacency=adjacency,
        )

    def relation_count(self) -> int:
        with self._lock:
            return len(self._relations_by_id)


def _has_path(
    *,
    source_claim_ref: ClaimVersionRef,
    target_claim_ref: ClaimVersionRef,
    adjacency: dict[ClaimVersionRef, tuple[ClaimVersionRef, ...]],
) -> bool:
    if source_claim_ref == target_claim_ref:
        return True
    visited: set[ClaimVersionRef] = set()
    pending: list[ClaimVersionRef] = [source_claim_ref]
    while len(pending) > 0:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        for next_ref in adjacency.get(current, ()):
            if next_ref == target_claim_ref:
                return True
            pending.append(next_ref)
    return False


def _ensure_claim_relations(value: Sequence[ClaimRelation]) -> tuple[ClaimRelation, ...]:
    if value is None:
        raise ValueError("claim_relations absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("claim_relations invalides")
    relations = tuple(value)
    relation_ids: list[str] = []
    for relation in relations:
        parsed_relation = _ensure_claim_relation(relation)
        if parsed_relation.relation_id in relation_ids:
            raise ValueError("claim_relation duplique")
        relation_ids.append(parsed_relation.relation_id)
    return relations


def _ensure_claim_relation(value: ClaimRelation) -> ClaimRelation:
    if not isinstance(value, ClaimRelation):
        raise ValueError("claim_relation invalide")
    return value


def _ensure_claim_ref(value: ClaimVersionRef, field_name: str) -> ClaimVersionRef:
    if not isinstance(value, ClaimVersionRef):
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_claim_id(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    if not value.startswith("CLM-"):
        raise ValueError(f"{field_name} invalide")
    return value


__all__ = ["InMemoryClaimRelationRepository"]
