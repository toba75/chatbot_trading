"""Relations auditees entre versions de claims EG."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.evidence_governance.domain.claim_evidence import Claim
from app.evidence_governance.domain.claim_extraction import ClaimScope


_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_RELATION_ID_PATTERN = re.compile(r"^REL-[A-Z0-9][A-Z0-9-]*$")
_REQUIRED_SCOPE_DIMENSIONS = ("universe", "horizon", "metric", "frequency")
_TEXTUAL_SIMILARITY_ONLY = "TEXTUAL_SIMILARITY_ONLY"
_EXPLICIT_SCOPE_COMPARISON = "EXPLICIT_SCOPE_COMPARISON"
_EXPLICIT_SOURCE_DEPENDENCY = "EXPLICIT_SOURCE_DEPENDENCY"
_EXPLICIT_SUPPORT_EVIDENCE = "EXPLICIT_SUPPORT_EVIDENCE"
_EXPLICIT_SCOPE_QUALIFICATION = "EXPLICIT_SCOPE_QUALIFICATION"
_ALLOWED_RELATION_BASES = frozenset(
    {
        _EXPLICIT_SCOPE_COMPARISON,
        _EXPLICIT_SOURCE_DEPENDENCY,
        _EXPLICIT_SUPPORT_EVIDENCE,
        _EXPLICIT_SCOPE_QUALIFICATION,
    }
)
_SCOPE_STOPWORDS = frozenset(
    {
        "avec",
        "de",
        "des",
        "du",
        "la",
        "le",
        "les",
        "tous",
        "toutes",
    }
)


class ClaimRelationType(str, Enum):
    """Type explicite de relation entre versions de claims."""

    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    APPARENTLY_CONTRADICTS = "APPARENTLY_CONTRADICTS"
    MORE_GENERAL_THAN = "MORE_GENERAL_THAN"
    DERIVED_FROM = "DERIVED_FROM"
    QUALIFIES = "QUALIFIES"


class ScopeCompatibilityStatus(str, Enum):
    """Resultat de comparaison de portee entre deux claims."""

    COMPARABLE = "COMPARABLE"
    NON_COMPARABLE = "NON_COMPARABLE"
    SOURCE_BROADER = "SOURCE_BROADER"
    TARGET_BROADER = "TARGET_BROADER"


@dataclass(frozen=True)
class ClaimVersionRef:
    """Reference explicite vers une version de claim."""

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


@dataclass(frozen=True)
class ScopeCompatibility:
    """Comparaison auditee des dimensions de portee."""

    status: ScopeCompatibilityStatus
    compared_dimensions: Sequence[str]
    reason_code: str | None

    @classmethod
    def compare(
        cls,
        *,
        source_scope: ClaimScope,
        target_scope: ClaimScope,
    ) -> "ScopeCompatibility":
        source = _ensure_claim_scope(source_scope, "source_scope")
        target = _ensure_claim_scope(target_scope, "target_scope")
        dimensions = _REQUIRED_SCOPE_DIMENSIONS

        if source.to_payload() == target.to_payload():
            return cls(
                status=ScopeCompatibilityStatus.COMPARABLE,
                compared_dimensions=dimensions,
                reason_code=None,
            )

        if source.horizon != target.horizon:
            return cls(
                status=ScopeCompatibilityStatus.NON_COMPARABLE,
                compared_dimensions=dimensions,
                reason_code="SCOPE_HORIZON_MISMATCH",
            )
        if source.metric != target.metric:
            return cls(
                status=ScopeCompatibilityStatus.NON_COMPARABLE,
                compared_dimensions=dimensions,
                reason_code="SCOPE_METRIC_MISMATCH",
            )
        if source.frequency != target.frequency:
            return cls(
                status=ScopeCompatibilityStatus.NON_COMPARABLE,
                compared_dimensions=dimensions,
                reason_code="SCOPE_FREQUENCY_MISMATCH",
            )

        universe_relation = _universe_relation(source.universe, target.universe)
        if universe_relation == ScopeCompatibilityStatus.SOURCE_BROADER:
            return cls(
                status=ScopeCompatibilityStatus.SOURCE_BROADER,
                compared_dimensions=dimensions,
                reason_code=None,
            )
        if universe_relation == ScopeCompatibilityStatus.TARGET_BROADER:
            return cls(
                status=ScopeCompatibilityStatus.TARGET_BROADER,
                compared_dimensions=dimensions,
                reason_code=None,
            )
        return cls(
            status=ScopeCompatibilityStatus.NON_COMPARABLE,
            compared_dimensions=dimensions,
            reason_code="SCOPE_UNIVERSE_MISMATCH",
        )

    def __post_init__(self) -> None:
        if not isinstance(self.status, ScopeCompatibilityStatus):
            raise ValueError("scope_compatibility_status invalide")
        object.__setattr__(
            self,
            "compared_dimensions",
            _ensure_scope_dimensions(self.compared_dimensions),
        )
        if self.status == ScopeCompatibilityStatus.NON_COMPARABLE:
            if self.reason_code is None:
                raise ValueError("scope_incompatibility_reason absente")
            object.__setattr__(
                self,
                "reason_code",
                _ensure_text(self.reason_code, "scope_incompatibility_reason"),
            )
            return
        if self.reason_code is not None:
            raise ValueError("scope_incompatibility_reason incoherente")

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "compared_dimensions": self.compared_dimensions,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class ClaimRelationPolicyDecision:
    """Decision de politique avant enregistrement d'une relation."""

    relation_type: ClaimRelationType
    scope_compatibility: ScopeCompatibility

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_type", _ensure_relation_type(self.relation_type))
        if not isinstance(self.scope_compatibility, ScopeCompatibility):
            raise ValueError("scope_compatibility invalide")


class ClaimRelationPolicy:
    """Politique reliant des claims seulement apres comparaison explicite."""

    def evaluate(
        self,
        *,
        source_claim: Claim,
        target_claim: Claim,
        requested_relation_type: ClaimRelationType,
        relation_basis: str,
    ) -> ClaimRelationPolicyDecision:
        source = _ensure_claim(source_claim, "source_claim")
        target = _ensure_claim(target_claim, "target_claim")
        relation_type = _ensure_relation_type(requested_relation_type)
        basis = _ensure_relation_basis(relation_basis)
        compatibility = ScopeCompatibility.compare(
            source_scope=source.scope,
            target_scope=target.scope,
        )

        if relation_type == ClaimRelationType.CONTRADICTS:
            _ensure_scope_comparison_basis(basis)
            if compatibility.status == ScopeCompatibilityStatus.COMPARABLE:
                return ClaimRelationPolicyDecision(
                    relation_type=ClaimRelationType.CONTRADICTS,
                    scope_compatibility=compatibility,
                )
            return ClaimRelationPolicyDecision(
                relation_type=ClaimRelationType.APPARENTLY_CONTRADICTS,
                scope_compatibility=compatibility,
            )

        if relation_type == ClaimRelationType.APPARENTLY_CONTRADICTS:
            _ensure_scope_comparison_basis(basis)
            if compatibility.status != ScopeCompatibilityStatus.NON_COMPARABLE:
                raise ValueError("contradiction_apparente_scope comparable")
            return ClaimRelationPolicyDecision(
                relation_type=relation_type,
                scope_compatibility=compatibility,
            )

        if relation_type == ClaimRelationType.MORE_GENERAL_THAN:
            _ensure_scope_comparison_basis(basis)
            if compatibility.status != ScopeCompatibilityStatus.SOURCE_BROADER:
                raise ValueError("source_scope non generale")
            return ClaimRelationPolicyDecision(
                relation_type=relation_type,
                scope_compatibility=compatibility,
            )

        if relation_type == ClaimRelationType.DERIVED_FROM:
            if basis != _EXPLICIT_SOURCE_DEPENDENCY:
                raise ValueError("source_dependency explicite absente")
            return ClaimRelationPolicyDecision(
                relation_type=relation_type,
                scope_compatibility=compatibility,
            )

        if relation_type == ClaimRelationType.SUPPORTS:
            if basis != _EXPLICIT_SUPPORT_EVIDENCE:
                raise ValueError("support explicite absent")
            if compatibility.status != ScopeCompatibilityStatus.COMPARABLE:
                raise ValueError("support_scope non compatible")
            return ClaimRelationPolicyDecision(
                relation_type=relation_type,
                scope_compatibility=compatibility,
            )

        if relation_type == ClaimRelationType.QUALIFIES:
            if basis != _EXPLICIT_SCOPE_QUALIFICATION:
                raise ValueError("qualification explicite absente")
            if compatibility.status != ScopeCompatibilityStatus.COMPARABLE:
                raise ValueError("qualification_scope non compatible")
            return ClaimRelationPolicyDecision(
                relation_type=relation_type,
                scope_compatibility=compatibility,
            )

        raise ValueError("relation_type invalide")


@dataclass(frozen=True)
class ClaimRelation:
    """Relation immutable entre deux versions de claims."""

    relation_id: str
    source_claim_ref: ClaimVersionRef
    target_claim_ref: ClaimVersionRef
    relation_type: ClaimRelationType
    scope_compatibility: ScopeCompatibility
    relation_basis: str
    policy_version: str
    recorded_at: str
    cycle_justification: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", _ensure_relation_id(self.relation_id))
        if not isinstance(self.source_claim_ref, ClaimVersionRef):
            raise ValueError("source_claim_ref invalide")
        if not isinstance(self.target_claim_ref, ClaimVersionRef):
            raise ValueError("target_claim_ref invalide")
        if self.source_claim_ref == self.target_claim_ref:
            raise ValueError("relation claim reflexive interdite")
        object.__setattr__(self, "relation_type", _ensure_relation_type(self.relation_type))
        if not isinstance(self.scope_compatibility, ScopeCompatibility):
            raise ValueError("scope_compatibility invalide")
        if (
            self.relation_type == ClaimRelationType.CONTRADICTS
            and self.scope_compatibility.status != ScopeCompatibilityStatus.COMPARABLE
        ):
            raise ValueError("contradiction_scope non comparable")
        if (
            self.relation_type == ClaimRelationType.APPARENTLY_CONTRADICTS
            and self.scope_compatibility.status != ScopeCompatibilityStatus.NON_COMPARABLE
        ):
            raise ValueError("contradiction_apparente_scope comparable")
        if (
            self.relation_type == ClaimRelationType.MORE_GENERAL_THAN
            and self.scope_compatibility.status != ScopeCompatibilityStatus.SOURCE_BROADER
        ):
            raise ValueError("source_scope non generale")
        object.__setattr__(self, "relation_basis", _ensure_relation_basis(self.relation_basis))
        if self.relation_type in {
            ClaimRelationType.CONTRADICTS,
            ClaimRelationType.APPARENTLY_CONTRADICTS,
            ClaimRelationType.MORE_GENERAL_THAN,
        }:
            _ensure_scope_comparison_basis(self.relation_basis)
        if self.relation_type == ClaimRelationType.DERIVED_FROM and (
            self.relation_basis != _EXPLICIT_SOURCE_DEPENDENCY
        ):
            raise ValueError("source_dependency explicite absente")
        if self.relation_type == ClaimRelationType.SUPPORTS and (
            self.relation_basis != _EXPLICIT_SUPPORT_EVIDENCE
        ):
            raise ValueError("support explicite absent")
        if self.relation_type == ClaimRelationType.SUPPORTS and (
            self.scope_compatibility.status != ScopeCompatibilityStatus.COMPARABLE
        ):
            raise ValueError("support_scope non compatible")
        if self.relation_type == ClaimRelationType.QUALIFIES and (
            self.relation_basis != _EXPLICIT_SCOPE_QUALIFICATION
        ):
            raise ValueError("qualification explicite absente")
        if self.relation_type == ClaimRelationType.QUALIFIES and (
            self.scope_compatibility.status != ScopeCompatibilityStatus.COMPARABLE
        ):
            raise ValueError("qualification_scope non compatible")
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        object.__setattr__(self, "recorded_at", _ensure_utc_instant(self.recorded_at))
        if self.cycle_justification is not None:
            object.__setattr__(
                self,
                "cycle_justification",
                _ensure_text(self.cycle_justification, "cycle_justification"),
            )

    def to_payload(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_claim_ref": self.source_claim_ref.to_payload(),
            "target_claim_ref": self.target_claim_ref.to_payload(),
            "relation_type": self.relation_type.value,
            "scope_compatibility": self.scope_compatibility.to_payload(),
            "relation_basis": self.relation_basis,
            "policy_version": self.policy_version,
            "recorded_at": self.recorded_at,
            "cycle_justification": self.cycle_justification,
        }


@dataclass(frozen=True)
class ClaimRelationRecorded:
    """Evenement publie quand une relation de claims est enregistree."""

    relation_id: str
    source_claim_ref: ClaimVersionRef
    target_claim_ref: ClaimVersionRef
    relation_type: ClaimRelationType
    scope_compatibility: ScopeCompatibility
    occurred_at: str

    @classmethod
    def from_relation(cls, relation: ClaimRelation) -> "ClaimRelationRecorded":
        parsed_relation = _ensure_relation(relation)
        return cls(
            relation_id=parsed_relation.relation_id,
            source_claim_ref=parsed_relation.source_claim_ref,
            target_claim_ref=parsed_relation.target_claim_ref,
            relation_type=parsed_relation.relation_type,
            scope_compatibility=parsed_relation.scope_compatibility,
            occurred_at=parsed_relation.recorded_at,
        )

    @property
    def event_type(self) -> str:
        return "ClaimRelationRecorded"

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", _ensure_relation_id(self.relation_id))
        if not isinstance(self.source_claim_ref, ClaimVersionRef):
            raise ValueError("source_claim_ref invalide")
        if not isinstance(self.target_claim_ref, ClaimVersionRef):
            raise ValueError("target_claim_ref invalide")
        object.__setattr__(self, "relation_type", _ensure_relation_type(self.relation_type))
        if not isinstance(self.scope_compatibility, ScopeCompatibility):
            raise ValueError("scope_compatibility invalide")
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "relation_id": self.relation_id,
                "source_claim_ref": self.source_claim_ref.to_payload(),
                "target_claim_ref": self.target_claim_ref.to_payload(),
                "relation_type": self.relation_type.value,
                "scope_compatibility": self.scope_compatibility.to_payload(),
            },
        }


def _ensure_relation(value: ClaimRelation) -> ClaimRelation:
    if not isinstance(value, ClaimRelation):
        raise ValueError("claim_relation invalide")
    return value


def _ensure_claim(value: Claim, field_name: str) -> Claim:
    if not isinstance(value, Claim):
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_claim_scope(value: ClaimScope, field_name: str) -> ClaimScope:
    if not isinstance(value, ClaimScope):
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_relation_type(value: Any) -> ClaimRelationType:
    if value is None:
        raise ValueError("relation_type absent")
    if not isinstance(value, ClaimRelationType):
        raise ValueError("relation_type invalide")
    return value


def _ensure_relation_basis(value: Any) -> str:
    text = _ensure_text(value, "relation_basis")
    if text == _TEXTUAL_SIMILARITY_ONLY:
        raise ValueError("relation par similarite textuelle seule interdite")
    if text not in _ALLOWED_RELATION_BASES:
        raise ValueError("relation_basis non autorisee")
    return text


def _ensure_scope_comparison_basis(value: str) -> None:
    if value != _EXPLICIT_SCOPE_COMPARISON:
        raise ValueError("scope_comparison explicite absente")


def _ensure_claim_id(value: Any) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_relation_id(value: Any) -> str:
    text = _ensure_text(value, "relation_id")
    if _RELATION_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("relation_id invalide")
    return text


def _ensure_scope_dimensions(value: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        raise ValueError("scope_dimensions absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("scope_dimensions invalides")
    dimensions = tuple(value)
    if dimensions != _REQUIRED_SCOPE_DIMENSIONS:
        raise ValueError("scope_dimensions incompletes")
    return dimensions


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


def _ensure_utc_instant(value: Any) -> str:
    text = _ensure_text(value, "recorded_at")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text) is None:
        raise ValueError("recorded_at invalide")
    return text


def _universe_relation(source_universe: str, target_universe: str) -> ScopeCompatibilityStatus | None:
    source_tokens = _scope_tokens(source_universe)
    target_tokens = _scope_tokens(target_universe)
    if source_tokens < target_tokens:
        return ScopeCompatibilityStatus.SOURCE_BROADER
    if target_tokens < source_tokens:
        return ScopeCompatibilityStatus.TARGET_BROADER
    return None


def _scope_tokens(value: str) -> frozenset[str]:
    text = _ensure_text(value, "universe").lower()
    tokens = frozenset(
        token
        for token in re.split(r"[^a-z0-9]+", _strip_accents(text))
        if token != "" and token not in _SCOPE_STOPWORDS
    )
    if len(tokens) == 0:
        raise ValueError("universe vide")
    return tokens


def _strip_accents(value: str) -> str:
    translation = str.maketrans(
        {
            "à": "a",
            "â": "a",
            "ä": "a",
            "ç": "c",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "î": "i",
            "ï": "i",
            "ô": "o",
            "ö": "o",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ÿ": "y",
        }
    )
    return value.translate(translation)


__all__ = [
    "ClaimRelation",
    "ClaimRelationPolicy",
    "ClaimRelationPolicyDecision",
    "ClaimRelationRecorded",
    "ClaimRelationType",
    "ClaimVersionRef",
    "ScopeCompatibility",
    "ScopeCompatibilityStatus",
]
