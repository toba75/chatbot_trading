"""Contrats publiés de résultats de recherche vérifiée."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.contracts._validation import (
    dumps_contract_json,
    ensure_allowed_fields,
    ensure_utc_instant_value,
    freeze_contract_value,
    thaw_contract_value,
)
from app.contracts.identity import ContractSchemaVersion, DomainIdentifier


RESEARCH_OUTCOME_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTED_STATUS = "SUPPORTED"
PARTIALLY_SUPPORTED_STATUS = "PARTIALLY_SUPPORTED"
INSUFFICIENT_EVIDENCE_STATUS = "INSUFFICIENT_EVIDENCE"
CONFLICTING_EVIDENCE_STATUS = "CONFLICTING_EVIDENCE"
REQUIRES_CURRENT_DATA_STATUS = "REQUIRES_CURRENT_DATA"
ALLOWED_RESEARCH_SUPPORT_STATUSES = frozenset(
    {
        SUPPORTED_STATUS,
        PARTIALLY_SUPPORTED_STATUS,
        INSUFFICIENT_EVIDENCE_STATUS,
        CONFLICTING_EVIDENCE_STATUS,
        REQUIRES_CURRENT_DATA_STATUS,
    }
)

_CLAIM_REF_PATTERN = re.compile(r"^(?P<claim_id>[A-Z]+-[A-Z0-9][A-Z0-9-]*)@(?P<version>[1-9][0-9]*)$")
_VERIFIED_RESEARCH_OUTCOME_FIELDS = frozenset(
    {
        "schema_version",
        "research_case_id",
        "question",
        "mandate",
        "answer_id",
        "support_status",
        "claim_refs",
        "unresolved_conflicts",
        "knowledge_gaps",
        "completed_at",
    }
)
_RESEARCH_CONFLICT_REF_FIELDS = frozenset({"summary", "claim_refs", "blocking"})
_KNOWLEDGE_GAP_REF_FIELDS = frozenset({"topic", "impact"})


@dataclass(frozen=True)
class VersionedClaimRef:
    """Référence compacte vers une version publiée de claim."""

    claim_id: str
    claim_version: int

    @classmethod
    def parse(cls, value: str) -> "VersionedClaimRef":
        _ensure_text_value(value, "claim_ref")
        match = _CLAIM_REF_PATTERN.fullmatch(value)
        if match is None:
            raise ValueError(f"claim_ref invalide: {value}")

        claim_id = str(DomainIdentifier.parse_with_prefix(match.group("claim_id"), "CLM"))
        return cls(claim_id=claim_id, claim_version=int(match.group("version")))

    def __str__(self) -> str:
        return f"{self.claim_id}@{self.claim_version}"


@dataclass(frozen=True)
class ResearchConflictRef:
    """Conflit non résolu transmis explicitement de RA vers SD."""

    summary: str
    claim_refs: tuple[VersionedClaimRef, ...]
    blocking: bool

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ResearchConflictRef":
        _ensure_mapping(payload, "unresolved_conflicts")
        ensure_allowed_fields(payload, _RESEARCH_CONFLICT_REF_FIELDS, "ResearchConflictRef")
        return cls(
            summary=_required_text(payload, "summary"),
            claim_refs=_required_claim_refs(payload, "claim_refs", allow_empty=False),
            blocking=_required_bool(payload, "blocking"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "claim_refs": [str(claim_ref) for claim_ref in self.claim_refs],
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class KnowledgeGapRef:
    """Lacune de connaissance conservée avant formalisation de stratégie."""

    topic: str
    impact: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "KnowledgeGapRef":
        _ensure_mapping(payload, "knowledge_gaps")
        ensure_allowed_fields(payload, _KNOWLEDGE_GAP_REF_FIELDS, "KnowledgeGapRef")
        return cls(
            topic=_required_text(payload, "topic"),
            impact=_required_text(payload, "impact"),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "impact": self.impact,
        }


@dataclass(frozen=True)
class VerifiedResearchOutcome:
    """Résultat RA publié vers SD sans exposer le modèle interne de recherche."""

    schema_version: str
    research_case_id: str
    question: str
    mandate: Mapping[str, Any]
    answer_id: str
    support_status: str
    claim_refs: tuple[VersionedClaimRef, ...]
    unresolved_conflicts: tuple[ResearchConflictRef, ...]
    knowledge_gaps: tuple[KnowledgeGapRef, ...]
    completed_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "VerifiedResearchOutcome":
        ensure_allowed_fields(payload, _VERIFIED_RESEARCH_OUTCOME_FIELDS, "VerifiedResearchOutcome")
        schema_version = ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=RESEARCH_OUTCOME_SCHEMA_VERSIONS,
        )
        support_status = _required_support_status(payload)
        unresolved_conflicts = _required_unresolved_conflicts(payload)
        _ensure_conflict_visibility(
            support_status=support_status,
            unresolved_conflicts=unresolved_conflicts,
        )
        knowledge_gaps = _required_knowledge_gaps(payload)
        _ensure_knowledge_gap_visibility(
            support_status=support_status,
            knowledge_gaps=knowledge_gaps,
        )

        return cls(
            schema_version=str(schema_version),
            research_case_id=_required_domain_identifier(payload, "research_case_id", "RSC"),
            question=_required_text(payload, "question"),
            mandate=_required_mandate(payload),
            answer_id=_required_domain_identifier(payload, "answer_id", "ANS"),
            support_status=support_status,
            claim_refs=_required_claim_refs(payload, "claim_refs"),
            unresolved_conflicts=unresolved_conflicts,
            knowledge_gaps=knowledge_gaps,
            completed_at=_required_utc_instant(payload, "completed_at"),
        )

    @classmethod
    def from_json(cls, serialized_payload: str) -> "VerifiedResearchOutcome":
        return cls.from_payload(_loads_contract_json(serialized_payload))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "research_case_id": self.research_case_id,
            "question": self.question,
            "mandate": thaw_contract_value(self.mandate),
            "answer_id": self.answer_id,
            "support_status": self.support_status,
            "claim_refs": [str(claim_ref) for claim_ref in self.claim_refs],
            "unresolved_conflicts": [
                unresolved_conflict.to_payload()
                for unresolved_conflict in self.unresolved_conflicts
            ],
            "knowledge_gaps": [knowledge_gap.to_payload() for knowledge_gap in self.knowledge_gaps],
            "completed_at": self.completed_at,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_payload())


def _ensure_conflict_visibility(
    support_status: str,
    unresolved_conflicts: tuple[ResearchConflictRef, ...],
) -> None:
    if support_status == CONFLICTING_EVIDENCE_STATUS and len(unresolved_conflicts) == 0:
        raise ValueError("unresolved_conflicts requis pour CONFLICTING_EVIDENCE")
    if support_status != CONFLICTING_EVIDENCE_STATUS and len(unresolved_conflicts) > 0:
        raise ValueError("support_status masque des conflits non résolus")


def _required_support_status(payload: Mapping[str, Any]) -> str:
    support_status = _required_text(payload, "support_status")
    if support_status not in ALLOWED_RESEARCH_SUPPORT_STATUSES:
        raise ValueError(f"support_status non autorisé: {support_status}")
    return support_status


def _ensure_knowledge_gap_visibility(
    support_status: str,
    knowledge_gaps: tuple[KnowledgeGapRef, ...],
) -> None:
    if support_status in {INSUFFICIENT_EVIDENCE_STATUS, REQUIRES_CURRENT_DATA_STATUS}:
        if len(knowledge_gaps) == 0:
            raise ValueError(f"knowledge_gaps requis pour {support_status}")


def _required_mandate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if "mandate" not in payload:
        raise ValueError("mandate absent")
    mandate = payload["mandate"]
    if not isinstance(mandate, Mapping):
        raise ValueError("mandate non objet")
    if len(mandate) == 0:
        raise ValueError("mandate vide")
    return freeze_contract_value(mandate, "valeur de contrat")


def _required_claim_refs(
    payload: Mapping[str, Any],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[VersionedClaimRef, ...]:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")

    claim_ref_values = payload[field_name]
    if isinstance(claim_ref_values, str) or not hasattr(claim_ref_values, "__iter__"):
        raise ValueError(f"{field_name} non liste")

    parsed_claim_refs = []
    for claim_ref_value in claim_ref_values:
        try:
            parsed_claim_refs.append(VersionedClaimRef.parse(claim_ref_value))
        except ValueError as exc:
            raise ValueError(f"{field_name} invalide: {exc}") from exc

    if len(parsed_claim_refs) == 0 and not allow_empty:
        raise ValueError(f"{field_name} vide")

    return tuple(parsed_claim_refs)


def _required_unresolved_conflicts(payload: Mapping[str, Any]) -> tuple[ResearchConflictRef, ...]:
    if "unresolved_conflicts" not in payload:
        raise ValueError("unresolved_conflicts absent")

    conflict_payloads = payload["unresolved_conflicts"]
    if isinstance(conflict_payloads, str) or not hasattr(conflict_payloads, "__iter__"):
        raise ValueError("unresolved_conflicts non liste")

    parsed_conflicts = []
    for conflict_payload in conflict_payloads:
        try:
            parsed_conflicts.append(ResearchConflictRef.from_payload(conflict_payload))
        except ValueError as exc:
            raise ValueError(f"unresolved_conflicts invalide: {exc}") from exc

    return tuple(parsed_conflicts)


def _required_knowledge_gaps(payload: Mapping[str, Any]) -> tuple[KnowledgeGapRef, ...]:
    if "knowledge_gaps" not in payload:
        raise ValueError("knowledge_gaps absent")

    knowledge_gap_payloads = payload["knowledge_gaps"]
    if isinstance(knowledge_gap_payloads, str) or not hasattr(knowledge_gap_payloads, "__iter__"):
        raise ValueError("knowledge_gaps non liste")

    parsed_knowledge_gaps = []
    for knowledge_gap_payload in knowledge_gap_payloads:
        try:
            parsed_knowledge_gaps.append(KnowledgeGapRef.from_payload(knowledge_gap_payload))
        except ValueError as exc:
            raise ValueError(f"knowledge_gaps invalide: {exc}") from exc

    return tuple(parsed_knowledge_gaps)


def _required_domain_identifier(
    payload: Mapping[str, Any],
    field_name: str,
    expected_prefix: str,
) -> str:
    value = _required_text(payload, field_name)
    try:
        return str(DomainIdentifier.parse_with_prefix(value, expected_prefix))
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide: {exc}") from exc


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return _ensure_text_value(payload[field_name], field_name)


def _ensure_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _required_bool(payload: Mapping[str, Any], field_name: str) -> bool:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booléen")
    return value


def _required_utc_instant(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    return ensure_utc_instant_value(value, field_name)


def _loads_contract_json(serialized_payload: str) -> Mapping[str, Any]:
    _ensure_text_value(serialized_payload, "contrat serialise")
    payload = json.loads(serialized_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("Contrat publié non objet.")
    return payload


def _dumps_contract_json(payload: Mapping[str, Any]) -> str:
    return dumps_contract_json(payload)


def _ensure_mapping(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
