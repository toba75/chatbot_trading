"""Anti-corruption layer SD pour les résultats de recherche RA."""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from app.contracts.research_outcomes import (
    CONFLICTING_EVIDENCE_STATUS,
    INSUFFICIENT_EVIDENCE_STATUS,
    REQUIRES_CURRENT_DATA_STATUS,
    VerifiedResearchOutcome,
)


BLOCKING_SUPPORT_STATUSES = frozenset(
    {
        CONFLICTING_EVIDENCE_STATUS,
        INSUFFICIENT_EVIDENCE_STATUS,
        REQUIRES_CURRENT_DATA_STATUS,
    }
)
FORBIDDEN_TRANSLATION_DETAIL_KEYS = frozenset(
    {
        "answer_draft",
        "ra_internal_state",
        "rule_expression",
        "strategy_rule",
    }
)
SENSITIVE_TRANSLATION_DETAIL_SUFFIXES = (
    "_api_key",
    "_password",
    "_secret",
    "_token",
)


@dataclass(frozen=True)
class ResearchOutcomeTranslationDecision:
    """Décision de traduction SD, sans règle ni stratégie candidate."""

    decision_type: str
    source_research_case_id: str
    source_answer_id: str
    source_claim_refs: tuple[str, ...]
    description: str
    blocking: bool
    details: Mapping[str, Any]

    def __post_init__(self) -> None:
        _ensure_text_value(self.decision_type, "decision_type")
        _ensure_text_value(self.source_research_case_id, "source_research_case_id")
        _ensure_text_value(self.source_answer_id, "source_answer_id")
        _ensure_claim_ref_tuple(self.source_claim_refs)
        _ensure_text_value(self.description, "description")
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking non booléen")
        _ensure_mapping(self.details, "details")
        object.__setattr__(
            self,
            "details",
            _freeze_translation_value(self.details),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "decision_type": self.decision_type,
            "source_research_case_id": self.source_research_case_id,
            "source_answer_id": self.source_answer_id,
            "source_claim_refs": list(self.source_claim_refs),
            "description": self.description,
            "blocking": self.blocking,
            "details": _thaw_translation_value(self.details),
        }


class StrategyDesignResearchOutcomeTranslator:
    """Traduit le langage RA vers des décisions SD auditables."""

    def translate(
        self,
        outcome: VerifiedResearchOutcome,
    ) -> tuple[ResearchOutcomeTranslationDecision, ...]:
        if not isinstance(outcome, VerifiedResearchOutcome):
            raise ValueError("VerifiedResearchOutcome attendu")

        source_claim_refs = tuple(str(claim_ref) for claim_ref in outcome.claim_refs)
        decisions = [
            ResearchOutcomeTranslationDecision(
                decision_type="SUPPORT_STATUS",
                source_research_case_id=outcome.research_case_id,
                source_answer_id=outcome.answer_id,
                source_claim_refs=source_claim_refs,
                description="Conserver le statut de support RA avant toute formalisation SD.",
                blocking=outcome.support_status in BLOCKING_SUPPORT_STATUSES,
                details={"support_status": outcome.support_status},
            ),
            ResearchOutcomeTranslationDecision(
                decision_type="MANDATE_CONSTRAINT",
                source_research_case_id=outcome.research_case_id,
                source_answer_id=outcome.answer_id,
                source_claim_refs=source_claim_refs,
                description="Traduire le mandat RA en contrainte explicite de conception SD.",
                blocking=False,
                details={"mandate": outcome.mandate},
            ),
            ResearchOutcomeTranslationDecision(
                decision_type="SOURCE_ORIGIN",
                source_research_case_id=outcome.research_case_id,
                source_answer_id=outcome.answer_id,
                source_claim_refs=source_claim_refs,
                description="Conserver les claims vérifiés comme origines disponibles.",
                blocking=False,
                details={"claim_refs": list(source_claim_refs)},
            ),
        ]

        for unresolved_conflict in outcome.unresolved_conflicts:
            decisions.append(
                ResearchOutcomeTranslationDecision(
                    decision_type="UNRESOLVED_CONFLICT",
                    source_research_case_id=outcome.research_case_id,
                    source_answer_id=outcome.answer_id,
                    source_claim_refs=tuple(
                        str(claim_ref) for claim_ref in unresolved_conflict.claim_refs
                    ),
                    description=unresolved_conflict.summary,
                    blocking=unresolved_conflict.blocking,
                    details=unresolved_conflict.to_payload(),
                )
            )

        for knowledge_gap in outcome.knowledge_gaps:
            decisions.append(
                ResearchOutcomeTranslationDecision(
                    decision_type="KNOWLEDGE_GAP",
                    source_research_case_id=outcome.research_case_id,
                    source_answer_id=outcome.answer_id,
                    source_claim_refs=source_claim_refs,
                    description=knowledge_gap.topic,
                    blocking=False,
                    details=knowledge_gap.to_payload(),
                )
            )

        return tuple(decisions)


def _ensure_text_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _ensure_claim_ref_tuple(value: Any) -> None:
    if isinstance(value, str) or not isinstance(value, tuple):
        raise ValueError("source_claim_refs non tuple")
    if len(value) == 0:
        raise ValueError("source_claim_refs vide")
    for claim_ref in value:
        _ensure_text_value(claim_ref, "source_claim_refs")


def _ensure_mapping(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")


def _freeze_translation_value(value: Any) -> Any:
    if value is None:
        raise ValueError("valeur de traduction invalide")
    if isinstance(value, str):
        return _ensure_text_value(value, "valeur de traduction")
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("valeur de traduction invalide")
        return value
    if isinstance(value, Mapping):
        _ensure_mapping(value, "valeur de traduction")
        frozen_mapping: dict[str, Any] = {}
        for key, child_value in value.items():
            normalized_key = _ensure_text_value(key, "clé de traduction").lower()
            if normalized_key in FORBIDDEN_TRANSLATION_DETAIL_KEYS:
                raise ValueError(f"cle interdite: {key}")
            if normalized_key.endswith(SENSITIVE_TRANSLATION_DETAIL_SUFFIXES):
                raise ValueError(f"cle interdite: {key}")
            frozen_mapping[key] = _freeze_translation_value(child_value)
        return MappingProxyType(frozen_mapping)
    if isinstance(value, list):
        if len(value) == 0:
            raise ValueError("valeur de traduction invalide")
        return tuple(_freeze_translation_value(child_value) for child_value in value)
    if isinstance(value, tuple):
        if len(value) == 0:
            raise ValueError("valeur de traduction invalide")
        return tuple(_freeze_translation_value(child_value) for child_value in value)
    raise ValueError("valeur de traduction invalide")


def _thaw_translation_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_translation_value(child_value) for key, child_value in value.items()}
    if isinstance(value, tuple):
        return [_thaw_translation_value(child_value) for child_value in value]
    return value
