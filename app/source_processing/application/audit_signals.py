"""Signaux d'audit de clôture pour le traitement des sources M-003."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRunStatus,
    PageRouteName,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.source_document import DocumentId


class SourceProcessingAuditSignalError(ValueError):
    """Erreur explicite du contrat d'audit SP."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class DocumentIngestionAuditEvent:
    """Événement d'audit sans contenu documentaire complet."""

    trace_id: str
    document_id: DocumentId
    processing_run_id: ProcessingRunId
    phase: str
    status: DocumentProcessingRunStatus
    route_name: PageRouteName | None
    routing_policy_version: RoutingPolicyVersion
    served_model: str
    page_count: int
    latency_ms: float
    quarantined: bool
    error_code: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _ensure_text(self.trace_id, "trace_id", "SP_AUDIT_TRACE_ID_REQUIRED"))
        _ensure_document_id(self.document_id)
        _ensure_processing_run_id(self.processing_run_id)
        object.__setattr__(self, "phase", _ensure_text(self.phase, "phase", "SP_AUDIT_PHASE_REQUIRED"))
        object.__setattr__(self, "status", _ensure_status(self.status))
        object.__setattr__(self, "route_name", _ensure_optional_route_name(self.route_name))
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(self, "served_model", _ensure_text(self.served_model, "served_model", "SP_AUDIT_SERVED_MODEL_REQUIRED"))
        object.__setattr__(self, "page_count", _ensure_positive_integer(self.page_count, "page_count", "SP_AUDIT_PAGE_COUNT_INVALID"))
        object.__setattr__(self, "latency_ms", _ensure_non_negative_number(self.latency_ms, "latency_ms", "SP_AUDIT_LATENCY_INVALID"))
        _ensure_bool(self.quarantined, "quarantined", "SP_AUDIT_QUARANTINED_INVALID")
        object.__setattr__(self, "error_code", _ensure_optional_text(self.error_code, "error_code", "SP_AUDIT_ERROR_CODE_INVALID"))
        _ensure_status_route_contract(status=self.status, route_name=self.route_name)
        _ensure_status_error_contract(status=self.status, quarantined=self.quarantined, error_code=self.error_code)

    def to_log_mapping(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "document_id": self.document_id.value,
            "processing_run_id": self.processing_run_id.value,
            "phase": self.phase,
            "status": self.status.value,
            "route_name": self.route_name.value if self.route_name is not None else None,
            "routing_policy_version": self.routing_policy_version.value,
            "served_model": self.served_model,
            "page_count": self.page_count,
            "latency_ms": self.latency_ms,
            "quarantined": self.quarantined,
            "error_code": self.error_code,
        }


@dataclass(frozen=True)
class SourceProcessingAuditLogEvent:
    """Log structuré SP sans payload documentaire."""

    fields: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", _freeze_observable_mapping(self.fields))

    def to_mapping(self) -> dict[str, Any]:
        return dict(self.fields)


@dataclass(frozen=True)
class SourceProcessingMetricEvent:
    """Métrique d'ingestion M-003."""

    name: str
    value: float
    unit: str
    tags: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _ensure_text(self.name, "name", "SP_AUDIT_METRIC_NAME_REQUIRED"))
        object.__setattr__(self, "value", _ensure_non_negative_number(self.value, "value", "SP_AUDIT_METRIC_VALUE_INVALID"))
        object.__setattr__(self, "unit", _ensure_text(self.unit, "unit", "SP_AUDIT_METRIC_UNIT_REQUIRED"))
        object.__setattr__(self, "tags", _freeze_string_mapping(self.tags))

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "tags": dict(self.tags),
        }


@dataclass(frozen=True)
class SourceProcessingAuditSignals:
    """Lot de logs et métriques de clôture M-003."""

    logs: tuple[SourceProcessingAuditLogEvent, ...]
    metrics: tuple[SourceProcessingMetricEvent, ...]

    def __post_init__(self) -> None:
        logs = _ensure_log_events(self.logs)
        metrics = _ensure_metric_events(self.metrics)
        object.__setattr__(self, "logs", logs)
        object.__setattr__(self, "metrics", metrics)


def build_source_processing_audit_signals(
    events: Sequence[DocumentIngestionAuditEvent],
) -> SourceProcessingAuditSignals:
    parsed_events = _ensure_audit_events(events)
    logs = tuple(
        SourceProcessingAuditLogEvent(fields=event.to_log_mapping())
        for event in parsed_events
    )

    route_counts: dict[str, int] = {}
    error_counts: dict[tuple[str, str], int] = {}
    quarantined_count = 0

    for event in parsed_events:
        if event.route_name is not None:
            route_name = event.route_name.value
            route_counts[route_name] = route_counts.get(route_name, 0) + 1
        if event.quarantined:
            quarantined_count += 1
        if event.error_code is not None:
            key = (event.served_model, event.error_code)
            error_counts[key] = error_counts.get(key, 0) + 1

    metrics: list[SourceProcessingMetricEvent] = []
    for route_name, count in route_counts.items():
        metrics.append(
            SourceProcessingMetricEvent(
                name="documents_par_route",
                value=float(count),
                unit="documents",
                tags={"route_name": route_name},
            )
        )

    metrics.append(
        SourceProcessingMetricEvent(
            name="taux_quarantaine",
            value=quarantined_count / len(parsed_events),
            unit="ratio",
            tags={"scope": "m003"},
        )
    )

    for (served_model, error_code), count in error_counts.items():
        metrics.append(
            SourceProcessingMetricEvent(
                name="erreurs_par_modele",
                value=float(count),
                unit="errors",
                tags={"served_model": served_model, "error_code": error_code},
            )
        )

    return SourceProcessingAuditSignals(logs=logs, metrics=tuple(metrics))


def _ensure_audit_events(
    value: Sequence[DocumentIngestionAuditEvent],
) -> tuple[DocumentIngestionAuditEvent, ...]:
    if value is None:
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_EVENTS_REQUIRED",
            "Les événements d'audit M-003 sont requis.",
        )
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_EVENTS_INVALID",
            "Les événements d'audit M-003 doivent former une séquence.",
        )
    events = tuple(value)
    if len(events) == 0:
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_EVENTS_REQUIRED",
            "Les événements d'audit M-003 sont vides.",
        )
    for event in events:
        if not isinstance(event, DocumentIngestionAuditEvent):
            raise SourceProcessingAuditSignalError(
                "SP_AUDIT_EVENT_INVALID",
                "Chaque événement d'audit doit utiliser DocumentIngestionAuditEvent.",
            )
    return events


def _ensure_log_events(
    value: Sequence[SourceProcessingAuditLogEvent],
) -> tuple[SourceProcessingAuditLogEvent, ...]:
    if value is None:
        raise SourceProcessingAuditSignalError("SP_AUDIT_LOGS_REQUIRED", "Les logs d'audit sont requis.")
    logs = tuple(value)
    if len(logs) == 0:
        raise SourceProcessingAuditSignalError("SP_AUDIT_LOGS_REQUIRED", "Les logs d'audit sont vides.")
    for log in logs:
        if not isinstance(log, SourceProcessingAuditLogEvent):
            raise SourceProcessingAuditSignalError("SP_AUDIT_LOG_INVALID", "Log d'audit invalide.")
    return logs


def _ensure_metric_events(
    value: Sequence[SourceProcessingMetricEvent],
) -> tuple[SourceProcessingMetricEvent, ...]:
    if value is None:
        raise SourceProcessingAuditSignalError("SP_AUDIT_METRICS_REQUIRED", "Les métriques d'audit sont requises.")
    metrics = tuple(value)
    metric_names = {metric.name for metric in metrics if isinstance(metric, SourceProcessingMetricEvent)}
    required_metric_names = {"documents_par_route", "taux_quarantaine"}
    missing_metric_names = required_metric_names - metric_names
    if len(missing_metric_names) > 0:
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_METRICS_REQUIRED",
            "Métriques d'audit M-003 absentes: " + ", ".join(sorted(missing_metric_names)),
        )
    for metric in metrics:
        if not isinstance(metric, SourceProcessingMetricEvent):
            raise SourceProcessingAuditSignalError("SP_AUDIT_METRIC_INVALID", "Métrique d'audit invalide.")
    return metrics


def _ensure_status_error_contract(
    *,
    status: DocumentProcessingRunStatus,
    quarantined: bool,
    error_code: str | None,
) -> None:
    if status is DocumentProcessingRunStatus.QUARANTINED:
        if not quarantined:
            raise SourceProcessingAuditSignalError(
                "SP_AUDIT_QUARANTINE_FLAG_REQUIRED",
                "Un statut QUARANTINED doit porter quarantined=true.",
            )
        if error_code is None:
            raise SourceProcessingAuditSignalError(
                "SP_AUDIT_ERROR_CODE_REQUIRED",
                "Une quarantaine M-003 doit porter un code d'erreur.",
            )
        return

    if quarantined:
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_QUARANTINE_STATUS_REQUIRED",
            "Un événement quarantined doit porter le statut QUARANTINED.",
        )

    if status is DocumentProcessingRunStatus.ROUTE_PLANNED and error_code is not None:
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_ERROR_CODE_FORBIDDEN",
            "Un routage planifié ne doit pas porter de code d'erreur.",
        )

    if status is not DocumentProcessingRunStatus.ROUTE_PLANNED and error_code is not None:
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_ERROR_CODE_FORBIDDEN",
            "Un code d'erreur n'est accepté que pour une quarantaine M-003.",
        )


def _ensure_status_route_contract(
    *,
    status: DocumentProcessingRunStatus,
    route_name: PageRouteName | None,
) -> None:
    if status is DocumentProcessingRunStatus.ROUTE_PLANNED:
        if route_name is None:
            raise SourceProcessingAuditSignalError(
                "SP_AUDIT_ROUTE_REQUIRED",
                "Un routage planifié doit porter une route.",
            )
        return

    if route_name is not None:
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_ROUTE_FORBIDDEN",
            "Une tentative non routée ne doit pas porter de route.",
        )


def _ensure_status(value: Any) -> DocumentProcessingRunStatus:
    if isinstance(value, DocumentProcessingRunStatus):
        return value
    raise SourceProcessingAuditSignalError("SP_AUDIT_STATUS_INVALID", "status invalide.")


def _ensure_optional_route_name(value: Any) -> PageRouteName | None:
    if value is None:
        return None
    return PageRouteName.from_value(value)


def _ensure_text(value: Any, field_name: str, code: str) -> str:
    if not isinstance(value, str):
        raise SourceProcessingAuditSignalError(code, f"Champ textuel invalide: {field_name}")
    if value.strip() == "":
        raise SourceProcessingAuditSignalError(code, f"Champ textuel vide: {field_name}")
    if value != value.strip():
        raise SourceProcessingAuditSignalError(code, f"Champ textuel non normalisé: {field_name}")
    return value


def _ensure_optional_text(value: Any, field_name: str, code: str) -> str | None:
    if value is None:
        return None
    return _ensure_text(value, field_name, code)


def _ensure_bool(value: Any, field_name: str, code: str) -> None:
    if not isinstance(value, bool):
        raise SourceProcessingAuditSignalError(code, f"Booléen invalide: {field_name}")


def _ensure_positive_integer(value: Any, field_name: str, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SourceProcessingAuditSignalError(code, f"Entier positif invalide: {field_name}")
    return value


def _ensure_non_negative_number(value: Any, field_name: str, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SourceProcessingAuditSignalError(code, f"Nombre invalide: {field_name}")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise SourceProcessingAuditSignalError(code, f"Nombre négatif ou infini: {field_name}")
    return number


def _ensure_document_id(value: Any) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise SourceProcessingAuditSignalError("SP_AUDIT_DOCUMENT_ID_INVALID", "document_id invalide.")
    return value


def _ensure_processing_run_id(value: Any) -> ProcessingRunId:
    if not isinstance(value, ProcessingRunId):
        raise SourceProcessingAuditSignalError("SP_AUDIT_PROCESSING_RUN_ID_INVALID", "processing_run_id invalide.")
    return value


def _ensure_routing_policy_version(value: Any) -> RoutingPolicyVersion:
    if not isinstance(value, RoutingPolicyVersion):
        raise SourceProcessingAuditSignalError(
            "SP_AUDIT_ROUTING_POLICY_VERSION_INVALID",
            "routing_policy_version invalide.",
        )
    return value


def _freeze_observable_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SourceProcessingAuditSignalError("SP_AUDIT_MAPPING_REQUIRED", "Mapping d'audit requis.")
    frozen: dict[str, Any] = {}
    for key, nested_value in value.items():
        parsed_key = _ensure_text(key, "field_name", "SP_AUDIT_FIELD_NAME_REQUIRED")
        if isinstance(nested_value, str):
            frozen[parsed_key] = _ensure_text(nested_value, parsed_key, "SP_AUDIT_FIELD_VALUE_REQUIRED")
        elif isinstance(nested_value, bool) or isinstance(nested_value, int) or nested_value is None:
            frozen[parsed_key] = nested_value
        elif isinstance(nested_value, float):
            frozen[parsed_key] = _ensure_non_negative_number(nested_value, parsed_key, "SP_AUDIT_FIELD_VALUE_INVALID")
        else:
            raise SourceProcessingAuditSignalError(
                "SP_AUDIT_FIELD_VALUE_INVALID",
                f"Valeur d'audit invalide: {parsed_key}",
            )
    return MappingProxyType(frozen)


def _freeze_string_mapping(value: Mapping[str, str]) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise SourceProcessingAuditSignalError("SP_AUDIT_TAGS_REQUIRED", "Tags de métrique requis.")
    frozen: dict[str, str] = {}
    for key, nested_value in value.items():
        parsed_key = _ensure_text(key, "tag_name", "SP_AUDIT_TAG_NAME_REQUIRED")
        frozen[parsed_key] = _ensure_text(nested_value, parsed_key, "SP_AUDIT_TAG_VALUE_REQUIRED")
    return MappingProxyType(frozen)


__all__ = [
    "DocumentIngestionAuditEvent",
    "SourceProcessingAuditLogEvent",
    "SourceProcessingAuditSignalError",
    "SourceProcessingAuditSignals",
    "SourceProcessingMetricEvent",
    "build_source_processing_audit_signals",
]
