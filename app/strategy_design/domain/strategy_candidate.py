"""Agrégat SD pour l'ouverture d'une stratégie candidate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from app.contracts.identity import DomainIdentifier
from app.contracts.research_outcomes import VerifiedResearchOutcome


class StrategyCandidateStatus:
    DRAFT = "DRAFT"
    SPECIFIED = "SPECIFIED"


class StrategyConcurrencyError(RuntimeError):
    def __init__(self, strategy_id: str, expected_version: int, actual_version: int) -> None:
        self.strategy_id = strategy_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            "version obsolète pour "
            f"{strategy_id}: attendue {expected_version}, actuelle {actual_version}"
        )


class StrategyCandidateNotFoundError(RuntimeError):
    def __init__(self, strategy_id: str) -> None:
        self.strategy_id = strategy_id
        super().__init__(f"stratégie candidate absente: {strategy_id}")


@dataclass(frozen=True)
class StrategyMandate:
    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "StrategyMandate":
        if not isinstance(payload, Mapping):
            raise ValueError("mandat SD non objet")
        if len(payload) == 0:
            raise ValueError("mandat SD vide")
        return cls(payload=_freeze_strategy_payload(payload, "mandat SD"))

    def to_payload(self) -> dict[str, Any]:
        return _thaw_strategy_value(self.payload)

    def hash(self) -> str:
        serialized_payload = json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VerifiedResearchRef:
    research_case_id: str
    answer_id: str
    claim_refs: tuple[str, ...]
    support_status: str

    @classmethod
    def from_outcome(cls, outcome: VerifiedResearchOutcome) -> "VerifiedResearchRef":
        if not isinstance(outcome, VerifiedResearchOutcome):
            raise ValueError("VerifiedResearchOutcome attendu")

        claim_refs = tuple(str(claim_ref) for claim_ref in outcome.claim_refs)
        if len(claim_refs) == 0:
            raise ValueError("claim_refs SD requis")

        return cls(
            research_case_id=outcome.research_case_id,
            answer_id=outcome.answer_id,
            claim_refs=claim_refs,
            support_status=outcome.support_status,
        )


@dataclass(frozen=True)
class StrategyTranslationDecision:
    decision_type: str
    source_research_case_id: str
    source_answer_id: str
    source_claim_refs: tuple[str, ...]
    description: str
    blocking: bool
    details: Mapping[str, Any]

    @classmethod
    def from_translation(cls, decision: Any) -> "StrategyTranslationDecision":
        decision_type = _required_attribute_text(decision, "decision_type")
        if decision_type in _FORBIDDEN_DECISION_TYPES:
            raise ValueError(f"décision de traduction interdite: {decision_type}")

        source_claim_refs = _required_claim_ref_tuple(
            _required_attribute(decision, "source_claim_refs")
        )
        blocking = _required_attribute(decision, "blocking")
        if not isinstance(blocking, bool):
            raise ValueError("blocking non booléen")

        details = _required_attribute(decision, "details")
        if not isinstance(details, Mapping):
            raise ValueError("details de traduction non objet")
        if len(details) == 0:
            raise ValueError("details de traduction vides")

        return cls(
            decision_type=decision_type,
            source_research_case_id=_required_attribute_text(decision, "source_research_case_id"),
            source_answer_id=_required_attribute_text(decision, "source_answer_id"),
            source_claim_refs=source_claim_refs,
            description=_required_attribute_text(decision, "description"),
            blocking=blocking,
            details=_freeze_strategy_value(details),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "decision_type": self.decision_type,
            "source_research_case_id": self.source_research_case_id,
            "source_answer_id": self.source_answer_id,
            "source_claim_refs": list(self.source_claim_refs),
            "description": self.description,
            "blocking": self.blocking,
            "details": _thaw_strategy_value(self.details),
        }


@dataclass(frozen=True)
class StrategyTranslationDiagnostic:
    code: str
    description: str
    blocking: bool
    source_decision_type: str

    @classmethod
    def from_decision(cls, decision: StrategyTranslationDecision) -> "StrategyTranslationDiagnostic":
        if decision.decision_type == "SUPPORT_STATUS":
            code = _required_mapping_text(decision.details, "support_status")
        elif decision.decision_type == "KNOWLEDGE_GAP":
            code = "KNOWLEDGE_GAP"
        elif decision.decision_type == "UNRESOLVED_CONFLICT":
            code = "UNRESOLVED_CONFLICT"
        else:
            code = "TRANSLATION_DECISION"

        return cls(
            code=code,
            description=decision.description,
            blocking=decision.blocking,
            source_decision_type=decision.decision_type,
        )


@dataclass(frozen=True)
class StrategyCandidateCreated:
    strategy_id: str
    strategy_version: int
    mandate_hash: str
    verified_research_ref: VerifiedResearchRef

    @property
    def event_type(self) -> str:
        return "StrategyCandidateCreated"


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    version: int
    status: str
    mandate: StrategyMandate
    verified_research_ref: VerifiedResearchRef
    translation_decisions: tuple[StrategyTranslationDecision, ...]
    translation_diagnostics: tuple[StrategyTranslationDiagnostic, ...]
    rules: tuple[Mapping[str, Any], ...]
    domain_events: tuple[StrategyCandidateCreated, ...]

    @classmethod
    def create_from_verified_research(
        cls,
        *,
        strategy_id: str,
        verified_research: VerifiedResearchOutcome,
        translation_decisions: Sequence[Any],
        expected_version: int,
    ) -> "StrategyCandidate":
        _ensure_strategy_id(strategy_id)
        _ensure_expected_initial_version(expected_version)
        verified_research_ref = VerifiedResearchRef.from_outcome(verified_research)
        mandate = StrategyMandate.from_payload(verified_research.mandate)
        decisions = _create_translation_decisions(
            translation_decisions=translation_decisions,
            verified_research_ref=verified_research_ref,
        )
        diagnostics = tuple(StrategyTranslationDiagnostic.from_decision(decision) for decision in decisions)
        version = 1
        created_event = StrategyCandidateCreated(
            strategy_id=strategy_id,
            strategy_version=version,
            mandate_hash=mandate.hash(),
            verified_research_ref=verified_research_ref,
        )
        return cls(
            strategy_id=strategy_id,
            version=version,
            status=StrategyCandidateStatus.DRAFT,
            mandate=mandate,
            verified_research_ref=verified_research_ref,
            translation_decisions=decisions,
            translation_diagnostics=diagnostics,
            rules=(),
            domain_events=(created_event,),
        )


_FORBIDDEN_DECISION_TYPES = frozenset({"RULE_EXPRESSION", "STRATEGY_RULE"})
_FORBIDDEN_DETAIL_KEYS = frozenset(
    {
        "answer_draft",
        "prompt_text",
        "ra_internal_state",
        "raw_research_payload",
        "rule_expression",
        "strategy_rule",
    }
)
_SENSITIVE_DETAIL_SUFFIXES = ("_api_key", "_password", "_secret", "_token")


def _create_translation_decisions(
    *,
    translation_decisions: Sequence[Any],
    verified_research_ref: VerifiedResearchRef,
) -> tuple[StrategyTranslationDecision, ...]:
    if isinstance(translation_decisions, str) or not isinstance(translation_decisions, Sequence):
        raise ValueError("décisions de traduction SD non liste")

    decisions = tuple(
        StrategyTranslationDecision.from_translation(decision)
        for decision in translation_decisions
    )
    if len(decisions) == 0:
        raise ValueError("décisions de traduction SD vides")

    for decision in decisions:
        if decision.source_research_case_id != verified_research_ref.research_case_id:
            raise ValueError("décision de traduction rattachée à un research_case_id différent")
        if decision.source_answer_id != verified_research_ref.answer_id:
            raise ValueError("décision de traduction rattachée à un answer_id différent")

    return decisions


def _ensure_strategy_id(value: str) -> str:
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "STRAT"))
    except ValueError as exc:
        raise ValueError(f"strategy_id SD invalide: {exc}") from exc


def _ensure_expected_initial_version(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("version attendue initiale non entière")
    if value != 0:
        raise ValueError("version attendue initiale invalide")


def _ensure_repository_expected_version(value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("version attendue non entière")
    if value < 0:
        raise ValueError("version attendue négative")


def _required_attribute(value: Any, attribute_name: str) -> Any:
    if not hasattr(value, attribute_name):
        raise ValueError(f"attribut de traduction absent: {attribute_name}")
    return getattr(value, attribute_name)


def _required_attribute_text(value: Any, attribute_name: str) -> str:
    return _ensure_text(_required_attribute(value, attribute_name), attribute_name)


def _required_mapping_text(value: Mapping[str, Any], field_name: str) -> str:
    if field_name not in value:
        raise ValueError(f"{field_name} absent")
    return _ensure_text(value[field_name], field_name)


def _required_claim_ref_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, tuple):
        raise ValueError("source_claim_refs non tuple")
    if len(value) == 0:
        raise ValueError("source_claim_refs vide")
    return tuple(_ensure_text(claim_ref, "source_claim_refs") for claim_ref in value)


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _freeze_strategy_value(value: Any) -> Any:
    if value is None:
        raise ValueError("valeur de traduction invalide")
    if isinstance(value, str):
        return _ensure_text(value, "valeur de traduction")
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("valeur de traduction invalide")
        return value
    if isinstance(value, Mapping):
        if len(value) == 0:
            raise ValueError("valeur de traduction vide")
        frozen_mapping: dict[str, Any] = {}
        for key, child_value in value.items():
            normalized_key = _ensure_text(key, "clé de traduction").lower()
            if normalized_key in _FORBIDDEN_DETAIL_KEYS:
                raise ValueError(f"clé de traduction interdite: {key}")
            if normalized_key.endswith(_SENSITIVE_DETAIL_SUFFIXES):
                raise ValueError(f"clé de traduction interdite: {key}")
            frozen_mapping[key] = _freeze_strategy_value(child_value)
        return MappingProxyType(frozen_mapping)
    if isinstance(value, list):
        if len(value) == 0:
            raise ValueError("valeur de traduction vide")
        return tuple(_freeze_strategy_value(child_value) for child_value in value)
    if isinstance(value, tuple):
        if len(value) == 0:
            raise ValueError("valeur de traduction vide")
        return tuple(_freeze_strategy_value(child_value) for child_value in value)
    raise ValueError("valeur de traduction invalide")


def _freeze_strategy_payload(value: Any, field_name: str) -> Any:
    if value is None:
        raise ValueError(f"{field_name} invalide")
    if isinstance(value, str):
        return _ensure_text(value, field_name)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} invalide")
        return value
    if isinstance(value, Mapping):
        if len(value) == 0:
            raise ValueError(f"{field_name} vide")
        return MappingProxyType(
            {
                _ensure_text(key, f"clé {field_name}"): _freeze_strategy_payload(
                    child_value,
                    field_name,
                )
                for key, child_value in value.items()
            }
        )
    if isinstance(value, list):
        return tuple(_freeze_strategy_payload(child_value, field_name) for child_value in value)
    if isinstance(value, tuple):
        return tuple(_freeze_strategy_payload(child_value, field_name) for child_value in value)
    raise ValueError(f"{field_name} invalide")


def _thaw_strategy_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_strategy_value(child_value) for key, child_value in value.items()}
    if isinstance(value, tuple):
        return [_thaw_strategy_value(child_value) for child_value in value]
    return value
