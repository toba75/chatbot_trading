"""Signaux d'audit de clôture pour les versions canoniques M-004."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.contracts.identity import DomainIdentifier

_ALLOWED_STATUSES = frozenset({"PUBLISHED", "REJECTED", "QUARANTINED"})
_ALLOWED_PHASES = frozenset(
    {
        "canonical_conversion",
        "canonical_quality",
        "canonical_publication",
        "canonical_supersession",
    }
)
_ALLOWED_ERROR_CODES = frozenset(
    {
        "DECIMAL_SEPARATOR_ALTERED",
        "FIGURE_PROVENANCE_MISSING",
        "INCOMPLETE_TABLE",
        "NEGATIVE_SIGN_ALTERED",
        "NUMERIC_INCONSISTENCY",
        "PAGE_AUTHORITY_AMBIGUOUS",
        "PAGE_AUTHORITY_MISSING",
        "PAGE_OMITTED",
        "PAGE_UNEXPECTED",
        "PERCENTAGE_ALTERED",
        "SOURCE_LOCATOR_INCONSISTENT",
        "SOURCE_NOT_CANONICAL",
        "SOURCE_QUARANTINED",
    }
)
_AUDIT_LOG_FIELD_NAMES = frozenset(
    {
        "trace_id",
        "document_id",
        "canonical_version_id",
        "phase",
        "status",
        "page_count",
        "pages_rejected_by_qa",
        "ambiguous_text_authorities",
        "artifact_hash",
        "error_code",
    }
)
_FORBIDDEN_DOCUMENT_PAYLOAD_TOKENS = frozenset(
    {
        "document_text",
        "full_text",
        "api_key",
        "secret",
        "token",
        "page_text",
        "texte documentaire complet",
        "performance_table_full_text",
        "artifact:source_processing.original_sources",
        "c:\\",
        "\\",
        "../",
        "/users/",
        "/home/",
    }
)


class CanonicalAuditSignalError(ValueError):
    """Erreur explicite du contrat d'audit canonique."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CanonicalAuditEvent:
    """Événement d'audit M-004 sans contenu documentaire complet."""

    trace_id: str
    document_id: str
    canonical_version_id: str
    phase: str
    status: str
    page_count: int
    pages_rejected_by_qa: int
    ambiguous_text_authorities: int
    artifact_hash: str
    error_code: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _ensure_trace_id(self.trace_id))
        object.__setattr__(self, "document_id", _ensure_document_id(self.document_id))
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_canonical_version_id(self.canonical_version_id),
        )
        object.__setattr__(self, "phase", _ensure_phase(self.phase))
        object.__setattr__(self, "status", _ensure_status(self.status))
        object.__setattr__(
            self,
            "page_count",
            _ensure_positive_integer(self.page_count, "page_count", "M004_AUDIT_PAGE_COUNT_INVALID"),
        )
        object.__setattr__(
            self,
            "pages_rejected_by_qa",
            _ensure_non_negative_integer(
                self.pages_rejected_by_qa,
                "pages_rejected_by_qa",
                "M004_AUDIT_QA_REJECTIONS_INVALID",
            ),
        )
        object.__setattr__(
            self,
            "ambiguous_text_authorities",
            _ensure_non_negative_integer(
                self.ambiguous_text_authorities,
                "ambiguous_text_authorities",
                "M004_AUDIT_AUTHORITY_AMBIGUITIES_INVALID",
            ),
        )
        object.__setattr__(self, "artifact_hash", _ensure_artifact_hash(self.artifact_hash))
        object.__setattr__(
            self,
            "error_code",
            _ensure_optional_error_code(self.error_code),
        )
        _ensure_status_counters_contract(
            status=self.status,
            pages_rejected_by_qa=self.pages_rejected_by_qa,
            ambiguous_text_authorities=self.ambiguous_text_authorities,
            error_code=self.error_code,
        )

    def to_log_mapping(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "document_id": self.document_id,
            "canonical_version_id": self.canonical_version_id,
            "phase": self.phase,
            "status": self.status,
            "page_count": self.page_count,
            "pages_rejected_by_qa": self.pages_rejected_by_qa,
            "ambiguous_text_authorities": self.ambiguous_text_authorities,
            "artifact_hash": self.artifact_hash,
            "error_code": self.error_code,
        }


@dataclass(frozen=True)
class CanonicalAuditLogEvent:
    """Log structuré M-004 sans payload documentaire."""

    fields: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", _freeze_observable_mapping(self.fields))

    def to_mapping(self) -> dict[str, Any]:
        return dict(self.fields)


@dataclass(frozen=True)
class CanonicalMetricEvent:
    """Métrique de clôture M-004."""

    name: str
    value: float
    unit: str
    tags: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _ensure_text(self.name, "name", "M004_AUDIT_METRIC_NAME_REQUIRED"))
        object.__setattr__(
            self,
            "value",
            _ensure_non_negative_number(self.value, "value", "M004_AUDIT_METRIC_VALUE_INVALID"),
        )
        object.__setattr__(self, "unit", _ensure_text(self.unit, "unit", "M004_AUDIT_METRIC_UNIT_REQUIRED"))
        object.__setattr__(self, "tags", _freeze_string_mapping(self.tags))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "tags": dict(self.tags),
        }


@dataclass(frozen=True)
class CanonicalAuditSignals:
    """Lot de logs et métriques de clôture M-004."""

    logs: tuple[CanonicalAuditLogEvent, ...]
    metrics: tuple[CanonicalMetricEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "logs", _ensure_log_events(self.logs))
        object.__setattr__(self, "metrics", _ensure_metric_events(self.metrics))


def build_canonical_audit_signals(
    events: Sequence[CanonicalAuditEvent],
) -> CanonicalAuditSignals:
    parsed_events = _ensure_audit_events(events)
    logs = tuple(CanonicalAuditLogEvent(fields=event.to_log_mapping()) for event in parsed_events)

    published_versions = 0
    rejected_pages = 0
    ambiguous_authorities = 0

    for event in parsed_events:
        if event.status == "PUBLISHED":
            published_versions += 1
        rejected_pages += event.pages_rejected_by_qa
        ambiguous_authorities += event.ambiguous_text_authorities

    metrics = (
        CanonicalMetricEvent(
            name="versions_canoniques_publiees",
            value=float(published_versions),
            unit="versions",
            tags={"scope": "m004"},
        ),
        CanonicalMetricEvent(
            name="pages_refusees_qa",
            value=float(rejected_pages),
            unit="pages",
            tags={"scope": "m004"},
        ),
        CanonicalMetricEvent(
            name="autorites_textuelles_ambiguës",
            value=float(ambiguous_authorities),
            unit="pages",
            tags={"scope": "m004"},
        ),
    )

    return CanonicalAuditSignals(logs=logs, metrics=metrics)


def _ensure_audit_events(value: Sequence[CanonicalAuditEvent]) -> tuple[CanonicalAuditEvent, ...]:
    if value is None:
        raise CanonicalAuditSignalError("M004_AUDIT_EVENTS_REQUIRED", "Les événements d'audit M-004 sont requis.")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise CanonicalAuditSignalError(
            "M004_AUDIT_EVENTS_INVALID",
            "Les événements d'audit M-004 doivent former une séquence.",
        )
    events = tuple(value)
    if len(events) == 0:
        raise CanonicalAuditSignalError("M004_AUDIT_EVENTS_REQUIRED", "Les événements d'audit M-004 sont vides.")
    for event in events:
        if not isinstance(event, CanonicalAuditEvent):
            raise CanonicalAuditSignalError(
                "M004_AUDIT_EVENT_INVALID",
                "Chaque événement d'audit doit utiliser CanonicalAuditEvent.",
            )
    return events


def _ensure_log_events(value: Sequence[CanonicalAuditLogEvent]) -> tuple[CanonicalAuditLogEvent, ...]:
    if value is None:
        raise CanonicalAuditSignalError("M004_AUDIT_LOGS_REQUIRED", "Les logs d'audit M-004 sont requis.")
    logs = tuple(value)
    if len(logs) == 0:
        raise CanonicalAuditSignalError("M004_AUDIT_LOGS_REQUIRED", "Les logs d'audit M-004 sont vides.")
    for log in logs:
        if not isinstance(log, CanonicalAuditLogEvent):
            raise CanonicalAuditSignalError("M004_AUDIT_LOG_INVALID", "Log d'audit M-004 invalide.")
    return logs


def _ensure_metric_events(value: Sequence[CanonicalMetricEvent]) -> tuple[CanonicalMetricEvent, ...]:
    if value is None:
        raise CanonicalAuditSignalError("M004_AUDIT_METRICS_REQUIRED", "Les métriques d'audit M-004 sont requises.")
    metrics = tuple(value)
    metric_names = {metric.name for metric in metrics if isinstance(metric, CanonicalMetricEvent)}
    required_metric_names = {
        "versions_canoniques_publiees",
        "pages_refusees_qa",
        "autorites_textuelles_ambiguës",
    }
    missing_metric_names = required_metric_names - metric_names
    if len(missing_metric_names) > 0:
        raise CanonicalAuditSignalError(
            "M004_AUDIT_METRICS_REQUIRED",
            "Métriques d'audit M-004 absentes: " + ", ".join(sorted(missing_metric_names)),
        )
    for metric in metrics:
        if not isinstance(metric, CanonicalMetricEvent):
            raise CanonicalAuditSignalError("M004_AUDIT_METRIC_INVALID", "Métrique d'audit M-004 invalide.")
    return metrics


def _ensure_status_counters_contract(
    *,
    status: str,
    pages_rejected_by_qa: int,
    ambiguous_text_authorities: int,
    error_code: str | None,
) -> None:
    if status == "PUBLISHED":
        if pages_rejected_by_qa != 0:
            raise CanonicalAuditSignalError(
                "M004_AUDIT_PUBLISHED_QA_REJECTIONS_FORBIDDEN",
                "Une version publiée ne doit pas porter de pages refusées par QA.",
            )
        if ambiguous_text_authorities != 0:
            raise CanonicalAuditSignalError(
                "M004_AUDIT_PUBLISHED_AMBIGUITIES_FORBIDDEN",
                "Une version publiée ne doit pas porter d'autorités textuelles ambiguës.",
            )
        if error_code is not None:
            raise CanonicalAuditSignalError(
                "M004_AUDIT_PUBLISHED_ERROR_FORBIDDEN",
                "Une version publiée ne doit pas porter de code d'erreur.",
            )
        return

    if error_code is None:
        raise CanonicalAuditSignalError(
            "M004_AUDIT_ERROR_CODE_REQUIRED",
            "Une version canonique non publiée doit porter un code d'erreur.",
        )

    if pages_rejected_by_qa == 0 and ambiguous_text_authorities == 0:
        raise CanonicalAuditSignalError(
            "M004_AUDIT_REJECTION_COUNTER_REQUIRED",
            "Une version canonique refusée doit porter au moins un compteur de refus.",
        )


def _ensure_status(value: Any) -> str:
    status = _ensure_text(value, "status", "M004_AUDIT_STATUS_REQUIRED")
    if status not in _ALLOWED_STATUSES:
        raise CanonicalAuditSignalError("M004_AUDIT_STATUS_INVALID", "Statut d'audit M-004 invalide.")
    return status


def _ensure_trace_id(value: Any) -> str:
    trace_id = _ensure_text(value, "trace_id", "M004_AUDIT_TRACE_ID_REQUIRED")
    if re.fullmatch(r"TRACE-M004-[A-Z0-9][A-Z0-9-]*", trace_id) is None:
        raise CanonicalAuditSignalError("M004_AUDIT_TRACE_ID_INVALID", "trace_id M-004 invalide.")
    return trace_id


def _ensure_document_id(value: Any) -> str:
    document_id = _ensure_text(value, "document_id", "M004_AUDIT_DOCUMENT_ID_REQUIRED")
    try:
        return str(DomainIdentifier.parse_with_prefix(document_id, "DOC"))
    except ValueError as exc:
        raise CanonicalAuditSignalError("M004_AUDIT_DOCUMENT_ID_INVALID", f"document_id invalide: {exc}") from exc


def _ensure_canonical_version_id(value: Any) -> str:
    canonical_version_id = _ensure_text(
        value,
        "canonical_version_id",
        "M004_AUDIT_VERSION_ID_REQUIRED",
    )
    try:
        return str(DomainIdentifier.parse_with_prefix(canonical_version_id, "CVER"))
    except ValueError as exc:
        raise CanonicalAuditSignalError(
            "M004_AUDIT_VERSION_ID_INVALID",
            f"canonical_version_id invalide: {exc}",
        ) from exc


def _ensure_phase(value: Any) -> str:
    phase = _ensure_text(value, "phase", "M004_AUDIT_PHASE_REQUIRED")
    if phase not in _ALLOWED_PHASES:
        raise CanonicalAuditSignalError("M004_AUDIT_PHASE_INVALID", "Phase d'audit M-004 invalide.")
    return phase


def _ensure_optional_error_code(value: Any) -> str | None:
    if value is None:
        return None
    error_code = _ensure_text(value, "error_code", "M004_AUDIT_ERROR_CODE_INVALID")
    if error_code not in _ALLOWED_ERROR_CODES:
        raise CanonicalAuditSignalError("M004_AUDIT_ERROR_CODE_INVALID", "Code d'erreur M-004 invalide.")
    return error_code


def _ensure_text(value: Any, field_name: str, code: str) -> str:
    if not isinstance(value, str):
        raise CanonicalAuditSignalError(code, f"Champ textuel invalide: {field_name}")
    if value.strip() == "":
        raise CanonicalAuditSignalError(code, f"Champ textuel vide: {field_name}")
    if value != value.strip():
        raise CanonicalAuditSignalError(code, f"Champ textuel non normalisé: {field_name}")
    _ensure_no_document_payload(value, field_name)
    return value


def _ensure_optional_text(value: Any, field_name: str, code: str) -> str | None:
    if value is None:
        return None
    return _ensure_text(value, field_name, code)


def _ensure_positive_integer(value: Any, field_name: str, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CanonicalAuditSignalError(code, f"Entier positif invalide: {field_name}")
    return value


def _ensure_non_negative_integer(value: Any, field_name: str, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CanonicalAuditSignalError(code, f"Entier non négatif invalide: {field_name}")
    return value


def _ensure_non_negative_number(value: Any, field_name: str, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CanonicalAuditSignalError(code, f"Nombre invalide: {field_name}")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise CanonicalAuditSignalError(code, f"Nombre négatif ou infini: {field_name}")
    return number


def _ensure_artifact_hash(value: Any) -> str:
    artifact_hash = _ensure_text(value, "artifact_hash", "M004_AUDIT_ARTIFACT_HASH_REQUIRED")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", artifact_hash) is None:
        raise CanonicalAuditSignalError(
            "M004_AUDIT_ARTIFACT_HASH_INVALID",
            "Le hash d'artefact canonique doit utiliser sha256:<64 hex>.",
        )
    return artifact_hash


def _freeze_observable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CanonicalAuditSignalError("M004_AUDIT_MAPPING_REQUIRED", "Mapping d'audit M-004 requis.")
    frozen: dict[str, Any] = {}
    for key, nested_value in value.items():
        parsed_key = _ensure_text(key, "field_name", "M004_AUDIT_FIELD_NAME_REQUIRED")
        if parsed_key not in _AUDIT_LOG_FIELD_NAMES:
            raise CanonicalAuditSignalError(
                "M004_AUDIT_FIELD_NAME_FORBIDDEN",
                f"Champ d'audit M-004 interdit: {parsed_key}",
            )
        if parsed_key == "trace_id":
            frozen[parsed_key] = _ensure_trace_id(nested_value)
        elif parsed_key == "document_id":
            frozen[parsed_key] = _ensure_document_id(nested_value)
        elif parsed_key == "canonical_version_id":
            frozen[parsed_key] = _ensure_canonical_version_id(nested_value)
        elif parsed_key == "phase":
            frozen[parsed_key] = _ensure_phase(nested_value)
        elif parsed_key == "status":
            frozen[parsed_key] = _ensure_status(nested_value)
        elif parsed_key == "artifact_hash":
            frozen[parsed_key] = _ensure_artifact_hash(nested_value)
        elif parsed_key == "error_code":
            frozen[parsed_key] = _ensure_optional_error_code(nested_value)
        elif isinstance(nested_value, str):
            frozen[parsed_key] = _ensure_text(nested_value, parsed_key, "M004_AUDIT_FIELD_VALUE_REQUIRED")
        elif isinstance(nested_value, bool):
            raise CanonicalAuditSignalError(
                "M004_AUDIT_FIELD_VALUE_INVALID",
                f"Booléen d'audit M-004 interdit: {parsed_key}",
            )
        elif isinstance(nested_value, int) or nested_value is None:
            frozen[parsed_key] = nested_value
        elif isinstance(nested_value, float):
            frozen[parsed_key] = _ensure_non_negative_number(
                nested_value,
                parsed_key,
                "M004_AUDIT_FIELD_VALUE_INVALID",
            )
        else:
            raise CanonicalAuditSignalError(
                "M004_AUDIT_FIELD_VALUE_INVALID",
                f"Valeur d'audit M-004 invalide: {parsed_key}",
            )
    missing_fields = _AUDIT_LOG_FIELD_NAMES - frozenset(frozen.keys())
    if len(missing_fields) > 0:
        raise CanonicalAuditSignalError(
            "M004_AUDIT_FIELD_NAME_REQUIRED",
            "Champs d'audit M-004 absents: " + ", ".join(sorted(missing_fields)),
        )
    return MappingProxyType(frozen)


def _freeze_string_mapping(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise CanonicalAuditSignalError("M004_AUDIT_TAGS_REQUIRED", "Tags de métrique M-004 requis.")
    frozen: dict[str, str] = {}
    for key, nested_value in value.items():
        parsed_key = _ensure_text(key, "tag_name", "M004_AUDIT_TAG_NAME_REQUIRED")
        frozen[parsed_key] = _ensure_text(nested_value, parsed_key, "M004_AUDIT_TAG_VALUE_REQUIRED")
    return MappingProxyType(frozen)


def _ensure_no_document_payload(value: str, field_name: str) -> None:
    normalized_value = value.casefold()
    for token in _FORBIDDEN_DOCUMENT_PAYLOAD_TOKENS:
        if token in normalized_value:
            raise CanonicalAuditSignalError(
                "M004_AUDIT_DOCUMENT_PAYLOAD_FORBIDDEN",
                f"Contenu documentaire complet interdit dans {field_name}.",
            )


__all__ = [
    "CanonicalAuditEvent",
    "CanonicalAuditLogEvent",
    "CanonicalAuditSignalError",
    "CanonicalAuditSignals",
    "CanonicalMetricEvent",
    "build_canonical_audit_signals",
]
