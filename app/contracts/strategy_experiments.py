"""Contrats publiés de snapshots de stratégie et résultats d'expérience."""

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
from app.contracts.research_outcomes import VersionedClaimRef


STRATEGY_EXPERIMENT_SCHEMA_VERSIONS = frozenset({"1.0"})
COMPILABLE_STRATEGY_STATUS = "COMPILABLE"
ALLOWED_STRATEGY_SNAPSHOT_STATUSES = frozenset({COMPILABLE_STRATEGY_STATUS})
COMPLETED_EXPERIMENT_STATUS = "COMPLETED"
FAILED_EXPERIMENT_STATUS = "FAILED"
CANCELLED_EXPERIMENT_STATUS = "CANCELLED"
ALLOWED_EXPERIMENT_RESULT_STATUSES = frozenset(
    {
        COMPLETED_EXPERIMENT_STATUS,
        FAILED_EXPERIMENT_STATUS,
        CANCELLED_EXPERIMENT_STATUS,
    }
)

_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{64}$", re.IGNORECASE)
_STRATEGY_SNAPSHOT_FIELDS = frozenset(
    {
        "schema_version",
        "strategy_id",
        "strategy_version_id",
        "spec_hash",
        "status",
        "rules",
        "parameters",
        "constraints",
        "data_requirements",
        "validation_plan",
        "evidence_refs",
        "created_at",
    }
)
_EXPERIMENT_RESULT_FIELDS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "strategy_version_id",
        "data_snapshot_id",
        "result_hash",
        "code_version",
        "status",
        "frozen_inputs",
        "metrics",
        "diagnostics",
        "artifacts",
        "started_at",
        "completed_at",
    }
)
_MUTABLE_MARKER_KEYS = frozenset(
    {
        "current_strategy_ref",
        "latest_data_ref",
        "live_reference",
        "mutable",
        "mutable_input",
        "mutable_reference",
    }
)
_PROFITABILITY_MARKER_KEYS = frozenset(
    {
        "declared_profitability",
        "expected_profitability",
        "is_profitable",
        "pnl_expectation",
        "profitability_statement",
        "rentability_claim",
    }
)


@dataclass(frozen=True)
class StrategySnapshot:
    """Snapshot immuable publié par SD vers EX."""

    schema_version: str
    strategy_id: str
    strategy_version_id: str
    spec_hash: str
    status: str
    rules: tuple[Mapping[str, Any], ...]
    parameters: tuple[Mapping[str, Any], ...]
    constraints: tuple[Mapping[str, Any], ...]
    data_requirements: tuple[Mapping[str, Any], ...]
    validation_plan: Mapping[str, Any]
    evidence_refs: tuple[VersionedClaimRef, ...]
    created_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "StrategySnapshot":
        _ensure_mapping(payload, "StrategySnapshot")
        _ensure_no_forbidden_contract_markers(
            payload,
            mutable_error_message="reference mutable interdite",
        )
        ensure_allowed_fields(payload, _STRATEGY_SNAPSHOT_FIELDS, "StrategySnapshot")
        schema_version = ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=STRATEGY_EXPERIMENT_SCHEMA_VERSIONS,
        )

        return cls(
            schema_version=str(schema_version),
            strategy_id=_required_domain_identifier(payload, "strategy_id", "STRAT"),
            strategy_version_id=_required_domain_identifier(
                payload,
                "strategy_version_id",
                "SVER",
            ),
            spec_hash=_required_hash(payload, "spec_hash"),
            status=_required_strategy_status(payload),
            rules=_required_strategy_rules(payload),
            parameters=_required_strategy_parameters(payload),
            constraints=_required_constraints(payload),
            data_requirements=_required_data_requirements(payload),
            validation_plan=_required_mapping_copy(payload, "validation_plan"),
            evidence_refs=_required_versioned_claim_refs(payload, "evidence_refs"),
            created_at=_required_utc_instant(payload, "created_at"),
        )

    @classmethod
    def from_json(cls, serialized_payload: str) -> "StrategySnapshot":
        return cls.from_payload(_loads_contract_json(serialized_payload))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "strategy_id": self.strategy_id,
            "strategy_version_id": self.strategy_version_id,
            "spec_hash": self.spec_hash,
            "status": self.status,
            "rules": [thaw_contract_value(rule) for rule in self.rules],
            "parameters": [thaw_contract_value(parameter) for parameter in self.parameters],
            "constraints": [thaw_contract_value(constraint) for constraint in self.constraints],
            "data_requirements": [
                thaw_contract_value(data_requirement)
                for data_requirement in self.data_requirements
            ],
            "validation_plan": thaw_contract_value(self.validation_plan),
            "evidence_refs": [str(evidence_ref) for evidence_ref in self.evidence_refs],
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_payload())


@dataclass(frozen=True)
class ExperimentResult:
    """Résultat d'expérience publié par EX vers RA et CV."""

    schema_version: str
    experiment_id: str
    strategy_version_id: str
    data_snapshot_id: str
    result_hash: str
    code_version: str
    status: str
    frozen_inputs: Mapping[str, Any]
    metrics: Mapping[str, Any]
    diagnostics: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...]
    started_at: str
    completed_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExperimentResult":
        _ensure_mapping(payload, "ExperimentResult")
        _ensure_no_forbidden_contract_markers(
            payload,
            mutable_error_message="entree mutable interdite",
        )
        ensure_allowed_fields(payload, _EXPERIMENT_RESULT_FIELDS, "ExperimentResult")
        schema_version = ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=STRATEGY_EXPERIMENT_SCHEMA_VERSIONS,
        )
        data_snapshot_id = _required_domain_identifier(payload, "data_snapshot_id", "DATA")
        status = _required_experiment_result_status(payload)
        diagnostics = _required_mapping_copy(payload, "diagnostics")
        _ensure_failed_result_diagnostics(status=status, diagnostics=diagnostics)

        return cls(
            schema_version=str(schema_version),
            experiment_id=_required_domain_identifier(payload, "experiment_id", "EXP"),
            strategy_version_id=_required_domain_identifier(
                payload,
                "strategy_version_id",
                "SVER",
            ),
            data_snapshot_id=data_snapshot_id,
            result_hash=_required_hash(payload, "result_hash"),
            code_version=_required_text(payload, "code_version"),
            status=status,
            frozen_inputs=_required_frozen_inputs(payload, data_snapshot_id=data_snapshot_id),
            metrics=_required_mapping_copy(payload, "metrics"),
            diagnostics=diagnostics,
            artifacts=_required_artifacts(payload),
            started_at=_required_utc_instant(payload, "started_at"),
            completed_at=_required_utc_instant(payload, "completed_at"),
        )

    @classmethod
    def from_json(cls, serialized_payload: str) -> "ExperimentResult":
        return cls.from_payload(_loads_contract_json(serialized_payload))

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "strategy_version_id": self.strategy_version_id,
            "data_snapshot_id": self.data_snapshot_id,
            "result_hash": self.result_hash,
            "code_version": self.code_version,
            "status": self.status,
            "frozen_inputs": thaw_contract_value(self.frozen_inputs),
            "metrics": thaw_contract_value(self.metrics),
            "diagnostics": thaw_contract_value(self.diagnostics),
            "artifacts": [thaw_contract_value(artifact) for artifact in self.artifacts],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_payload())


def _required_strategy_status(payload: Mapping[str, Any]) -> str:
    status = _required_text(payload, "status")
    if status not in ALLOWED_STRATEGY_SNAPSHOT_STATUSES:
        raise ValueError(f"status non autorise: {status}")
    return status


def _required_experiment_result_status(payload: Mapping[str, Any]) -> str:
    status = _required_text(payload, "status")
    if status not in ALLOWED_EXPERIMENT_RESULT_STATUSES:
        raise ValueError(f"status non autorise: {status}")
    return status


def _ensure_failed_result_diagnostics(status: str, diagnostics: Mapping[str, Any]) -> None:
    if status != FAILED_EXPERIMENT_STATUS:
        return
    if "failure_reason" not in diagnostics:
        raise ValueError("diagnostic d'echec requis")
    _required_text(diagnostics, "failure_reason")


def _required_strategy_rules(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rules = _required_object_list(payload, "rules")
    parsed_rules = []
    for rule in rules:
        _required_text(rule, "rule_id")
        _required_text(rule, "kind")
        _required_text(rule, "expression")
        _required_text(rule, "origin")
        if "deterministic" not in rule:
            raise ValueError("deterministic absent")
        if not isinstance(rule["deterministic"], bool):
            raise ValueError("deterministic non booleen")
        if rule["deterministic"] is not True:
            raise ValueError("regle non deterministe")
        _required_versioned_claim_refs(rule, "evidence_refs")
        parsed_rules.append(freeze_contract_value(rule, "valeur de contrat"))
    return tuple(parsed_rules)


def _required_strategy_parameters(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    parameters = _required_object_list(payload, "parameters")
    parsed_parameters = []
    for parameter in parameters:
        _required_text(parameter, "name")
        _required_text(parameter, "origin")
        blocking = _required_bool(parameter, "blocking")
        resolution_status = _required_text(parameter, "resolution_status")
        _ensure_parameter_value_declared(parameter)
        if blocking and resolution_status != "RESOLVED":
            raise ValueError("parametre bloquant non resolu")
        parsed_parameters.append(freeze_contract_value(parameter, "valeur de contrat"))
    return tuple(parsed_parameters)


def _required_constraints(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    constraints = _required_object_list(payload, "constraints")
    parsed_constraints = []
    for constraint in constraints:
        _required_text(constraint, "name")
        _required_text(constraint, "origin")
        parsed_constraints.append(freeze_contract_value(constraint, "valeur de contrat"))
    return tuple(parsed_constraints)


def _required_data_requirements(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    data_requirements = _required_object_list(payload, "data_requirements")
    parsed_data_requirements = []
    for data_requirement in data_requirements:
        _required_text(data_requirement, "name")
        _required_text(data_requirement, "frequency")
        _required_bool(data_requirement, "point_in_time")
        parsed_data_requirements.append(freeze_contract_value(data_requirement, "valeur de contrat"))
    return tuple(parsed_data_requirements)


def _required_frozen_inputs(
    payload: Mapping[str, Any],
    data_snapshot_id: str,
) -> dict[str, Any]:
    frozen_inputs = _required_mapping_copy(payload, "frozen_inputs")
    _required_hash(frozen_inputs, "strategy_snapshot_hash")
    frozen_data_snapshot_id = _required_domain_identifier(
        frozen_inputs,
        "data_snapshot_id",
        "DATA",
    )
    if frozen_data_snapshot_id != data_snapshot_id:
        raise ValueError("data_snapshot_id incoherent avec frozen_inputs")
    _required_hash(frozen_inputs, "data_snapshot_hash")
    _required_hash(frozen_inputs, "cost_model_hash")
    _required_hash(frozen_inputs, "execution_environment_hash")
    _required_utc_instant(frozen_inputs, "frozen_at")
    return frozen_inputs


def _required_artifacts(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    artifacts = _required_object_list(payload, "artifacts")
    parsed_artifacts = []
    for artifact in artifacts:
        _required_text(artifact, "artifact_id")
        _required_text(artifact, "artifact_type")
        _required_hash(artifact, "artifact_hash")
        parsed_artifacts.append(freeze_contract_value(artifact, "valeur de contrat"))
    return tuple(parsed_artifacts)


def _required_object_list(
    payload: Mapping[str, Any],
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    values = payload[field_name]
    if isinstance(values, str) or not hasattr(values, "__iter__"):
        raise ValueError(f"{field_name} non liste")

    parsed_values = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError(f"{field_name} invalide")
        if len(value) == 0:
            raise ValueError(f"{field_name} invalide")
        parsed_values.append(dict(value))

    if len(parsed_values) == 0:
        raise ValueError(f"{field_name} vide")

    return tuple(parsed_values)


def _required_mapping_copy(payload: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
    if len(value) == 0:
        raise ValueError(f"{field_name} vide")
    return _copy_mapping_value(value, field_name)


def _required_versioned_claim_refs(
    payload: Mapping[str, Any],
    field_name: str,
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

    if len(parsed_claim_refs) == 0:
        raise ValueError(f"{field_name} vide")

    return tuple(parsed_claim_refs)


def _ensure_parameter_value_declared(parameter: Mapping[str, Any]) -> None:
    value_fields = ("value", "domain", "calibration_rule", "unresolved_reason")
    if not any(field_name in parameter for field_name in value_fields):
        raise ValueError("parametre sans valeur ni domaine")


def _ensure_no_forbidden_contract_markers(
    value: Any,
    mutable_error_message: str,
) -> None:
    if isinstance(value, Mapping):
        for key, child_value in value.items():
            normalized_key = key.lower() if isinstance(key, str) else key
            if normalized_key in _PROFITABILITY_MARKER_KEYS:
                raise ValueError("declaration de rentabilite interdite")
            if normalized_key in _MUTABLE_MARKER_KEYS:
                raise ValueError(mutable_error_message)
            _ensure_no_forbidden_contract_markers(
                child_value,
                mutable_error_message=mutable_error_message,
            )
    elif isinstance(value, list):
        for child_value in value:
            _ensure_no_forbidden_contract_markers(
                child_value,
                mutable_error_message=mutable_error_message,
            )
    elif isinstance(value, tuple):
        for child_value in value:
            _ensure_no_forbidden_contract_markers(
                child_value,
                mutable_error_message=mutable_error_message,
            )
    elif isinstance(value, str):
        lowered_value = value.lower()
        if lowered_value.startswith("strategy_candidate:") or lowered_value.endswith("/current"):
            raise ValueError(mutable_error_message)
        if lowered_value.endswith(":latest"):
            raise ValueError(mutable_error_message)


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
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_bool(payload: Mapping[str, Any], field_name: str) -> bool:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booleen")
    return value


def _required_hash(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_utc_instant(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    return ensure_utc_instant_value(value, field_name)


def _loads_contract_json(serialized_payload: str) -> Mapping[str, Any]:
    _ensure_text_value(serialized_payload, "contrat serialise")
    payload = json.loads(serialized_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("Contrat publie non objet.")
    return payload


def _dumps_contract_json(payload: Mapping[str, Any]) -> str:
    return dumps_contract_json(payload)


def _ensure_mapping(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")


def _copy_mapping_value(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    return freeze_contract_value(value, "valeur de contrat")
