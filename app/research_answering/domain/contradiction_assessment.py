"""Diagnostics RA de contradictions et de lacunes documentaires."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_RESEARCH_CASE_ID_PATTERN = re.compile(r"^RSC-[A-Z0-9][A-Z0-9-]*$")
_RELATION_ID_PATTERN = re.compile(r"^REL-[A-Z0-9][A-Z0-9-]*$")
_CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Z0-9][A-Z0-9-]*$")
_GAP_ID_PATTERN = re.compile(r"^KGP-[A-Z0-9][A-Z0-9-]*$")
_REQUIRED_SCOPE_DIMENSIONS = ("universe", "horizon", "metric", "frequency")
_EG_SCOPE_RELATION_BASIS = "EG_SCOPE_RELATION"
_FREQUENCY_CONSENSUS_BASIS = "FREQUENCY_CONSENSUS"
_RECORDED_CONTRADICTION_BASIS = "RECORDED_CONTRADICTION_ASSESSMENT"
_COVERAGE_OBLIGATION_BASIS = "COVERAGE_OBLIGATION_ASSESSMENT"


class SupportStatus(str, Enum):
    """Statuts documentaires RA publiables par politique."""

    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    REQUIRES_CURRENT_DATA = "REQUIRES_CURRENT_DATA"


class ContradictionClassification(str, Enum):
    """Classement RA d'une opposition documentaire."""

    DIRECT_CONFLICT = "DIRECT_CONFLICT"
    DIFFERENT_HORIZON = "DIFFERENT_HORIZON"
    DIFFERENT_METRIC = "DIFFERENT_METRIC"
    DIFFERENT_FREQUENCY = "DIFFERENT_FREQUENCY"
    DIFFERENT_UNIVERSE = "DIFFERENT_UNIVERSE"
    RESOLVED_BY_QUALIFICATION = "RESOLVED_BY_QUALIFICATION"


class KnowledgeGapType(str, Enum):
    """Type public de lacune documentaire RA."""

    COVERAGE_OBLIGATION_MISSING = "COVERAGE_OBLIGATION_MISSING"


@dataclass(frozen=True)
class ClaimRef:
    """Reference minimale de version de claim consommee par RA."""

    claim_id: str
    claim_version: int

    @classmethod
    def from_object(cls, value: object, field_name: str) -> "ClaimRef":
        if value is None:
            raise ValueError(f"{field_name} absent")
        return cls(
            claim_id=_ensure_claim_id(getattr(value, "claim_id", None)),
            claim_version=_ensure_positive_integer(
                getattr(value, "claim_version", None),
                f"{field_name}.claim_version",
            ),
        )

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
class ContradictionAssessment:
    """Diagnostic RA conserve avant toute synthese de reponse."""

    contradiction_id: str
    relation_id: str
    source_claim_ref: ClaimRef
    target_claim_ref: ClaimRef
    classification: ContradictionClassification
    reason_code: str
    public_reason: str
    policy_version: str
    requires_public_explanation: bool
    blocks_general_supported_status: bool
    blocks_publication: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "contradiction_id", _ensure_relation_id(self.contradiction_id))
        object.__setattr__(self, "relation_id", _ensure_relation_id(self.relation_id))
        if self.contradiction_id != self.relation_id:
            raise ValueError("contradiction_id incoherent")
        if not isinstance(self.source_claim_ref, ClaimRef):
            raise ValueError("source_claim_ref invalide")
        if not isinstance(self.target_claim_ref, ClaimRef):
            raise ValueError("target_claim_ref invalide")
        if self.source_claim_ref == self.target_claim_ref:
            raise ValueError("contradiction reflexive interdite")
        object.__setattr__(self, "classification", _ensure_classification(self.classification))
        object.__setattr__(self, "reason_code", _ensure_text(self.reason_code, "reason_code"))
        object.__setattr__(self, "public_reason", _ensure_text(self.public_reason, "public_reason"))
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))
        for field_name in (
            "requires_public_explanation",
            "blocks_general_supported_status",
            "blocks_publication",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} non booleen")
        if self.classification == ContradictionClassification.DIRECT_CONFLICT and not self.blocks_publication:
            raise ValueError("conflit direct non bloquant")
        if (
            self.classification != ContradictionClassification.DIRECT_CONFLICT
            and self.blocks_publication
        ):
            raise ValueError("contradiction qualifiee bloquante")

    def to_payload(self) -> dict[str, Any]:
        return {
            "contradiction_id": self.contradiction_id,
            "relation_id": self.relation_id,
            "source_claim_ref": self.source_claim_ref.to_payload(),
            "target_claim_ref": self.target_claim_ref.to_payload(),
            "classification": self.classification.value,
            "reason_code": self.reason_code,
            "public_reason": self.public_reason,
            "policy_version": self.policy_version,
            "requires_public_explanation": self.requires_public_explanation,
            "blocks_general_supported_status": self.blocks_general_supported_status,
            "blocks_publication": self.blocks_publication,
        }


@dataclass(frozen=True)
class KnowledgeGap:
    """Lacune documentaire visible dans l'issue RA."""

    gap_id: str
    gap_type: KnowledgeGapType
    affected_obligation: str
    reason_code: str
    public_reason: str

    @classmethod
    def for_missing_obligation(
        cls,
        *,
        research_case_id: str,
        affected_obligation: str,
        reason_code: str,
    ) -> "KnowledgeGap":
        obligation = _ensure_text(affected_obligation, "affected_obligation")
        code = _ensure_text(reason_code, "reason_code")
        return cls(
            gap_id=_gap_id_for(
                research_case_id=_ensure_research_case_id(research_case_id),
                affected_obligation=obligation,
                reason_code=code,
            ),
            gap_type=KnowledgeGapType.COVERAGE_OBLIGATION_MISSING,
            affected_obligation=obligation,
            reason_code=code,
            public_reason=f"Obligation documentaire non satisfaite: {obligation}.",
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "gap_id", _ensure_gap_id(self.gap_id))
        if not isinstance(self.gap_type, KnowledgeGapType):
            raise ValueError("knowledge_gap_type invalide")
        object.__setattr__(
            self,
            "affected_obligation",
            _ensure_text(self.affected_obligation, "affected_obligation"),
        )
        object.__setattr__(self, "reason_code", _ensure_text(self.reason_code, "reason_code"))
        object.__setattr__(self, "public_reason", _ensure_text(self.public_reason, "public_reason"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "gap_type": self.gap_type.value,
            "affected_obligation": self.affected_obligation,
            "reason_code": self.reason_code,
            "public_reason": self.public_reason,
        }


@dataclass(frozen=True)
class ContradictionDetected:
    """Evenement RA de diagnostic de contradiction."""

    research_case_id: str
    contradiction_id: str
    contradiction_type: ContradictionClassification
    affected_claim_refs: tuple[ClaimRef, ClaimRef]
    reason_code: str
    occurred_at: str

    @classmethod
    def from_assessment(
        cls,
        *,
        research_case_id: str,
        assessment: ContradictionAssessment,
        occurred_at: str,
    ) -> "ContradictionDetected":
        if not isinstance(assessment, ContradictionAssessment):
            raise ValueError("contradiction_assessment invalide")
        return cls(
            research_case_id=research_case_id,
            contradiction_id=assessment.contradiction_id,
            contradiction_type=assessment.classification,
            affected_claim_refs=(assessment.source_claim_ref, assessment.target_claim_ref),
            reason_code=assessment.reason_code,
            occurred_at=occurred_at,
        )

    @property
    def event_type(self) -> str:
        return "ContradictionDetected"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(self, "contradiction_id", _ensure_relation_id(self.contradiction_id))
        object.__setattr__(self, "contradiction_type", _ensure_classification(self.contradiction_type))
        refs = _ensure_claim_refs(self.affected_claim_refs, "affected_claim_refs")
        if len(refs) != 2:
            raise ValueError("affected_claim_refs invalides")
        object.__setattr__(self, "affected_claim_refs", refs)
        object.__setattr__(self, "reason_code", _ensure_text(self.reason_code, "reason_code"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "contradiction_id": self.contradiction_id,
                "contradiction_type": self.contradiction_type.value,
                "affected_claim_refs": [ref.to_payload() for ref in self.affected_claim_refs],
                "reason_code": self.reason_code,
            },
        }


@dataclass(frozen=True)
class KnowledgeGapRecorded:
    """Evenement RA de lacune documentaire."""

    research_case_id: str
    gap_type: KnowledgeGapType
    affected_obligation: str
    reason_code: str
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "KnowledgeGapRecorded"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        if not isinstance(self.gap_type, KnowledgeGapType):
            raise ValueError("knowledge_gap_type invalide")
        object.__setattr__(
            self,
            "affected_obligation",
            _ensure_text(self.affected_obligation, "affected_obligation"),
        )
        object.__setattr__(self, "reason_code", _ensure_text(self.reason_code, "reason_code"))
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "gap_type": self.gap_type.value,
                "affected_obligation": self.affected_obligation,
                "reason_code": self.reason_code,
            },
        }


@dataclass(frozen=True)
class ResearchEvidenceFoundInsufficient:
    """Evenement RA terminal de preuves insuffisantes."""

    research_case_id: str
    missing_obligations: tuple[str, ...]
    reason_codes: tuple[str, ...]
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "ResearchEvidenceFoundInsufficient"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(
            self,
            "missing_obligations",
            _ensure_text_tuple(self.missing_obligations, "missing_obligations"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _ensure_text_tuple(self.reason_codes, "reason_codes"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "missing_obligations": self.missing_obligations,
                "reason_codes": self.reason_codes,
            },
        }


@dataclass(frozen=True)
class ResearchEvidenceFoundConflicting:
    """Evenement RA terminal de conflit documentaire."""

    research_case_id: str
    contradiction_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    occurred_at: str

    @property
    def event_type(self) -> str:
        return "ResearchEvidenceFoundConflicting"

    def __post_init__(self) -> None:
        object.__setattr__(self, "research_case_id", _ensure_research_case_id(self.research_case_id))
        object.__setattr__(
            self,
            "contradiction_ids",
            _ensure_relation_ids(self.contradiction_ids, "contradiction_ids", allow_empty=False),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _ensure_text_tuple(self.reason_codes, "reason_codes"),
        )
        object.__setattr__(self, "occurred_at", _ensure_utc_instant(self.occurred_at, "occurred_at"))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": {
                "research_case_id": self.research_case_id,
                "contradiction_ids": self.contradiction_ids,
                "reason_codes": self.reason_codes,
            },
        }


@dataclass(frozen=True)
class ContradictionClassificationPolicy:
    """Politique RA de classification des relations EG deja comparees."""

    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_version", _ensure_text(self.policy_version, "policy_version"))

    def classify(
        self,
        claim_relation: object,
        *,
        qualified_relation_ids: Sequence[str],
    ) -> ContradictionAssessment:
        relation = _relation_snapshot(claim_relation)
        qualified_ids = _ensure_relation_ids(
            qualified_relation_ids,
            "qualified_relation_ids",
            allow_empty=True,
        )
        if relation["relation_type"] == "CONTRADICTS":
            if relation["relation_id"] in qualified_ids:
                return self._assessment_for(
                    relation=relation,
                    classification=ContradictionClassification.RESOLVED_BY_QUALIFICATION,
                    reason_code="QUALIFIED_DIRECT_CONFLICT",
                    public_reason="Contradiction documentaire conservee avec qualification explicite.",
                    blocks_publication=False,
                )
            return self._assessment_for(
                relation=relation,
                classification=ContradictionClassification.DIRECT_CONFLICT,
                reason_code="UNRESOLVED_DIRECT_CONFLICT",
                public_reason="Claims verifies opposes sur une portee comparable.",
                blocks_publication=True,
            )

        if relation["relation_type"] == "APPARENTLY_CONTRADICTS":
            return self._assessment_for_non_comparable(relation)

        raise ValueError("relation non contradictoire")

    def _assessment_for_non_comparable(self, relation: Mapping[str, Any]) -> ContradictionAssessment:
        if relation["scope_status"] != "NON_COMPARABLE":
            raise ValueError("contradiction apparente sans non-comparabilite")
        reason_code = _ensure_text(relation["scope_reason_code"], "scope_reason_code")
        classification_by_reason = {
            "SCOPE_HORIZON_MISMATCH": ContradictionClassification.DIFFERENT_HORIZON,
            "SCOPE_METRIC_MISMATCH": ContradictionClassification.DIFFERENT_METRIC,
            "SCOPE_FREQUENCY_MISMATCH": ContradictionClassification.DIFFERENT_FREQUENCY,
            "SCOPE_UNIVERSE_MISMATCH": ContradictionClassification.DIFFERENT_UNIVERSE,
        }
        if reason_code not in classification_by_reason:
            raise ValueError(f"scope_reason_code non supporte: {reason_code}")
        public_reason_by_classification = {
            ContradictionClassification.DIFFERENT_HORIZON: "Opposition documentaire limitee par des horizons differents.",
            ContradictionClassification.DIFFERENT_METRIC: "Opposition documentaire limitee par des metriques differentes.",
            ContradictionClassification.DIFFERENT_FREQUENCY: "Opposition documentaire limitee par des frequences differentes.",
            ContradictionClassification.DIFFERENT_UNIVERSE: "Opposition documentaire limitee par des univers differents.",
        }
        classification = classification_by_reason[reason_code]
        return self._assessment_for(
            relation=relation,
            classification=classification,
            reason_code=reason_code,
            public_reason=public_reason_by_classification[classification],
            blocks_publication=False,
        )

    def _assessment_for(
        self,
        *,
        relation: Mapping[str, Any],
        classification: ContradictionClassification,
        reason_code: str,
        public_reason: str,
        blocks_publication: bool,
    ) -> ContradictionAssessment:
        return ContradictionAssessment(
            contradiction_id=relation["relation_id"],
            relation_id=relation["relation_id"],
            source_claim_ref=relation["source_claim_ref"],
            target_claim_ref=relation["target_claim_ref"],
            classification=classification,
            reason_code=reason_code,
            public_reason=public_reason,
            policy_version=self.policy_version,
            requires_public_explanation=True,
            blocks_general_supported_status=True,
            blocks_publication=blocks_publication,
        )


def ensure_classification_basis(value: object) -> str:
    text = _ensure_text(value, "classification_basis")
    if text == _FREQUENCY_CONSENSUS_BASIS:
        raise ValueError("consensus par frequence interdit")
    if text != _EG_SCOPE_RELATION_BASIS:
        raise ValueError("classification_basis non autorisee")
    return text


def ensure_conflicting_decision_basis(value: object) -> str:
    text = _ensure_text(value, "decision_basis")
    if text == _FREQUENCY_CONSENSUS_BASIS:
        raise ValueError("consensus par frequence interdit")
    if text != _RECORDED_CONTRADICTION_BASIS:
        raise ValueError("decision_basis conflit non autorisee")
    return text


def ensure_insufficient_decision_basis(value: object) -> str:
    text = _ensure_text(value, "decision_basis")
    if text != _COVERAGE_OBLIGATION_BASIS:
        raise ValueError("decision_basis insuffisance non autorisee")
    return text


def ensure_support_status(value: object) -> SupportStatus:
    if not isinstance(value, SupportStatus):
        raise ValueError("support_status invalide")
    return value


def ensure_assessments(value: object) -> tuple[ContradictionAssessment, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("contradiction_assessments invalides")
    assessments = tuple(value)
    ids: list[str] = []
    for assessment in assessments:
        if not isinstance(assessment, ContradictionAssessment):
            raise ValueError("contradiction_assessment invalide")
        if assessment.contradiction_id in ids:
            raise ValueError("contradiction_assessment duplique")
        ids.append(assessment.contradiction_id)
    return assessments


def ensure_knowledge_gaps(value: object) -> tuple[KnowledgeGap, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("knowledge_gaps invalides")
    gaps = tuple(value)
    ids: list[str] = []
    for gap in gaps:
        if not isinstance(gap, KnowledgeGap):
            raise ValueError("knowledge_gap invalide")
        if gap.gap_id in ids:
            raise ValueError("knowledge_gap duplique")
        ids.append(gap.gap_id)
    return gaps


def ensure_relation_sequence(value: object) -> tuple[object, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("claim_relations invalides")
    relations = tuple(value)
    if len(relations) == 0:
        raise ValueError("claim_relations absentes")
    relation_ids: list[str] = []
    for relation in relations:
        snapshot = _relation_snapshot(relation)
        if snapshot["relation_id"] in relation_ids:
            raise ValueError("claim_relation dupliquee")
        relation_ids.append(snapshot["relation_id"])
    return relations


def ensure_relation_ids(value: object, field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    return _ensure_relation_ids(value, field_name, allow_empty=allow_empty)


def ensure_reason_codes(value: object) -> tuple[str, ...]:
    return _ensure_text_tuple(value, "reason_codes")


def ensure_missing_obligations(value: object) -> tuple[str, ...]:
    return _ensure_text_tuple(value, "missing_obligations")


def ensure_utc_instant(value: object, field_name: str) -> str:
    return _ensure_utc_instant(value, field_name)


def ensure_research_case_id(value: object) -> str:
    return _ensure_research_case_id(value)


def contradiction_id_for_relation(relation: object) -> str:
    return _relation_snapshot(relation)["relation_id"]


def claim_refs_for_relation(relation: object) -> tuple[ClaimRef, ClaimRef]:
    snapshot = _relation_snapshot(relation)
    return snapshot["source_claim_ref"], snapshot["target_claim_ref"]


def _relation_snapshot(value: object) -> dict[str, Any]:
    if value is None:
        raise ValueError("claim_relation absent")
    relation_id = _ensure_relation_id(getattr(value, "relation_id", None))
    relation_type = _enum_text(getattr(value, "relation_type", None), "relation_type")
    scope_compatibility = getattr(value, "scope_compatibility", None)
    if scope_compatibility is None:
        raise ValueError("scope_compatibility absente")
    compared_dimensions = getattr(scope_compatibility, "compared_dimensions", None)
    if tuple(compared_dimensions or ()) != _REQUIRED_SCOPE_DIMENSIONS:
        raise ValueError("scope_dimensions incompletes")
    scope_status = _enum_text(getattr(scope_compatibility, "status", None), "scope_status")
    scope_reason_code = getattr(scope_compatibility, "reason_code", None)
    return {
        "relation_id": relation_id,
        "relation_type": relation_type,
        "source_claim_ref": ClaimRef.from_object(
            getattr(value, "source_claim_ref", None),
            "source_claim_ref",
        ),
        "target_claim_ref": ClaimRef.from_object(
            getattr(value, "target_claim_ref", None),
            "target_claim_ref",
        ),
        "scope_status": scope_status,
        "scope_reason_code": scope_reason_code,
    }


def _enum_text(value: object, field_name: str) -> str:
    if value is None:
        raise ValueError(f"{field_name} absent")
    text = getattr(value, "value", value)
    return _ensure_text(text, field_name)


def _ensure_classification(value: object) -> ContradictionClassification:
    if not isinstance(value, ContradictionClassification):
        raise ValueError("contradiction_classification invalide")
    return value


def _ensure_claim_refs(value: object, field_name: str) -> tuple[ClaimRef, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    refs = tuple(value)
    for ref in refs:
        if not isinstance(ref, ClaimRef):
            raise ValueError(f"{field_name} invalides")
    return refs


def _ensure_text_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_text(item, field_name) for item in value)
    if len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliques")
    return parsed


def _ensure_relation_ids(value: object, field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if value is None or isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalides")
    parsed = tuple(_ensure_relation_id(item) for item in value)
    if not allow_empty and len(parsed) == 0:
        raise ValueError(f"{field_name} absents")
    if len(parsed) != len(set(parsed)):
        raise ValueError(f"{field_name} dupliques")
    return parsed


def _ensure_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _ensure_research_case_id(value: object) -> str:
    text = _ensure_text(value, "research_case_id")
    if _RESEARCH_CASE_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("research_case_id invalide")
    return text


def _ensure_relation_id(value: object) -> str:
    text = _ensure_text(value, "relation_id")
    if _RELATION_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("relation_id invalide")
    return text


def _ensure_claim_id(value: object) -> str:
    text = _ensure_text(value, "claim_id")
    if _CLAIM_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("claim_id invalide")
    return text


def _ensure_gap_id(value: object) -> str:
    text = _ensure_text(value, "gap_id")
    if _GAP_ID_PATTERN.fullmatch(text) is None:
        raise ValueError("gap_id invalide")
    return text


def _ensure_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _ensure_utc_instant(value: object, field_name: str) -> str:
    text = _ensure_text(value, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{field_name} invalide")
    return text


def _gap_id_for(
    *,
    research_case_id: str,
    affected_obligation: str,
    reason_code: str,
) -> str:
    payload = {
        "research_case_id": research_case_id,
        "affected_obligation": affected_obligation,
        "reason_code": reason_code,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"KGP-{digest[:24].upper()}"


__all__ = [
    "ClaimRef",
    "ContradictionAssessment",
    "ContradictionClassification",
    "ContradictionClassificationPolicy",
    "ContradictionDetected",
    "KnowledgeGap",
    "KnowledgeGapRecorded",
    "KnowledgeGapType",
    "ResearchEvidenceFoundConflicting",
    "ResearchEvidenceFoundInsufficient",
    "SupportStatus",
    "claim_refs_for_relation",
    "contradiction_id_for_relation",
    "ensure_assessments",
    "ensure_classification_basis",
    "ensure_conflicting_decision_basis",
    "ensure_insufficient_decision_basis",
    "ensure_knowledge_gaps",
    "ensure_missing_obligations",
    "ensure_reason_codes",
    "ensure_relation_ids",
    "ensure_relation_sequence",
    "ensure_research_case_id",
    "ensure_support_status",
    "ensure_utc_instant",
]
