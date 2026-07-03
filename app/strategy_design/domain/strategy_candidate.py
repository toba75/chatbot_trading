"""Agrégat SD pour l'ouverture d'une stratégie candidate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.identity import DomainIdentifier
from app.contracts.research_outcomes import VerifiedResearchOutcome, VersionedClaimRef


class StrategyCandidateStatus:
    DRAFT = "DRAFT"
    SPECIFIED = "SPECIFIED"
    INCOMPLETE = "INCOMPLETE"


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


class RuleOriginType(str, Enum):
    SOURCE = "SOURCE"
    DEDUCTION = "DEDUCTION"
    DESIGN_CHOICE = "DESIGN_CHOICE"
    PARAMETER_TO_CALIBRATE = "PARAMETER_TO_CALIBRATE"
    USER_CONSTRAINT = "USER_CONSTRAINT"


@dataclass(frozen=True)
class CompilationDiagnostic:
    code: str
    description: str
    blocking: bool
    rule_id: str | None

    def __post_init__(self) -> None:
        _ensure_text(self.code, "code diagnostic")
        _ensure_text(self.description, "description diagnostic")
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking diagnostic non booléen")
        if self.rule_id is not None:
            _ensure_text(self.rule_id, "rule_id diagnostic")


@dataclass(frozen=True)
class RuleExpression:
    text: str

    @classmethod
    def from_text(cls, value: str) -> "RuleExpression":
        return cls(text=_ensure_text(value, "expression de règle"))

    def __post_init__(self) -> None:
        _ensure_text(self.text, "expression de règle")


@dataclass(frozen=True)
class RuleOrigin:
    origin_type: RuleOriginType
    verified_claim_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    premises: tuple[str, ...]
    transformation: str | None
    justification: str | None
    mandate_impact: str | None
    calibration_domain: Mapping[str, Any] | None
    calibration_protocol: str | None
    mandate_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if isinstance(self.origin_type, str) and not isinstance(self.origin_type, RuleOriginType):
            raise ValueError("origin_type libre interdit")
        if not isinstance(self.origin_type, RuleOriginType):
            raise ValueError("origin_type de règle invalide")
        object.__setattr__(
            self,
            "verified_claim_refs",
            tuple(
                _normalize_verified_claim_ref_value(claim_ref)
                for claim_ref in self.verified_claim_refs
            ),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(_normalize_evidence_ref_value(evidence_ref) for evidence_ref in self.evidence_refs),
        )
        object.__setattr__(
            self,
            "premises",
            tuple(_ensure_text(premise, "prémisse de règle") for premise in self.premises),
        )
        object.__setattr__(
            self,
            "transformation",
            _ensure_origin_optional_text(self.transformation, "transformation de règle"),
        )
        object.__setattr__(
            self,
            "justification",
            _ensure_origin_optional_text(self.justification, "justification de choix"),
        )
        object.__setattr__(
            self,
            "mandate_impact",
            _ensure_origin_optional_text(self.mandate_impact, "impact mandat"),
        )
        if self.calibration_domain is not None:
            object.__setattr__(
                self,
                "calibration_domain",
                _freeze_origin_mapping(self.calibration_domain),
            )
        object.__setattr__(
            self,
            "calibration_protocol",
            _ensure_origin_optional_text(self.calibration_protocol, "protocole de calibration"),
        )
        object.__setattr__(
            self,
            "mandate_refs",
            tuple(_ensure_text(mandate_ref, "référence mandat") for mandate_ref in self.mandate_refs),
        )

    @classmethod
    def source(
        cls,
        *,
        verified_claim_refs: tuple[Any, ...],
        evidence_refs: tuple[Any, ...],
    ) -> "RuleOrigin":
        return cls(
            origin_type=RuleOriginType.SOURCE,
            verified_claim_refs=verified_claim_refs,
            evidence_refs=evidence_refs,
            premises=(),
            transformation=None,
            justification=None,
            mandate_impact=None,
            calibration_domain=None,
            calibration_protocol=None,
            mandate_refs=(),
        )

    @classmethod
    def deduction(
        cls,
        *,
        premises: tuple[str, ...],
        transformation: str,
    ) -> "RuleOrigin":
        return cls(
            origin_type=RuleOriginType.DEDUCTION,
            verified_claim_refs=(),
            evidence_refs=(),
            premises=premises,
            transformation=transformation,
            justification=None,
            mandate_impact=None,
            calibration_domain=None,
            calibration_protocol=None,
            mandate_refs=(),
        )

    @classmethod
    def design_choice(
        cls,
        *,
        justification: str,
        mandate_impact: str,
    ) -> "RuleOrigin":
        return cls(
            origin_type=RuleOriginType.DESIGN_CHOICE,
            verified_claim_refs=(),
            evidence_refs=(),
            premises=(),
            transformation=None,
            justification=justification,
            mandate_impact=mandate_impact,
            calibration_domain=None,
            calibration_protocol=None,
            mandate_refs=(),
        )

    @classmethod
    def parameter_to_calibrate(
        cls,
        *,
        calibration_domain: Mapping[str, Any],
        calibration_protocol: str,
    ) -> "RuleOrigin":
        return cls(
            origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
            verified_claim_refs=(),
            evidence_refs=(),
            premises=(),
            transformation=None,
            justification=None,
            mandate_impact=None,
            calibration_domain=calibration_domain,
            calibration_protocol=calibration_protocol,
            mandate_refs=(),
        )

    @classmethod
    def user_constraint(cls, *, mandate_refs: tuple[str, ...]) -> "RuleOrigin":
        return cls(
            origin_type=RuleOriginType.USER_CONSTRAINT,
            verified_claim_refs=(),
            evidence_refs=(),
            premises=(),
            transformation=None,
            justification=None,
            mandate_impact=None,
            calibration_domain=None,
            calibration_protocol=None,
            mandate_refs=mandate_refs,
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "RuleOrigin":
        if not isinstance(payload, Mapping):
            raise ValueError("RuleOrigin non objet")
        origin_type_value = _required_mapping_text(payload, "origin_type")
        try:
            origin_type = RuleOriginType(origin_type_value)
        except ValueError as exc:
            raise ValueError(f"origine de regle inconnue: {origin_type_value}") from exc

        if origin_type is RuleOriginType.SOURCE:
            return cls.source(
                verified_claim_refs=_required_origin_tuple(payload, "verified_claim_refs"),
                evidence_refs=_required_origin_tuple(payload, "evidence_refs"),
            )
        if origin_type is RuleOriginType.DEDUCTION:
            return cls.deduction(
                premises=_required_origin_tuple(payload, "premises"),
                transformation=_required_mapping_origin_text(payload, "transformation"),
            )
        if origin_type is RuleOriginType.DESIGN_CHOICE:
            return cls.design_choice(
                justification=_required_mapping_origin_text(payload, "justification"),
                mandate_impact=_required_mapping_origin_text(payload, "mandate_impact"),
            )
        if origin_type is RuleOriginType.PARAMETER_TO_CALIBRATE:
            if "calibration_domain" not in payload or not isinstance(payload["calibration_domain"], Mapping):
                raise ValueError("calibration_domain absent")
            return cls.parameter_to_calibrate(
                calibration_domain=payload["calibration_domain"],
                calibration_protocol=_required_mapping_origin_text(payload, "calibration_protocol"),
            )
        return cls.user_constraint(mandate_refs=_required_origin_tuple(payload, "mandate_refs"))

    @property
    def evidence_ref_count(self) -> int:
        return len(self.evidence_refs) + len(
            tuple(
                claim_ref
                for claim_ref in self.verified_claim_refs
                if _is_versioned_claim_ref(claim_ref)
            )
        )


@dataclass(frozen=True)
class StrategyRule:
    rule_id: str
    rule_kind: str
    expression: RuleExpression
    origin: RuleOrigin | None

    def __post_init__(self) -> None:
        _ensure_text(self.rule_id, "rule_id")
        _ensure_text(self.rule_kind, "rule_kind")
        if not isinstance(self.expression, RuleExpression):
            raise ValueError("RuleExpression attendue")
        if self.origin is not None and not isinstance(self.origin, RuleOrigin):
            raise ValueError("RuleOrigin attendue")

    @classmethod
    def without_origin(
        cls,
        *,
        rule_id: str,
        rule_kind: str,
        expression: RuleExpression,
    ) -> "StrategyRule":
        return cls(
            rule_id=rule_id,
            rule_kind=rule_kind,
            expression=expression,
            origin=None,
        )

    @classmethod
    def with_origin(
        cls,
        *,
        rule_id: str,
        rule_kind: str,
        expression: RuleExpression,
        origin: RuleOrigin,
    ) -> "StrategyRule":
        return cls(
            rule_id=rule_id,
            rule_kind=rule_kind,
            expression=expression,
            origin=origin,
        )

    def assign_origin(self, origin: RuleOrigin) -> "StrategyRule":
        if not isinstance(origin, RuleOrigin):
            raise ValueError("RuleOrigin attendue")
        return replace(self, origin=origin)


class RuleOriginPolicy:
    def validate_rule(self, rule: StrategyRule) -> tuple[CompilationDiagnostic, ...]:
        if not isinstance(rule, StrategyRule):
            raise ValueError("StrategyRule attendue")

        if rule.origin is None:
            return (
                _rule_diagnostic(
                    code="RULE_ORIGIN_REQUIRED",
                    rule_id=rule.rule_id,
                    description="Règle de stratégie sans origine autorisée.",
                ),
            )

        origin = rule.origin
        if origin.origin_type is RuleOriginType.SOURCE:
            if origin.evidence_ref_count == 0:
                return (
                    _rule_diagnostic(
                        code="SOURCE_EVIDENCE_REQUIRED",
                        rule_id=rule.rule_id,
                        description="Origine SOURCE sans VerifiedClaimRef versionné ni EvidenceRef.",
                    ),
                )
            return ()

        if origin.origin_type is RuleOriginType.DEDUCTION:
            if len(origin.premises) == 0 or _is_blank_origin_text(origin.transformation):
                return (
                    _rule_diagnostic(
                        code="RULE_ORIGIN_REQUIRED",
                        rule_id=rule.rule_id,
                        description="Déduction sans prémisses explicites ou transformation.",
                    ),
                )
            return ()

        if origin.origin_type is RuleOriginType.DESIGN_CHOICE:
            if _is_blank_origin_text(origin.justification) or _is_blank_origin_text(origin.mandate_impact):
                return (
                    _rule_diagnostic(
                        code="DESIGN_CHOICE_JUSTIFICATION_REQUIRED",
                        rule_id=rule.rule_id,
                        description="Choix de conception sans justification opérationnelle.",
                    ),
                )
            return ()

        if origin.origin_type is RuleOriginType.PARAMETER_TO_CALIBRATE:
            if _is_empty_mapping(origin.calibration_domain) or _is_blank_origin_text(origin.calibration_protocol):
                return (
                    _rule_diagnostic(
                        code="PARAMETER_CALIBRATION_REQUIRED",
                        rule_id=rule.rule_id,
                        description="Paramètre à calibrer sans domaine ou protocole.",
                    ),
                )
            return ()

        if len(origin.mandate_refs) == 0:
            return (
                _rule_diagnostic(
                    code="STRATEGY_MANDATE_REQUIRED",
                    rule_id=rule.rule_id,
                    description="Contrainte utilisateur sans référence au mandat.",
                ),
            )
        return ()


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
class StrategyRuleAdded:
    strategy_id: str
    strategy_version: int
    rule_id: str
    rule_kind: str

    @property
    def event_type(self) -> str:
        return "StrategyRuleAdded"


@dataclass(frozen=True)
class RuleOriginAssigned:
    strategy_id: str
    rule_id: str
    origin_type: str
    evidence_ref_count: int

    @property
    def event_type(self) -> str:
        return "RuleOriginAssigned"


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    version: int
    status: str
    mandate: StrategyMandate
    verified_research_ref: VerifiedResearchRef
    translation_decisions: tuple[StrategyTranslationDecision, ...]
    translation_diagnostics: tuple[StrategyTranslationDiagnostic, ...]
    compilation_diagnostics: tuple[CompilationDiagnostic, ...]
    rules: tuple[StrategyRule, ...]
    domain_events: tuple[object, ...]

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
            compilation_diagnostics=(),
            rules=(),
            domain_events=(created_event,),
        )

    def add_rule(
        self,
        *,
        rule: StrategyRule,
        expected_version: int,
    ) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        if not isinstance(rule, StrategyRule):
            raise ValueError("StrategyRule attendue")
        if any(existing_rule.rule_id == rule.rule_id for existing_rule in self.rules):
            raise ValueError(f"règle de stratégie déjà présente: {rule.rule_id}")

        new_version = self.version + 1
        return replace(
            self,
            version=new_version,
            status=StrategyCandidateStatus.SPECIFIED,
            compilation_diagnostics=(),
            rules=self.rules + (rule,),
            domain_events=self.domain_events
            + (
                StrategyRuleAdded(
                    strategy_id=self.strategy_id,
                    strategy_version=new_version,
                    rule_id=rule.rule_id,
                    rule_kind=rule.rule_kind,
                ),
            ),
        )

    def assign_rule_origin(
        self,
        *,
        rule_id: str,
        origin: RuleOrigin,
        expected_version: int,
    ) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        _ensure_text(rule_id, "rule_id")
        if not isinstance(origin, RuleOrigin):
            raise ValueError("RuleOrigin attendue")

        updated_rules = []
        matched = False
        for rule in self.rules:
            if rule.rule_id == rule_id:
                updated_rules.append(rule.assign_origin(origin))
                matched = True
            else:
                updated_rules.append(rule)
        if not matched:
            raise ValueError(f"règle de stratégie absente: {rule_id}")

        return replace(
            self,
            version=self.version + 1,
            status=StrategyCandidateStatus.SPECIFIED,
            compilation_diagnostics=(),
            rules=tuple(updated_rules),
            domain_events=self.domain_events
            + (
                RuleOriginAssigned(
                    strategy_id=self.strategy_id,
                    rule_id=rule_id,
                    origin_type=origin.origin_type.value,
                    evidence_ref_count=origin.evidence_ref_count,
                ),
            ),
        )

    def validate_for_compilation(self, *, expected_version: int) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        diagnostics = tuple(
            diagnostic
            for rule in self.rules
            for diagnostic in RuleOriginPolicy().validate_rule(rule)
        )
        next_status = (
            StrategyCandidateStatus.INCOMPLETE
            if any(diagnostic.blocking for diagnostic in diagnostics)
            else StrategyCandidateStatus.SPECIFIED
        )
        return replace(
            self,
            version=self.version + 1,
            status=next_status,
            compilation_diagnostics=diagnostics,
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


def _ensure_current_candidate_version(
    candidate: StrategyCandidate,
    expected_version: int,
) -> None:
    _ensure_repository_expected_version(expected_version)
    if candidate.version != expected_version:
        raise StrategyConcurrencyError(
            candidate.strategy_id,
            expected_version,
            candidate.version,
        )


def _rule_diagnostic(
    *,
    code: str,
    rule_id: str,
    description: str,
) -> CompilationDiagnostic:
    return CompilationDiagnostic(
        code=code,
        description=description,
        blocking=True,
        rule_id=rule_id,
    )


def _required_origin_tuple(payload: Mapping[str, Any], field_name: str) -> tuple[Any, ...]:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    values = payload[field_name]
    if isinstance(values, str) or not hasattr(values, "__iter__"):
        raise ValueError(f"{field_name} non liste")
    return tuple(values)


def _required_mapping_origin_text(value: Mapping[str, Any], field_name: str) -> str:
    if field_name not in value:
        raise ValueError(f"{field_name} absent")
    text_value = _ensure_origin_optional_text(value[field_name], field_name)
    if text_value is None:
        raise ValueError(f"{field_name} absent")
    return text_value


def _ensure_origin_optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalisé")
    return value


def _normalize_verified_claim_ref_value(value: Any) -> str:
    if isinstance(value, VersionedClaimRef):
        return str(value)
    if isinstance(value, VerifiedClaimRef):
        return f"{value.claim_id}@{value.claim_version}"
    return _ensure_text(value, "verified_claim_refs")


def _normalize_evidence_ref_value(value: Any) -> str:
    if isinstance(value, EvidenceRef):
        return value.evidence_id
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "EVS"))
    except ValueError as exc:
        raise ValueError(f"evidence_refs invalide: {exc}") from exc


def _is_versioned_claim_ref(value: str) -> bool:
    try:
        VersionedClaimRef.parse(value)
    except ValueError:
        return False
    return True


def _is_blank_origin_text(value: str | None) -> bool:
    return value is None or value == ""


def _is_empty_mapping(value: Mapping[str, Any] | None) -> bool:
    return value is None or len(value) == 0


def _freeze_origin_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("calibration_domain non objet")
    return MappingProxyType(
        {
            _ensure_text(key, "clé calibration_domain"): _freeze_origin_value(child_value)
            for key, child_value in value.items()
        }
    )


def _freeze_origin_value(value: Any) -> Any:
    if value is None:
        raise ValueError("valeur d'origine invalide")
    if isinstance(value, str):
        return _ensure_text(value, "valeur d'origine")
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("valeur d'origine invalide")
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                _ensure_text(key, "clé d'origine"): _freeze_origin_value(child_value)
                for key, child_value in value.items()
            }
        )
    if isinstance(value, list):
        return tuple(_freeze_origin_value(child_value) for child_value in value)
    if isinstance(value, tuple):
        return tuple(_freeze_origin_value(child_value) for child_value in value)
    raise ValueError("valeur d'origine invalide")


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
