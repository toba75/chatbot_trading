"""Agrégat SD pour l'ouverture d'une stratégie candidate."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

from app.contracts.evidence_claims import EvidenceRef, VerifiedClaimRef
from app.contracts.identity import DomainIdentifier
from app.contracts.research_outcomes import VerifiedResearchOutcome, VersionedClaimRef


class StrategyCandidateStatus:
    DRAFT = "DRAFT"
    SPECIFIED = "SPECIFIED"
    VALIDATING = "VALIDATING"
    COMPILABLE = "COMPILABLE"
    INCOMPLETE = "INCOMPLETE"
    INCONSISTENT = "INCONSISTENT"


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


class CompatibilityFindingCode(str, Enum):
    POINT_IN_TIME_VIOLATION = "POINT_IN_TIME_VIOLATION"
    DATA_FREQUENCY_INCOMPATIBLE = "DATA_FREQUENCY_INCOMPATIBLE"
    CALENDAR_UNAVAILABLE = "CALENDAR_UNAVAILABLE"
    IMPLICIT_COST_MODEL = "IMPLICIT_COST_MODEL"
    TURNOVER_CONSTRAINT_VIOLATION = "TURNOVER_CONSTRAINT_VIOLATION"
    LIQUIDITY_CONSTRAINT_VIOLATION = "LIQUIDITY_CONSTRAINT_VIOLATION"
    LEVERAGE_CONSTRAINT_VIOLATION = "LEVERAGE_CONSTRAINT_VIOLATION"
    HORIZON_MISMATCH = "HORIZON_MISMATCH"
    EVIDENCE_SCOPE_MISMATCH = "EVIDENCE_SCOPE_MISMATCH"


class CompilationDiagnosticCode(str, Enum):
    STRATEGY_RULE_REQUIRED = "STRATEGY_RULE_REQUIRED"
    RULE_ORIGIN_REQUIRED = "RULE_ORIGIN_REQUIRED"
    SOURCE_EVIDENCE_REQUIRED = "SOURCE_EVIDENCE_REQUIRED"
    DESIGN_CHOICE_JUSTIFICATION_REQUIRED = "DESIGN_CHOICE_JUSTIFICATION_REQUIRED"
    STRATEGY_MANDATE_REQUIRED = "STRATEGY_MANDATE_REQUIRED"
    PARAMETER_CALIBRATION_REQUIRED = "PARAMETER_CALIBRATION_REQUIRED"
    VALIDATION_PLAN_REQUIRED = "VALIDATION_PLAN_REQUIRED"
    STRATEGY_CONFLICT_BLOCKING = "STRATEGY_CONFLICT_BLOCKING"
    STRATEGY_NOT_COMPILABLE = "STRATEGY_NOT_COMPILABLE"
    RULE_EXPRESSION_INVALID = "RULE_EXPRESSION_INVALID"
    RULE_NON_DETERMINISTIC = "RULE_NON_DETERMINISTIC"


@dataclass(frozen=True)
class CompilationDiagnostic:
    code: CompilationDiagnosticCode | CompatibilityFindingCode
    description: str
    blocking: bool
    rule_id: str | None
    parameter_id: str | None

    def __post_init__(self) -> None:
        if isinstance(self.code, str) and not isinstance(
            self.code,
            (CompilationDiagnosticCode, CompatibilityFindingCode),
        ):
            raise ValueError("code diagnostic libre interdit")
        if not isinstance(self.code, (CompilationDiagnosticCode, CompatibilityFindingCode)):
            raise ValueError("code diagnostic invalide")
        _ensure_text(self.description, "description diagnostic")
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking diagnostic non booléen")
        if self.rule_id is not None:
            _ensure_text(self.rule_id, "rule_id diagnostic")
        if self.parameter_id is not None:
            _ensure_text(self.parameter_id, "parameter_id diagnostic")
        if self.rule_id is not None and self.parameter_id is not None:
            raise ValueError("diagnostic de compilation à cible multiple")


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
                    code=CompilationDiagnosticCode.RULE_ORIGIN_REQUIRED,
                    rule_id=rule.rule_id,
                    description="Règle de stratégie sans origine autorisée.",
                ),
            )

        origin = rule.origin
        if origin.origin_type is RuleOriginType.SOURCE:
            if origin.evidence_ref_count == 0:
                return (
                    _rule_diagnostic(
                        code=CompilationDiagnosticCode.SOURCE_EVIDENCE_REQUIRED,
                        rule_id=rule.rule_id,
                        description="Origine SOURCE sans VerifiedClaimRef versionné ni EvidenceRef.",
                    ),
                )
            return ()

        if origin.origin_type is RuleOriginType.DEDUCTION:
            if len(origin.premises) == 0 or _is_blank_origin_text(origin.transformation):
                return (
                    _rule_diagnostic(
                        code=CompilationDiagnosticCode.RULE_ORIGIN_REQUIRED,
                        rule_id=rule.rule_id,
                        description="Déduction sans prémisses explicites ou transformation.",
                    ),
                )
            return ()

        if origin.origin_type is RuleOriginType.DESIGN_CHOICE:
            if _is_blank_origin_text(origin.justification) or _is_blank_origin_text(origin.mandate_impact):
                return (
                    _rule_diagnostic(
                        code=CompilationDiagnosticCode.DESIGN_CHOICE_JUSTIFICATION_REQUIRED,
                        rule_id=rule.rule_id,
                        description="Choix de conception sans justification opérationnelle.",
                    ),
                )
            return ()

        if origin.origin_type is RuleOriginType.PARAMETER_TO_CALIBRATE:
            if _is_empty_mapping(origin.calibration_domain) or _is_blank_origin_text(origin.calibration_protocol):
                return (
                    _rule_diagnostic(
                        code=CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED,
                        rule_id=rule.rule_id,
                        description="Paramètre à calibrer sans domaine ou protocole.",
                    ),
                )
            return ()

        if len(origin.mandate_refs) == 0:
            return (
                _rule_diagnostic(
                    code=CompilationDiagnosticCode.STRATEGY_MANDATE_REQUIRED,
                    rule_id=rule.rule_id,
                    description="Contrainte utilisateur sans référence au mandat.",
                ),
            )
        return ()


@dataclass(frozen=True)
class ParameterDomain:
    lower_bound: int | float
    upper_bound: int | float
    unit: str

    @classmethod
    def from_bounds(
        cls,
        *,
        lower_bound: int | float,
        upper_bound: int | float,
        unit: str,
    ) -> "ParameterDomain":
        return cls(
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            unit=unit,
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParameterDomain":
        if not isinstance(payload, Mapping) or len(payload) == 0:
            raise ValueError("domaine de calibration vide")
        allowed_fields = frozenset({"lower_bound", "upper_bound", "unit"})
        unexpected_fields = sorted(set(payload).difference(allowed_fields))
        if unexpected_fields:
            raise ValueError(f"champ domaine de calibration inattendu: {unexpected_fields[0]}")
        if "lower_bound" not in payload:
            raise ValueError("lower_bound absent")
        if "upper_bound" not in payload:
            raise ValueError("upper_bound absent")
        if "unit" not in payload:
            raise ValueError("unit absent")
        return cls.from_bounds(
            lower_bound=payload["lower_bound"],
            upper_bound=payload["upper_bound"],
            unit=payload["unit"],
        )

    def __post_init__(self) -> None:
        lower_bound = _ensure_parameter_number(self.lower_bound, "borne basse")
        upper_bound = _ensure_parameter_number(self.upper_bound, "borne haute")
        if lower_bound >= upper_bound:
            raise ValueError("borne basse superieure ou egale a la borne haute")
        object.__setattr__(self, "lower_bound", lower_bound)
        object.__setattr__(self, "upper_bound", upper_bound)
        object.__setattr__(self, "unit", _normalize_parameter_unit(self.unit))

    def to_payload(self) -> dict[str, Any]:
        return {
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "unit": self.unit,
        }

    def hash(self) -> str:
        serialized_payload = json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ValidationPlan:
    calibration_protocol: str
    expected_sensitivity: str

    def __post_init__(self) -> None:
        _ensure_text(self.calibration_protocol, "protocole de calibration")
        _ensure_text(self.expected_sensitivity, "sensibilite attendue")

    def to_payload(self) -> dict[str, Any]:
        return {
            "calibration_protocol": self.calibration_protocol,
            "expected_sensitivity": self.expected_sensitivity,
        }


@dataclass(frozen=True)
class StrategyParameter:
    parameter_id: str
    name: str
    origin_type: RuleOriginType
    value: Any | None
    domain: ParameterDomain | None
    validation_plan: ValidationPlan | None
    blocking: bool
    resolution_status: str
    unresolved_reason: str | None

    @classmethod
    def fixed_value(
        cls,
        *,
        parameter_id: str,
        name: str,
        value: Any,
        origin_type: RuleOriginType,
        blocking: bool,
    ) -> "StrategyParameter":
        return cls(
            parameter_id=parameter_id,
            name=name,
            origin_type=origin_type,
            value=value,
            domain=None,
            validation_plan=None,
            blocking=blocking,
            resolution_status="RESOLVED",
            unresolved_reason=None,
        )

    @classmethod
    def to_calibrate(
        cls,
        *,
        parameter_id: str,
        name: str,
        domain: ParameterDomain,
        validation_plan: ValidationPlan,
        blocking: bool,
    ) -> "StrategyParameter":
        return cls(
            parameter_id=parameter_id,
            name=name,
            origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
            value=None,
            domain=domain,
            validation_plan=validation_plan,
            blocking=blocking,
            resolution_status="RESOLVED",
            unresolved_reason=None,
        )

    @classmethod
    def unresolved(
        cls,
        *,
        parameter_id: str,
        name: str,
        origin_type: RuleOriginType,
        blocking: bool,
        unresolved_reason: str,
    ) -> "StrategyParameter":
        return cls(
            parameter_id=parameter_id,
            name=name,
            origin_type=origin_type,
            value=None,
            domain=None,
            validation_plan=None,
            blocking=blocking,
            resolution_status="UNRESOLVED",
            unresolved_reason=unresolved_reason,
        )

    def __post_init__(self) -> None:
        _ensure_text(self.parameter_id, "parameter_id")
        _ensure_text(self.name, "nom de paramètre")
        if isinstance(self.origin_type, str) and not isinstance(self.origin_type, RuleOriginType):
            raise ValueError("origin_type de parametre invalide")
        if not isinstance(self.origin_type, RuleOriginType):
            raise ValueError("origin_type de parametre invalide")
        if self.value is not None:
            object.__setattr__(self, "value", _freeze_parameter_value(self.value))
        if self.domain is not None and not isinstance(self.domain, ParameterDomain):
            raise ValueError("ParameterDomain attendu")
        if self.validation_plan is not None and not isinstance(self.validation_plan, ValidationPlan):
            raise ValueError("ValidationPlan attendu")
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking paramètre non booléen")
        if self.resolution_status not in {"RESOLVED", "UNRESOLVED"}:
            raise ValueError(f"statut de résolution paramètre inconnu: {self.resolution_status}")
        object.__setattr__(
            self,
            "unresolved_reason",
            _ensure_parameter_optional_text(self.unresolved_reason, "raison de non-resolution"),
        )

        has_value = self.value is not None
        has_domain = self.domain is not None
        has_unresolved_reason = self.unresolved_reason is not None
        if not has_value and not has_domain and not has_unresolved_reason:
            raise ValueError("parametre sans valeur, domaine ni raison de non-resolution")
        if has_value and (has_domain or self.validation_plan is not None or has_unresolved_reason):
            raise ValueError("parametre a valeur fixe avec calibration ou non-resolution")
        if has_unresolved_reason and (has_domain or self.validation_plan is not None):
            raise ValueError("parametre non resolu avec plan de calibration")
        if self.resolution_status == "RESOLVED" and has_unresolved_reason:
            raise ValueError("parametre resolu avec raison de non-resolution")
        if self.resolution_status == "UNRESOLVED" and has_value:
            raise ValueError("parametre non resolu avec valeur fixe")
        if self.origin_type is RuleOriginType.PARAMETER_TO_CALIBRATE and has_value:
            raise ValueError("parametre a calibrer avec valeur fixe interdite")

    def define_calibration_plan(
        self,
        *,
        domain: ParameterDomain,
        validation_plan: ValidationPlan,
    ) -> "StrategyParameter":
        if self.origin_type is not RuleOriginType.PARAMETER_TO_CALIBRATE:
            raise ValueError("plan de calibration interdit pour une origine non calibrable")
        if not isinstance(domain, ParameterDomain):
            raise ValueError("ParameterDomain attendu")
        if not isinstance(validation_plan, ValidationPlan):
            raise ValueError("ValidationPlan attendu")
        return replace(
            self,
            domain=domain,
            validation_plan=validation_plan,
            resolution_status="RESOLVED",
            unresolved_reason=None,
        )


class ParameterCalibrationPolicy:
    def validate_parameter(self, parameter: StrategyParameter) -> tuple[CompilationDiagnostic, ...]:
        if not isinstance(parameter, StrategyParameter):
            raise ValueError("StrategyParameter attendu")

        if parameter.origin_type is RuleOriginType.PARAMETER_TO_CALIBRATE:
            if parameter.domain is None:
                return (
                    _parameter_diagnostic(
                        code=CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED,
                        parameter_id=parameter.parameter_id,
                        description="Paramètre à calibrer sans domaine ou protocole.",
                    ),
                )
            if parameter.validation_plan is None:
                return (
                    _parameter_diagnostic(
                        code=CompilationDiagnosticCode.VALIDATION_PLAN_REQUIRED,
                        parameter_id=parameter.parameter_id,
                        description="Plan de validation absent pour un paramÃ¨tre Ã  calibrer.",
                    ),
                )
            return ()

        if parameter.blocking and parameter.resolution_status != "RESOLVED":
            return (
                _parameter_diagnostic(
                    code=CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED,
                    parameter_id=parameter.parameter_id,
                    description="Paramètre bloquant non résolu.",
                ),
            )
        return ()


@dataclass(frozen=True)
class StrategyConflict:
    conflict_id: str
    diagnostic: CompilationDiagnostic
    resolution_status: str
    resolution_summary: str | None

    @classmethod
    def blocking_documentary_conflict(
        cls,
        *,
        conflict_id: str,
        description: str,
    ) -> "StrategyConflict":
        return cls(
            conflict_id=conflict_id,
            diagnostic=CompilationDiagnostic(
                code=CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING,
                description=description,
                blocking=True,
                rule_id=None,
                parameter_id=None,
            ),
            resolution_status="OPEN",
            resolution_summary=None,
        )

    def __post_init__(self) -> None:
        _ensure_text(self.conflict_id, "conflict_id")
        if not isinstance(self.diagnostic, CompilationDiagnostic):
            raise ValueError("CompilationDiagnostic attendu")
        if self.diagnostic.code is not CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING:
            raise ValueError("diagnostic de conflit de stratégie invalide")
        if self.resolution_status not in {"OPEN", "RESOLVED"}:
            raise ValueError(f"statut de résolution conflit inconnu: {self.resolution_status}")
        object.__setattr__(
            self,
            "resolution_summary",
            _ensure_parameter_optional_text(self.resolution_summary, "résumé de résolution"),
        )
        if self.resolution_status == "OPEN" and self.resolution_summary is not None:
            raise ValueError("conflit ouvert avec résumé de résolution")
        if self.resolution_status == "RESOLVED" and self.resolution_summary is None:
            raise ValueError("conflit résolu sans résumé de résolution")

    @property
    def is_blocking_unresolved(self) -> bool:
        return self.resolution_status == "OPEN" and self.diagnostic.blocking

    def resolve(self, *, resolution_summary: str) -> "StrategyConflict":
        return replace(
            self,
            resolution_status="RESOLVED",
            resolution_summary=_ensure_text(resolution_summary, "résumé de résolution"),
        )

    def to_diagnostic(self) -> CompilationDiagnostic:
        return self.diagnostic


class StrategyCompletenessPolicy:
    def evaluate(self, candidate: "StrategyCandidate") -> tuple[CompilationDiagnostic, ...]:
        if not isinstance(candidate, StrategyCandidate):
            raise ValueError("StrategyCandidate attendue")

        diagnostics: list[CompilationDiagnostic] = []
        if len(candidate.rules) == 0:
            diagnostics.append(
                CompilationDiagnostic(
                    code=CompilationDiagnosticCode.STRATEGY_RULE_REQUIRED,
                    description="Stratégie candidate sans règle formalisée.",
                    blocking=True,
                    rule_id=None,
                    parameter_id=None,
                )
            )
        diagnostics.extend(
            diagnostic
            for rule in candidate.rules
            for diagnostic in RuleOriginPolicy().validate_rule(rule)
        )
        diagnostics.extend(
            diagnostic
            for parameter in candidate.parameters
            for diagnostic in ParameterCalibrationPolicy().validate_parameter(parameter)
        )
        diagnostics.extend(
            conflict.to_diagnostic()
            for conflict in candidate.conflicts
            if conflict.is_blocking_unresolved
        )
        diagnostics.extend(finding.to_diagnostic() for finding in candidate.compatibility_findings)
        return tuple(diagnostics)


@dataclass(frozen=True)
class CompatibilityFinding:
    code: CompatibilityFindingCode
    description: str
    blocking: bool
    rule_id: str | None
    parameter_id: str | None

    def __post_init__(self) -> None:
        if isinstance(self.code, str) and not isinstance(self.code, CompatibilityFindingCode):
            raise ValueError("code finding compatibilitÃ© libre interdit")
        if not isinstance(self.code, CompatibilityFindingCode):
            raise ValueError("code finding compatibilitÃ© invalide")
        _ensure_text(self.description, "description finding compatibilitÃ©")
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking finding compatibilitÃ© non boolÃ©en")
        if self.rule_id is not None:
            _ensure_text(self.rule_id, "rule_id finding compatibilitÃ©")
        if self.parameter_id is not None:
            _ensure_text(self.parameter_id, "parameter_id finding compatibilitÃ©")
        if self.rule_id is not None and self.parameter_id is not None:
            raise ValueError("finding de compatibilitÃ© Ã  cible multiple")

    def to_diagnostic(self) -> CompilationDiagnostic:
        return CompilationDiagnostic(
            code=self.code,
            description=self.description,
            blocking=self.blocking,
            rule_id=self.rule_id,
            parameter_id=self.parameter_id,
        )


@dataclass(frozen=True)
class DataAvailability:
    requirement_id: str
    available_at: str

    def __post_init__(self) -> None:
        _ensure_text(self.requirement_id, "requirement_id")
        _parse_utc_instant(self.available_at, "available_at")


@dataclass(frozen=True)
class DataRequirement:
    requirement_id: str
    data_name: str
    frequency: str
    evidence_scope_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _ensure_text(self.requirement_id, "requirement_id")
        _ensure_text(self.data_name, "data_name")
        object.__setattr__(self, "frequency", _normalize_temporal_bucket(self.frequency, "frequency"))
        if isinstance(self.evidence_scope_refs, str) or not isinstance(self.evidence_scope_refs, tuple):
            raise ValueError("evidence_scope_refs non tuple")
        if len(self.evidence_scope_refs) == 0:
            raise ValueError("evidence_scope_refs vide")
        object.__setattr__(
            self,
            "evidence_scope_refs",
            tuple(_ensure_text(scope_ref, "evidence_scope_refs") for scope_ref in self.evidence_scope_refs),
        )


@dataclass(frozen=True)
class ExecutionProfile:
    signal_horizon: str
    holding_horizon: str
    decision_frequency: str
    calendar_id: str
    cost_model_id: str | None
    expected_turnover: int | float
    expected_liquidity_usage: int | float
    expected_leverage: int | float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "signal_horizon",
            _normalize_temporal_bucket(self.signal_horizon, "signal_horizon"),
        )
        object.__setattr__(
            self,
            "holding_horizon",
            _normalize_temporal_bucket(self.holding_horizon, "holding_horizon"),
        )
        object.__setattr__(
            self,
            "decision_frequency",
            _normalize_temporal_bucket(self.decision_frequency, "decision_frequency"),
        )
        _ensure_text(self.calendar_id, "calendar_id")
        if self.cost_model_id is not None:
            _ensure_text(self.cost_model_id, "cost_model_id")
        object.__setattr__(
            self,
            "expected_turnover",
            _ensure_non_negative_measure(self.expected_turnover, "coÃ»t attendu invalide"),
        )
        object.__setattr__(
            self,
            "expected_liquidity_usage",
            _ensure_non_negative_measure(self.expected_liquidity_usage, "coÃ»t attendu invalide"),
        )
        object.__setattr__(
            self,
            "expected_leverage",
            _ensure_non_negative_measure(self.expected_leverage, "coÃ»t attendu invalide"),
        )


@dataclass(frozen=True)
class StrategyCompatibilityContext:
    rule_id: str
    decision_at: str
    data_requirements: tuple[DataRequirement, ...]
    execution: ExecutionProfile

    def __post_init__(self) -> None:
        _ensure_text(self.rule_id, "rule_id")
        _parse_utc_instant(self.decision_at, "decision_at")
        if isinstance(self.data_requirements, str) or not isinstance(self.data_requirements, tuple):
            raise ValueError("data_requirements non tuple")
        if len(self.data_requirements) == 0:
            raise ValueError("data_requirements vide")
        for requirement in self.data_requirements:
            if not isinstance(requirement, DataRequirement):
                raise ValueError("DataRequirement attendu")
        if not isinstance(self.execution, ExecutionProfile):
            raise ValueError("ExecutionProfile attendu")


class PointInTimeDataPolicy:
    def __init__(self, *, data_availability_catalog: Any) -> None:
        if not hasattr(data_availability_catalog, "availability_for"):
            raise ValueError("DataAvailabilityCatalog attendu")
        self._data_availability_catalog = data_availability_catalog

    def evaluate(
        self,
        *,
        rule_id: str,
        decision_at: str,
        data_requirements: tuple[DataRequirement, ...],
        signal_horizon: str,
    ) -> tuple[CompatibilityFinding, ...]:
        _ensure_text(rule_id, "rule_id")
        decision_time = _parse_utc_instant(decision_at, "decision_at")
        normalized_signal_horizon = _normalize_temporal_bucket(signal_horizon, "signal_horizon")

        findings: list[CompatibilityFinding] = []
        for requirement in data_requirements:
            if not isinstance(requirement, DataRequirement):
                raise ValueError("DataRequirement attendu")
            availability = self._data_availability_catalog.availability_for(requirement)
            if not isinstance(availability, DataAvailability):
                raise ValueError("DataAvailability attendu")
            if availability.requirement_id != requirement.requirement_id:
                raise ValueError("disponibilitÃ© de donnÃ©e incohÃ©rente")
            if _parse_utc_instant(availability.available_at, "available_at") > decision_time:
                findings.append(
                    CompatibilityFinding(
                        code=CompatibilityFindingCode.POINT_IN_TIME_VIOLATION,
                        description="DonnÃ©e indisponible au moment de dÃ©cision.",
                        blocking=True,
                        rule_id=rule_id,
                        parameter_id=None,
                    )
                )
            if _temporal_rank(requirement.frequency) > _temporal_rank(normalized_signal_horizon):
                findings.append(
                    CompatibilityFinding(
                        code=CompatibilityFindingCode.DATA_FREQUENCY_INCOMPATIBLE,
                        description="FrÃ©quence de donnÃ©e incompatible avec l'horizon du signal.",
                        blocking=True,
                        rule_id=rule_id,
                        parameter_id=None,
                    )
                )
        return tuple(findings)


class ExecutionFeasibilityPolicy:
    def __init__(self, *, market_calendar_catalog: Any) -> None:
        if not hasattr(market_calendar_catalog, "has_calendar"):
            raise ValueError("MarketCalendarCatalog attendu")
        self._market_calendar_catalog = market_calendar_catalog

    def evaluate(
        self,
        *,
        rule_id: str,
        mandate: "StrategyMandate",
        execution: ExecutionProfile,
    ) -> tuple[CompatibilityFinding, ...]:
        _ensure_text(rule_id, "rule_id")
        if not isinstance(mandate, StrategyMandate):
            raise ValueError("StrategyMandate attendu")
        if not isinstance(execution, ExecutionProfile):
            raise ValueError("ExecutionProfile attendu")

        findings: list[CompatibilityFinding] = []
        if not self._market_calendar_catalog.has_calendar(execution.calendar_id):
            findings.append(
                CompatibilityFinding(
                    code=CompatibilityFindingCode.CALENDAR_UNAVAILABLE,
                    description="Calendrier de marchÃ© absent.",
                    blocking=True,
                    rule_id=rule_id,
                    parameter_id=None,
                )
            )
        if execution.cost_model_id is None:
            findings.append(
                CompatibilityFinding(
                    code=CompatibilityFindingCode.IMPLICIT_COST_MODEL,
                    description="ModÃ¨le de coÃ»ts explicite absent.",
                    blocking=True,
                    rule_id=rule_id,
                    parameter_id=None,
                )
            )
        max_turnover = _optional_mandate_number(mandate, "max_turnover")
        if max_turnover is not None and execution.expected_turnover > max_turnover:
            findings.append(
                CompatibilityFinding(
                    code=CompatibilityFindingCode.TURNOVER_CONSTRAINT_VIOLATION,
                    description="Turnover attendu supÃ©rieur au mandat.",
                    blocking=True,
                    rule_id=rule_id,
                    parameter_id=None,
                )
            )
        max_liquidity_usage = _optional_mandate_number(mandate, "max_liquidity_usage")
        if max_liquidity_usage is not None and execution.expected_liquidity_usage > max_liquidity_usage:
            findings.append(
                CompatibilityFinding(
                    code=CompatibilityFindingCode.LIQUIDITY_CONSTRAINT_VIOLATION,
                    description="Usage de liquiditÃ© attendu supÃ©rieur au mandat.",
                    blocking=True,
                    rule_id=rule_id,
                    parameter_id=None,
                )
            )
        max_leverage = _optional_mandate_number(mandate, "max_leverage")
        if max_leverage is not None and execution.expected_leverage > max_leverage:
            findings.append(
                CompatibilityFinding(
                    code=CompatibilityFindingCode.LEVERAGE_CONSTRAINT_VIOLATION,
                    description="Levier attendu supÃ©rieur au mandat.",
                    blocking=True,
                    rule_id=rule_id,
                    parameter_id=None,
                )
            )
        return tuple(findings)


class StrategyCompatibilityPolicy:
    def __init__(
        self,
        *,
        point_in_time_policy: PointInTimeDataPolicy,
        execution_feasibility_policy: ExecutionFeasibilityPolicy,
    ) -> None:
        if not isinstance(point_in_time_policy, PointInTimeDataPolicy):
            raise ValueError("PointInTimeDataPolicy attendue")
        if not isinstance(execution_feasibility_policy, ExecutionFeasibilityPolicy):
            raise ValueError("ExecutionFeasibilityPolicy attendue")
        self._point_in_time_policy = point_in_time_policy
        self._execution_feasibility_policy = execution_feasibility_policy

    def evaluate(
        self,
        *,
        mandate: "StrategyMandate",
        context: StrategyCompatibilityContext,
    ) -> tuple[CompatibilityFinding, ...]:
        if not isinstance(mandate, StrategyMandate):
            raise ValueError("StrategyMandate attendu")
        if not isinstance(context, StrategyCompatibilityContext):
            raise ValueError("StrategyCompatibilityContext attendu")

        findings = list(
            self._point_in_time_policy.evaluate(
                rule_id=context.rule_id,
                decision_at=context.decision_at,
                data_requirements=context.data_requirements,
                signal_horizon=context.execution.signal_horizon,
            )
        )
        findings.extend(
            self._execution_feasibility_policy.evaluate(
                rule_id=context.rule_id,
                mandate=mandate,
                execution=context.execution,
            )
        )
        mandate_horizon = _optional_mandate_text(mandate, "horizon")
        if mandate_horizon is not None and _normalize_temporal_bucket(
            mandate_horizon,
            "horizon mandat",
        ) != context.execution.holding_horizon:
            findings.append(
                CompatibilityFinding(
                    code=CompatibilityFindingCode.HORIZON_MISMATCH,
                    description="Horizon de dÃ©tention incompatible avec le mandat.",
                    blocking=True,
                    rule_id=context.rule_id,
                    parameter_id=None,
                )
            )
        allowed_scope_refs = _optional_mandate_text_tuple(mandate, "allowed_evidence_scope_refs")
        if allowed_scope_refs is not None:
            allowed_scope_set = frozenset(allowed_scope_refs)
            for requirement in context.data_requirements:
                if not set(requirement.evidence_scope_refs).issubset(allowed_scope_set):
                    findings.append(
                        CompatibilityFinding(
                            code=CompatibilityFindingCode.EVIDENCE_SCOPE_MISMATCH,
                            description="PortÃ©e des preuves incompatible avec le mandat.",
                            blocking=True,
                            rule_id=context.rule_id,
                            parameter_id=None,
                        )
                    )
                    break
        return tuple(findings)


class StrategyCompatibilityAnalyzer:
    def __init__(self, *, policy: StrategyCompatibilityPolicy) -> None:
        if not isinstance(policy, StrategyCompatibilityPolicy):
            raise ValueError("StrategyCompatibilityPolicy attendue")
        self._policy = policy

    def analyze(
        self,
        candidate: "StrategyCandidate",
        *,
        context: StrategyCompatibilityContext,
        expected_version: int,
    ) -> "StrategyCandidate":
        if not isinstance(candidate, StrategyCandidate):
            raise ValueError("StrategyCandidate attendue")
        _ensure_current_candidate_version(candidate, expected_version)
        findings = self._policy.evaluate(mandate=candidate.mandate, context=context)
        diagnostics = candidate.compilation_diagnostics + tuple(
            finding.to_diagnostic() for finding in findings
        )
        next_status = (
            StrategyCandidateStatus.INCONSISTENT
            if any(finding.blocking for finding in findings)
            else StrategyCandidateStatus.SPECIFIED
        )
        return replace(
            candidate,
            version=candidate.version + 1,
            status=next_status,
            compatibility_findings=findings,
            compilation_diagnostics=diagnostics,
        )


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
class StrategyParameterAdded:
    strategy_id: str
    strategy_version: int
    parameter_id: str
    origin_type: str
    blocking_status: bool

    @property
    def event_type(self) -> str:
        return "StrategyParameterAdded"


@dataclass(frozen=True)
class CalibrationPlanDefined:
    strategy_id: str
    parameter_id: str
    domain_hash: str
    protocol_version: str

    @property
    def event_type(self) -> str:
        return "CalibrationPlanDefined"


@dataclass(frozen=True)
class StrategyConflictRecorded:
    strategy_id: str
    strategy_version: int
    conflict_id: str
    diagnostic_code: CompilationDiagnosticCode
    blocking_status: bool

    @property
    def event_type(self) -> str:
        return "StrategyConflictRecorded"


@dataclass(frozen=True)
class StrategyConflictResolved:
    strategy_id: str
    previous_version: int
    new_version: int
    conflict_id: str
    resolution_summary_hash: str

    @property
    def event_type(self) -> str:
        return "StrategyConflictResolved"


@dataclass(frozen=True)
class StrategyCandidateValidated:
    strategy_id: str
    strategy_version: int
    status: str
    diagnostic_count: int

    @property
    def event_type(self) -> str:
        return "StrategyCandidateValidated"


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
    compatibility_findings: tuple[CompatibilityFinding, ...]
    conflicts: tuple[StrategyConflict, ...]
    rules: tuple[StrategyRule, ...]
    parameters: tuple[StrategyParameter, ...]
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
            compatibility_findings=(),
            conflicts=(),
            rules=(),
            parameters=(),
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
            compatibility_findings=(),
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
            compatibility_findings=(),
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

    def add_parameter(
        self,
        *,
        parameter: StrategyParameter,
        expected_version: int,
    ) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        if not isinstance(parameter, StrategyParameter):
            raise ValueError("StrategyParameter attendu")
        if any(existing_parameter.parameter_id == parameter.parameter_id for existing_parameter in self.parameters):
            raise ValueError(f"paramètre de stratégie déjà présent: {parameter.parameter_id}")

        new_version = self.version + 1
        return replace(
            self,
            version=new_version,
            status=StrategyCandidateStatus.SPECIFIED,
            compilation_diagnostics=(),
            compatibility_findings=(),
            parameters=self.parameters + (parameter,),
            domain_events=self.domain_events
            + (
                StrategyParameterAdded(
                    strategy_id=self.strategy_id,
                    strategy_version=new_version,
                    parameter_id=parameter.parameter_id,
                    origin_type=parameter.origin_type.value,
                    blocking_status=parameter.blocking,
                ),
            ),
        )

    def define_calibration_plan(
        self,
        *,
        parameter_id: str,
        domain: ParameterDomain,
        validation_plan: ValidationPlan,
        expected_version: int,
    ) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        _ensure_text(parameter_id, "parameter_id")
        if not isinstance(domain, ParameterDomain):
            raise ValueError("ParameterDomain attendu")
        if not isinstance(validation_plan, ValidationPlan):
            raise ValueError("ValidationPlan attendu")

        updated_parameters = []
        matched = False
        for parameter in self.parameters:
            if parameter.parameter_id == parameter_id:
                updated_parameters.append(
                    parameter.define_calibration_plan(
                        domain=domain,
                        validation_plan=validation_plan,
                    )
                )
                matched = True
            else:
                updated_parameters.append(parameter)
        if not matched:
            raise ValueError(f"paramètre de stratégie absent: {parameter_id}")

        return replace(
            self,
            version=self.version + 1,
            status=StrategyCandidateStatus.SPECIFIED,
            compilation_diagnostics=(),
            compatibility_findings=(),
            parameters=tuple(updated_parameters),
            domain_events=self.domain_events
            + (
                CalibrationPlanDefined(
                    strategy_id=self.strategy_id,
                    parameter_id=parameter_id,
                    domain_hash=domain.hash(),
                    protocol_version=validation_plan.calibration_protocol,
                ),
            ),
        )

    def record_conflict(
        self,
        *,
        conflict: StrategyConflict,
        expected_version: int,
    ) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        if not isinstance(conflict, StrategyConflict):
            raise ValueError("StrategyConflict attendu")
        if any(existing.conflict_id == conflict.conflict_id for existing in self.conflicts):
            raise ValueError(f"conflit de stratégie déjà enregistré: {conflict.conflict_id}")

        new_version = self.version + 1
        return replace(
            self,
            version=new_version,
            status=StrategyCandidateStatus.SPECIFIED,
            compilation_diagnostics=(),
            conflicts=self.conflicts + (conflict,),
            domain_events=self.domain_events
            + (
                StrategyConflictRecorded(
                    strategy_id=self.strategy_id,
                    strategy_version=new_version,
                    conflict_id=conflict.conflict_id,
                    diagnostic_code=conflict.diagnostic.code,
                    blocking_status=conflict.diagnostic.blocking,
                ),
            ),
        )

    def resolve_conflict(
        self,
        *,
        conflict_id: str,
        resolution_summary: str,
        expected_version: int,
    ) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        _ensure_text(conflict_id, "conflict_id")
        _ensure_text(resolution_summary, "résumé de résolution")

        updated_conflicts = []
        matched = False
        for conflict in self.conflicts:
            if conflict.conflict_id == conflict_id:
                updated_conflicts.append(conflict.resolve(resolution_summary=resolution_summary))
                matched = True
            else:
                updated_conflicts.append(conflict)
        if not matched:
            raise ValueError(f"conflit de stratégie absent: {conflict_id}")

        new_version = self.version + 1
        return replace(
            self,
            version=new_version,
            status=StrategyCandidateStatus.SPECIFIED,
            compilation_diagnostics=(),
            conflicts=tuple(updated_conflicts),
            domain_events=self.domain_events
            + (
                StrategyConflictResolved(
                    strategy_id=self.strategy_id,
                    previous_version=self.version,
                    new_version=new_version,
                    conflict_id=conflict_id,
                    resolution_summary_hash=_hash_text(resolution_summary),
                ),
            ),
        )

    def validate_candidate(self, *, expected_version: int) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        diagnostics = StrategyCompletenessPolicy().evaluate(self)
        next_status = _strategy_status_from_diagnostics(diagnostics)
        new_version = self.version + 1
        return replace(
            self,
            version=new_version,
            status=next_status,
            compilation_diagnostics=diagnostics,
            domain_events=self.domain_events
            + (
                StrategyCandidateValidated(
                    strategy_id=self.strategy_id,
                    strategy_version=new_version,
                    status=next_status,
                    diagnostic_count=len(diagnostics),
                ),
            ),
        )

    def validate_for_compilation(self, *, expected_version: int) -> "StrategyCandidate":
        _ensure_current_candidate_version(self, expected_version)
        rule_parameter_diagnostics = tuple(
            diagnostic
            for rule in self.rules
            for diagnostic in RuleOriginPolicy().validate_rule(rule)
        ) + tuple(
            diagnostic
            for parameter in self.parameters
            for diagnostic in ParameterCalibrationPolicy().validate_parameter(parameter)
        )
        conflict_diagnostics = tuple(
            conflict.to_diagnostic()
            for conflict in self.conflicts
            if conflict.is_blocking_unresolved
        )
        compatibility_diagnostics = tuple(finding.to_diagnostic() for finding in self.compatibility_findings)
        diagnostics = rule_parameter_diagnostics + conflict_diagnostics + compatibility_diagnostics
        has_rule_or_parameter_blocking = any(diagnostic.blocking for diagnostic in rule_parameter_diagnostics)
        has_conflict_blocking = any(diagnostic.blocking for diagnostic in conflict_diagnostics)
        has_compatibility_blocking = any(finding.blocking for finding in self.compatibility_findings)
        next_status = (
            StrategyCandidateStatus.INCOMPLETE
            if has_rule_or_parameter_blocking
            else StrategyCandidateStatus.INCONSISTENT
            if has_conflict_blocking or has_compatibility_blocking
            else StrategyCandidateStatus.SPECIFIED
        )
        return replace(
            self,
            version=self.version + 1,
            status=next_status,
            compilation_diagnostics=diagnostics,
        )


class StrategyCompilationStatus:
    COMPILED = "COMPILED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class RuleExpressionValidation:
    rule_id: str
    valid: bool
    is_deterministic: bool
    normalized_expression: str | None
    random_mechanism: str | None
    seed: str | None
    reason: str | None

    @classmethod
    def deterministic(
        cls,
        *,
        rule_id: str,
        normalized_expression: str,
    ) -> "RuleExpressionValidation":
        return cls(
            rule_id=rule_id,
            valid=True,
            is_deterministic=True,
            normalized_expression=normalized_expression,
            random_mechanism=None,
            seed=None,
            reason=None,
        )

    @classmethod
    def invalid(
        cls,
        *,
        rule_id: str,
        reason: str,
    ) -> "RuleExpressionValidation":
        return cls(
            rule_id=rule_id,
            valid=False,
            is_deterministic=False,
            normalized_expression=None,
            random_mechanism=None,
            seed=None,
            reason=reason,
        )

    @classmethod
    def non_deterministic(
        cls,
        *,
        rule_id: str,
        random_mechanism: str | None,
        seed: str | None,
        reason: str,
    ) -> "RuleExpressionValidation":
        return cls(
            rule_id=rule_id,
            valid=True,
            is_deterministic=False,
            normalized_expression=None,
            random_mechanism=random_mechanism,
            seed=seed,
            reason=reason,
        )

    def __post_init__(self) -> None:
        _ensure_text(self.rule_id, "rule_id validation expression")
        if not isinstance(self.valid, bool):
            raise ValueError("valid expression non boolÃ©en")
        if not isinstance(self.is_deterministic, bool):
            raise ValueError("deterministic expression non boolÃ©en")
        object.__setattr__(
            self,
            "normalized_expression",
            _ensure_parameter_optional_text(self.normalized_expression, "expression normalisÃ©e"),
        )
        object.__setattr__(
            self,
            "random_mechanism",
            _ensure_parameter_optional_text(self.random_mechanism, "mÃ©canisme alÃ©atoire"),
        )
        object.__setattr__(
            self,
            "seed",
            _ensure_parameter_optional_text(self.seed, "graine alÃ©atoire"),
        )
        object.__setattr__(
            self,
            "reason",
            _ensure_parameter_optional_text(self.reason, "raison validation expression"),
        )
        if self.valid and self.is_deterministic and self.normalized_expression is None:
            raise ValueError("expression dÃ©terministe sans forme normalisÃ©e")
        if not self.valid and self.reason is None:
            raise ValueError("expression invalide sans raison")
        if self.is_deterministic and (self.random_mechanism is not None or self.seed is not None):
            raise ValueError("expression dÃ©terministe avec alÃ©a dÃ©clarÃ©")
        if self.seed is not None and self.random_mechanism is None:
            raise ValueError("graine sans mÃ©canisme alÃ©atoire")

    @property
    def has_explicit_randomness(self) -> bool:
        return self.random_mechanism is not None and self.seed is not None

    @property
    def is_compilable(self) -> bool:
        return self.valid and (self.is_deterministic or self.has_explicit_randomness)


class RuleExpressionValidator(Protocol):
    def validate(self, rule: StrategyRule) -> RuleExpressionValidation:
        raise NotImplementedError


@dataclass(frozen=True)
class CompiledRule:
    rule_id: str
    rule_kind: str
    normalized_expression: str
    origin_type: str
    origin_hash: str
    deterministic: bool
    random_mechanism: str | None
    seed: str | None

    @classmethod
    def from_rule(
        cls,
        *,
        rule: StrategyRule,
        validation: RuleExpressionValidation,
    ) -> "CompiledRule":
        if not isinstance(rule, StrategyRule):
            raise ValueError("StrategyRule attendue")
        if not isinstance(validation, RuleExpressionValidation):
            raise ValueError("RuleExpressionValidation attendue")
        if validation.rule_id != rule.rule_id:
            raise ValueError("validation expression hors rÃ¨gle")
        if not validation.is_compilable:
            raise ValueError("validation expression non compilable")
        if rule.origin is None:
            raise ValueError("rÃ¨gle sans origine non compilable")

        normalized_expression = (
            validation.normalized_expression
            if validation.normalized_expression is not None
            else rule.expression.text
        )
        return cls(
            rule_id=rule.rule_id,
            rule_kind=rule.rule_kind,
            normalized_expression=normalized_expression,
            origin_type=rule.origin.origin_type.value,
            origin_hash=_hash_payload(_rule_origin_payload(rule.origin)),
            deterministic=validation.is_deterministic,
            random_mechanism=validation.random_mechanism,
            seed=validation.seed,
        )

    def __post_init__(self) -> None:
        _ensure_text(self.rule_id, "rule_id compilÃ©")
        _ensure_text(self.rule_kind, "rule_kind compilÃ©")
        _ensure_text(self.normalized_expression, "expression compilÃ©e")
        _ensure_text(self.origin_type, "origin_type compilÃ©")
        _ensure_text(self.origin_hash, "origin_hash compilÃ©")
        if not isinstance(self.deterministic, bool):
            raise ValueError("deterministic compilÃ© non boolÃ©en")
        object.__setattr__(
            self,
            "random_mechanism",
            _ensure_parameter_optional_text(self.random_mechanism, "mÃ©canisme alÃ©atoire compilÃ©"),
        )
        object.__setattr__(
            self,
            "seed",
            _ensure_parameter_optional_text(self.seed, "graine compilÃ©e"),
        )
        if self.deterministic and (self.random_mechanism is not None or self.seed is not None):
            raise ValueError("rÃ¨gle compilÃ©e dÃ©terministe avec alÃ©a")
        if not self.deterministic and (self.random_mechanism is None or self.seed is None):
            raise ValueError("rÃ¨gle compilÃ©e alÃ©atoire sans mÃ©canisme ou graine")

    def to_payload(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_kind": self.rule_kind,
            "normalized_expression": self.normalized_expression,
            "origin_type": self.origin_type,
            "origin_hash": self.origin_hash,
            "deterministic": self.deterministic,
            "random_mechanism": self.random_mechanism,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class CompiledParameter:
    parameter_id: str
    name: str
    origin_type: str
    value_hash: str | None
    domain_hash: str | None
    validation_plan_hash: str | None
    blocking: bool

    @classmethod
    def from_parameter(cls, parameter: StrategyParameter) -> "CompiledParameter":
        if not isinstance(parameter, StrategyParameter):
            raise ValueError("StrategyParameter attendu")
        value_hash = (
            _hash_payload(_thaw_strategy_value(parameter.value))
            if parameter.value is not None
            else None
        )
        domain_hash = parameter.domain.hash() if parameter.domain is not None else None
        validation_plan_hash = (
            _hash_payload(parameter.validation_plan.to_payload())
            if parameter.validation_plan is not None
            else None
        )
        return cls(
            parameter_id=parameter.parameter_id,
            name=parameter.name,
            origin_type=parameter.origin_type.value,
            value_hash=value_hash,
            domain_hash=domain_hash,
            validation_plan_hash=validation_plan_hash,
            blocking=parameter.blocking,
        )

    def __post_init__(self) -> None:
        _ensure_text(self.parameter_id, "parameter_id compilÃ©")
        _ensure_text(self.name, "nom paramÃ¨tre compilÃ©")
        _ensure_text(self.origin_type, "origin_type paramÃ¨tre compilÃ©")
        object.__setattr__(
            self,
            "value_hash",
            _ensure_parameter_optional_text(self.value_hash, "hash valeur paramÃ¨tre"),
        )
        object.__setattr__(
            self,
            "domain_hash",
            _ensure_parameter_optional_text(self.domain_hash, "hash domaine paramÃ¨tre"),
        )
        object.__setattr__(
            self,
            "validation_plan_hash",
            _ensure_parameter_optional_text(
                self.validation_plan_hash,
                "hash plan validation paramÃ¨tre",
            ),
        )
        if not isinstance(self.blocking, bool):
            raise ValueError("blocking paramÃ¨tre compilÃ© non boolÃ©en")
        if self.value_hash is None and self.domain_hash is None:
            raise ValueError("paramÃ¨tre compilÃ© sans valeur ni domaine")
        if self.origin_type == RuleOriginType.PARAMETER_TO_CALIBRATE.value and self.validation_plan_hash is None:
            raise ValueError("paramÃ¨tre compilÃ© sans plan de validation")

    def to_payload(self) -> dict[str, Any]:
        return {
            "parameter_id": self.parameter_id,
            "name": self.name,
            "origin_type": self.origin_type,
            "value_hash": self.value_hash,
            "domain_hash": self.domain_hash,
            "validation_plan_hash": self.validation_plan_hash,
            "blocking": self.blocking,
        }


@dataclass(frozen=True)
class CompiledStrategyRepresentation:
    strategy_id: str
    strategy_version: int
    compiler_version: str
    mandate_hash: str
    verified_research_hash: str
    rules: tuple[CompiledRule, ...]
    parameters: tuple[CompiledParameter, ...]
    representation_hash: str

    @classmethod
    def from_candidate(
        cls,
        *,
        candidate: "StrategyCandidate",
        rule_validations: Sequence[RuleExpressionValidation],
        compiler_version: str,
    ) -> "CompiledStrategyRepresentation":
        if not isinstance(candidate, StrategyCandidate):
            raise ValueError("StrategyCandidate attendue")
        compiler_version = _ensure_text(compiler_version, "version compilateur")
        validation_by_rule_id = {
            validation.rule_id: validation
            for validation in rule_validations
            if isinstance(validation, RuleExpressionValidation)
        }
        if len(validation_by_rule_id) != len(tuple(rule_validations)):
            raise ValueError("RuleExpressionValidation attendue")

        compiled_rules = tuple(
            CompiledRule.from_rule(
                rule=rule,
                validation=_required_rule_validation(validation_by_rule_id, rule.rule_id),
            )
            for rule in sorted(candidate.rules, key=lambda current_rule: current_rule.rule_id)
        )
        compiled_parameters = tuple(
            CompiledParameter.from_parameter(parameter)
            for parameter in sorted(
                candidate.parameters,
                key=lambda current_parameter: current_parameter.parameter_id,
            )
        )
        verified_research_hash = _hash_payload(
            _verified_research_ref_payload(candidate.verified_research_ref)
        )
        representation_payload = {
            "schema_version": "strategy_compiled_representation.v1",
            "strategy_id": candidate.strategy_id,
            "strategy_version": candidate.version,
            "compiler_version": compiler_version,
            "mandate_hash": candidate.mandate.hash(),
            "verified_research_hash": verified_research_hash,
            "rules": [rule.to_payload() for rule in compiled_rules],
            "parameters": [parameter.to_payload() for parameter in compiled_parameters],
        }
        return cls(
            strategy_id=candidate.strategy_id,
            strategy_version=candidate.version,
            compiler_version=compiler_version,
            mandate_hash=candidate.mandate.hash(),
            verified_research_hash=verified_research_hash,
            rules=compiled_rules,
            parameters=compiled_parameters,
            representation_hash=_hash_payload(representation_payload),
        )

    def __post_init__(self) -> None:
        _ensure_strategy_id(self.strategy_id)
        if not isinstance(self.strategy_version, int) or isinstance(self.strategy_version, bool):
            raise ValueError("strategy_version compilÃ©e non entiÃ¨re")
        if self.strategy_version < 0:
            raise ValueError("strategy_version compilÃ©e nÃ©gative")
        _ensure_text(self.compiler_version, "version compilateur")
        _ensure_text(self.mandate_hash, "hash mandat compilÃ©")
        _ensure_text(self.verified_research_hash, "hash recherche compilÃ©e")
        _ensure_text(self.representation_hash, "hash reprÃ©sentation")
        if not isinstance(self.rules, tuple) or any(not isinstance(rule, CompiledRule) for rule in self.rules):
            raise ValueError("rÃ¨gles compilÃ©es invalides")
        if not isinstance(self.parameters, tuple) or any(
            not isinstance(parameter, CompiledParameter)
            for parameter in self.parameters
        ):
            raise ValueError("paramÃ¨tres compilÃ©s invalides")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "strategy_compiled_representation.v1",
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "compiler_version": self.compiler_version,
            "mandate_hash": self.mandate_hash,
            "verified_research_hash": self.verified_research_hash,
            "rules": [rule.to_payload() for rule in self.rules],
            "parameters": [parameter.to_payload() for parameter in self.parameters],
            "representation_hash": self.representation_hash,
        }


@dataclass(frozen=True)
class StrategyCompilationRejected:
    strategy_id: str
    strategy_version: int
    public_error_code: CompilationDiagnosticCode | CompatibilityFindingCode
    diagnostic_count: int

    @property
    def event_type(self) -> str:
        return "StrategyCompilationRejected"


@dataclass(frozen=True)
class StrategyCompiled:
    strategy_id: str
    strategy_version: int
    compiler_version: str
    representation_hash: str

    @property
    def event_type(self) -> str:
        return "StrategyCompiled"


@dataclass(frozen=True)
class StrategyCompilationResult:
    compilation_status: str
    strategy_id: str
    strategy_version: int
    representation: CompiledStrategyRepresentation | None
    diagnostics: tuple[CompilationDiagnostic, ...]
    event: StrategyCompiled | StrategyCompilationRejected

    def __post_init__(self) -> None:
        if self.compilation_status not in {
            StrategyCompilationStatus.COMPILED,
            StrategyCompilationStatus.REJECTED,
        }:
            raise ValueError("statut de compilation inconnu")
        _ensure_strategy_id(self.strategy_id)
        if not isinstance(self.strategy_version, int) or isinstance(self.strategy_version, bool):
            raise ValueError("strategy_version resultat non entiÃ¨re")
        if self.representation is not None and not isinstance(self.representation, CompiledStrategyRepresentation):
            raise ValueError("CompiledStrategyRepresentation attendue")
        if not isinstance(self.diagnostics, tuple) or any(
            not isinstance(diagnostic, CompilationDiagnostic)
            for diagnostic in self.diagnostics
        ):
            raise ValueError("diagnostics de compilation invalides")
        if self.compilation_status == StrategyCompilationStatus.COMPILED:
            if self.representation is None or self.diagnostics != ():
                raise ValueError("resultat compile incoherent")
            if not isinstance(self.event, StrategyCompiled):
                raise ValueError("StrategyCompiled attendu")
        if self.compilation_status == StrategyCompilationStatus.REJECTED:
            if self.representation is not None or len(self.diagnostics) == 0:
                raise ValueError("resultat rejet incoherent")
            if not isinstance(self.event, StrategyCompilationRejected):
                raise ValueError("StrategyCompilationRejected attendu")


@dataclass(frozen=True)
class StrategyCompilationAssessment:
    diagnostics: tuple[CompilationDiagnostic, ...]
    rule_validations: tuple[RuleExpressionValidation, ...]


class StrategyCompilationPolicy:
    def __init__(self, *, expression_validator: RuleExpressionValidator) -> None:
        if expression_validator is None or not hasattr(expression_validator, "validate"):
            raise ValueError("RuleExpressionValidator requis")
        self._expression_validator = expression_validator

    def evaluate(self, candidate: "StrategyCandidate") -> StrategyCompilationAssessment:
        if not isinstance(candidate, StrategyCandidate):
            raise ValueError("StrategyCandidate attendue")

        diagnostics: list[CompilationDiagnostic] = []
        if candidate.status != StrategyCandidateStatus.COMPILABLE:
            diagnostics.append(
                CompilationDiagnostic(
                    code=CompilationDiagnosticCode.STRATEGY_NOT_COMPILABLE,
                    description="Statut de stratÃ©gie non compilable.",
                    blocking=True,
                    rule_id=None,
                    parameter_id=None,
                )
            )
        diagnostics.extend(StrategyCompletenessPolicy().evaluate(candidate))

        rule_validations: list[RuleExpressionValidation] = []
        for rule in candidate.rules:
            validation = self._expression_validator.validate(rule)
            if not isinstance(validation, RuleExpressionValidation):
                raise ValueError("RuleExpressionValidation attendue")
            if validation.rule_id != rule.rule_id:
                raise ValueError("validation expression hors rÃ¨gle")
            rule_validations.append(validation)
            if not validation.valid:
                diagnostics.append(
                    _rule_diagnostic(
                        code=CompilationDiagnosticCode.RULE_EXPRESSION_INVALID,
                        rule_id=rule.rule_id,
                        description=validation.reason
                        if validation.reason is not None
                        else "Expression de rÃ¨gle invalide.",
                    )
                )
            elif not validation.is_compilable:
                diagnostics.append(
                    _rule_diagnostic(
                        code=CompilationDiagnosticCode.RULE_NON_DETERMINISTIC,
                        rule_id=rule.rule_id,
                        description=validation.reason
                        if validation.reason is not None
                        else "RÃ¨gle non dÃ©terministe sans mÃ©canisme et graine explicites.",
                    )
                )

        return StrategyCompilationAssessment(
            diagnostics=tuple(diagnostics),
            rule_validations=tuple(rule_validations),
        )


class StrategyCompilerBackend(Protocol):
    def compile_representation(
        self,
        *,
        candidate: "StrategyCandidate",
        rule_validations: Sequence[RuleExpressionValidation],
        compiler_version: str,
    ) -> CompiledStrategyRepresentation:
        raise NotImplementedError


class StrategyCompiler:
    def __init__(
        self,
        *,
        backend: StrategyCompilerBackend,
        expression_validator: RuleExpressionValidator,
        compiler_version: str,
    ) -> None:
        if backend is None or not hasattr(backend, "compile_representation"):
            raise ValueError("StrategyCompilerBackend requis")
        self._backend = backend
        self._compiler_version = _ensure_text(compiler_version, "version compilateur")
        self._policy = StrategyCompilationPolicy(expression_validator=expression_validator)

    def compile(
        self,
        candidate: "StrategyCandidate",
        *,
        expected_version: int,
    ) -> StrategyCompilationResult:
        _ensure_current_candidate_version(candidate, expected_version)
        assessment = self._policy.evaluate(candidate)
        if assessment.diagnostics:
            event = StrategyCompilationRejected(
                strategy_id=candidate.strategy_id,
                strategy_version=candidate.version,
                public_error_code=assessment.diagnostics[0].code,
                diagnostic_count=len(assessment.diagnostics),
            )
            return StrategyCompilationResult(
                compilation_status=StrategyCompilationStatus.REJECTED,
                strategy_id=candidate.strategy_id,
                strategy_version=candidate.version,
                representation=None,
                diagnostics=assessment.diagnostics,
                event=event,
            )

        representation = self._backend.compile_representation(
            candidate=candidate,
            rule_validations=assessment.rule_validations,
            compiler_version=self._compiler_version,
        )
        if not isinstance(representation, CompiledStrategyRepresentation):
            raise ValueError("CompiledStrategyRepresentation attendue")
        event = StrategyCompiled(
            strategy_id=candidate.strategy_id,
            strategy_version=candidate.version,
            compiler_version=self._compiler_version,
            representation_hash=representation.representation_hash,
        )
        return StrategyCompilationResult(
            compilation_status=StrategyCompilationStatus.COMPILED,
            strategy_id=candidate.strategy_id,
            strategy_version=candidate.version,
            representation=representation,
            diagnostics=(),
            event=event,
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
_INCOMPLETE_DIAGNOSTIC_CODES = frozenset(
    {
        CompilationDiagnosticCode.STRATEGY_RULE_REQUIRED,
        CompilationDiagnosticCode.RULE_ORIGIN_REQUIRED,
        CompilationDiagnosticCode.SOURCE_EVIDENCE_REQUIRED,
        CompilationDiagnosticCode.DESIGN_CHOICE_JUSTIFICATION_REQUIRED,
        CompilationDiagnosticCode.STRATEGY_MANDATE_REQUIRED,
        CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED,
        CompilationDiagnosticCode.VALIDATION_PLAN_REQUIRED,
    }
)


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


def _strategy_status_from_diagnostics(
    diagnostics: tuple[CompilationDiagnostic, ...],
) -> str:
    if any(
        diagnostic.blocking and diagnostic.code in _INCOMPLETE_DIAGNOSTIC_CODES
        for diagnostic in diagnostics
    ):
        return StrategyCandidateStatus.INCOMPLETE
    if any(diagnostic.blocking for diagnostic in diagnostics):
        return StrategyCandidateStatus.INCONSISTENT
    return StrategyCandidateStatus.COMPILABLE


def _hash_text(value: str) -> str:
    return hashlib.sha256(_ensure_text(value, "valeur à hacher").encode("utf-8")).hexdigest()


def _hash_payload(value: Any) -> str:
    serialized_payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


def _verified_research_ref_payload(value: VerifiedResearchRef) -> dict[str, Any]:
    if not isinstance(value, VerifiedResearchRef):
        raise ValueError("VerifiedResearchRef attendue")
    return {
        "research_case_id": value.research_case_id,
        "answer_id": value.answer_id,
        "claim_refs": list(value.claim_refs),
        "support_status": value.support_status,
    }


def _rule_origin_payload(value: RuleOrigin) -> dict[str, Any]:
    if not isinstance(value, RuleOrigin):
        raise ValueError("RuleOrigin attendue")
    return {
        "origin_type": value.origin_type.value,
        "verified_claim_refs": list(value.verified_claim_refs),
        "evidence_refs": list(value.evidence_refs),
        "premises": list(value.premises),
        "transformation": value.transformation,
        "justification": value.justification,
        "mandate_impact": value.mandate_impact,
        "calibration_domain": _thaw_strategy_value(value.calibration_domain)
        if value.calibration_domain is not None
        else None,
        "calibration_protocol": value.calibration_protocol,
        "mandate_refs": list(value.mandate_refs),
    }


def _required_rule_validation(
    validations: Mapping[str, RuleExpressionValidation],
    rule_id: str,
) -> RuleExpressionValidation:
    if rule_id not in validations:
        raise ValueError(f"validation expression absente: {rule_id}")
    return validations[rule_id]


def _rule_diagnostic(
    *,
    code: CompilationDiagnosticCode,
    rule_id: str,
    description: str,
) -> CompilationDiagnostic:
    return CompilationDiagnostic(
        code=code,
        description=description,
        blocking=True,
        rule_id=rule_id,
        parameter_id=None,
    )


def _parameter_diagnostic(
    *,
    code: CompilationDiagnosticCode,
    parameter_id: str,
    description: str,
) -> CompilationDiagnostic:
    return CompilationDiagnostic(
        code=code,
        description=description,
        blocking=True,
        rule_id=None,
        parameter_id=parameter_id,
    )


_TEMPORAL_BUCKET_RANK = {
    "INTRADAY": 0,
    "DAILY": 1,
    "SWING": 2,
    "WEEKLY": 2,
    "MONTHLY": 3,
    "QUARTERLY": 4,
    "YEARLY": 5,
}


def _parse_utc_instant(value: Any, field_name: str) -> datetime:
    text_value = _ensure_text(value, field_name)
    try:
        return datetime.strptime(text_value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{field_name} instant UTC invalide") from exc


def _normalize_temporal_bucket(value: Any, field_name: str) -> str:
    normalized_value = _ensure_text(value, field_name).upper()
    if normalized_value not in _TEMPORAL_BUCKET_RANK:
        raise ValueError(f"{field_name} inconnu: {value}")
    return normalized_value


def _temporal_rank(value: str) -> int:
    normalized_value = _normalize_temporal_bucket(value, "horizon temporel")
    return _TEMPORAL_BUCKET_RANK[normalized_value]


def _ensure_non_negative_measure(value: Any, error_message: str) -> int | float:
    number_value = _ensure_parameter_number(value, error_message)
    if number_value < 0:
        raise ValueError(error_message)
    return number_value


def _optional_mandate_number(mandate: "StrategyMandate", field_name: str) -> int | float | None:
    if field_name not in mandate.payload:
        return None
    return _ensure_non_negative_measure(mandate.payload[field_name], f"{field_name} mandat invalide")


def _optional_mandate_text(mandate: "StrategyMandate", field_name: str) -> str | None:
    if field_name not in mandate.payload:
        return None
    return _ensure_text(mandate.payload[field_name], field_name)


def _optional_mandate_text_tuple(mandate: "StrategyMandate", field_name: str) -> tuple[str, ...] | None:
    if field_name not in mandate.payload:
        return None
    values = mandate.payload[field_name]
    if isinstance(values, str) or not hasattr(values, "__iter__"):
        raise ValueError(f"{field_name} non liste")
    parsed_values = tuple(_ensure_text(value, field_name) for value in values)
    if len(parsed_values) == 0:
        raise ValueError(f"{field_name} vide")
    return parsed_values


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


def _ensure_parameter_number(value: Any, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} invalide")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{field_name} invalide")
    return value


def _normalize_parameter_unit(value: Any) -> str:
    unit = _ensure_text(value, "unité de paramètre")
    return unit.lower()


def _ensure_parameter_optional_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _ensure_text(value, field_name)


def _freeze_parameter_value(value: Any) -> Any:
    if value is None:
        raise ValueError("valeur de paramètre invalide")
    if isinstance(value, str):
        return _ensure_text(value, "valeur de paramètre")
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("valeur de paramètre invalide")
        return value
    if isinstance(value, Mapping):
        if len(value) == 0:
            raise ValueError("valeur de paramètre vide")
        return MappingProxyType(
            {
                _ensure_text(key, "clé de paramètre"): _freeze_parameter_value(child_value)
                for key, child_value in value.items()
            }
        )
    if isinstance(value, list):
        if len(value) == 0:
            raise ValueError("valeur de paramètre vide")
        return tuple(_freeze_parameter_value(child_value) for child_value in value)
    if isinstance(value, tuple):
        if len(value) == 0:
            raise ValueError("valeur de paramètre vide")
        return tuple(_freeze_parameter_value(child_value) for child_value in value)
    raise ValueError("valeur de paramètre invalide")


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
