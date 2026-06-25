"""Enveloppe versionnee des evenements intercontextes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.contracts.identity import DomainIdentifier


SUPPORTED_EVENT_VERSIONS = frozenset({1})
ALLOWED_EVENT_PRODUCER_CONTEXTS = frozenset({"SP", "KA", "EG", "RA", "CV", "SD", "EX"})
ALLOWED_PAST_EVENT_SUFFIXES = frozenset(
    {
        "Accepted",
        "Archived",
        "Built",
        "Cancelled",
        "Completed",
        "Compiled",
        "Created",
        "Deleted",
        "Failed",
        "Imported",
        "Indexed",
        "Processed",
        "Published",
        "Registered",
        "Rejected",
        "Resolved",
        "Started",
        "Superseded",
        "Updated",
        "Verified",
    }
)

_EVENT_ID_PATTERN = re.compile(r"^EVT-[A-Z0-9][A-Z0-9-]*$")
_CORRELATION_ID_PATTERN = re.compile(r"^CORR-[A-Z0-9][A-Z0-9-]*$")
_CAUSATION_ID_PATTERN = re.compile(r"^(CMD|EVT)-[A-Z0-9][A-Z0-9-]*$")
_EVENT_TYPE_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_TECHNICAL_JOB_NAME_PATTERN = re.compile(r"^[A-Z0-9]+(?:_[A-Z0-9]+)+$")
_UTC_INSTANT_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
)
_COMMAND_PREFIXES = (
    "Accept",
    "Archive",
    "Build",
    "Cancel",
    "Complete",
    "Compile",
    "Convert",
    "Create",
    "Delete",
    "Execute",
    "Get",
    "Import",
    "Index",
    "List",
    "Process",
    "Publish",
    "Register",
    "Reject",
    "Resolve",
    "Run",
    "Search",
    "Start",
    "Supersede",
    "Update",
    "Verify",
)


@dataclass(frozen=True)
class EventEnvelope:
    """Contrat publie minimal d'un evenement intercontexte."""

    event_id: str
    event_type: str
    event_version: int
    occurred_at: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    correlation_id: str
    causation_id: str
    producer_context: str
    payload: Mapping[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "EventEnvelope":
        _ensure_mapping(payload, "EventEnvelope")
        return cls(
            event_id=_required_event_id(payload),
            event_type=_required_event_type(payload),
            event_version=_required_event_version(payload),
            occurred_at=_required_utc_instant(payload, "occurred_at"),
            aggregate_type=_required_aggregate_type(payload),
            aggregate_id=_required_aggregate_id(payload),
            aggregate_version=_required_positive_integer(payload, "aggregate_version"),
            correlation_id=_required_correlation_id(payload),
            causation_id=_required_causation_id(payload),
            producer_context=_required_producer_context(payload),
            payload=_required_event_payload(payload),
        )

    @classmethod
    def from_json(cls, serialized_payload: str) -> "EventEnvelope":
        return cls.from_payload(_loads_event_json(serialized_payload))

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_version": self.aggregate_version,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "producer_context": self.producer_context,
            "payload": _copy_event_payload_value(self.payload),
        }

    def to_json(self) -> str:
        return _dumps_event_json(self.to_payload())


@dataclass(frozen=True)
class EventIdempotenceDecision:
    """Resultat observable d'une verification d'idempotence par event_id."""

    event_id: str
    already_processed: bool
    ledger: "EventIdempotenceLedger"


@dataclass(frozen=True)
class EventIdempotenceLedger:
    """Etat de test non persistant des event_id deja traites."""

    processed_event_ids: frozenset[str]

    @classmethod
    def from_processed_event_ids(
        cls,
        processed_event_ids: Iterable[str],
    ) -> "EventIdempotenceLedger":
        if processed_event_ids is None:
            raise ValueError("processed_event_ids absent")
        if isinstance(processed_event_ids, str) or not hasattr(processed_event_ids, "__iter__"):
            raise ValueError("processed_event_ids non liste")

        parsed_event_ids = []
        for event_id in processed_event_ids:
            parsed_event_ids.append(_ensure_event_id_value(event_id, "event_id"))

        return cls(processed_event_ids=frozenset(parsed_event_ids))

    def has_processed(self, event: Any) -> bool:
        event_id = _event_id_from_event_or_text(event)
        return event_id in self.processed_event_ids

    def record(self, event: Any) -> EventIdempotenceDecision:
        event_id = _event_id_from_event_or_text(event)
        if event_id in self.processed_event_ids:
            return EventIdempotenceDecision(
                event_id=event_id,
                already_processed=True,
                ledger=self,
            )

        return EventIdempotenceDecision(
            event_id=event_id,
            already_processed=False,
            ledger=EventIdempotenceLedger(
                processed_event_ids=self.processed_event_ids | frozenset({event_id}),
            ),
        )


def _event_id_from_event_or_text(value: Any) -> str:
    if isinstance(value, EventEnvelope):
        return value.event_id
    if isinstance(value, str):
        return _ensure_event_id_value(value, "event_id")
    raise ValueError("event invalide")


def _required_event_id(payload: Mapping[str, Any]) -> str:
    return _ensure_event_id_value(_required_text(payload, "event_id"), "event_id")


def _ensure_event_id_value(value: Any, field_name: str) -> str:
    text_value = _ensure_text_value(value, field_name)
    if _EVENT_ID_PATTERN.fullmatch(text_value) is None:
        raise ValueError(f"{field_name} invalide")
    return text_value


def _required_event_type(payload: Mapping[str, Any]) -> str:
    event_type = _required_text(payload, "event_type")
    if _TECHNICAL_JOB_NAME_PATTERN.fullmatch(event_type) is not None:
        raise ValueError("event_type invalide: job technique")
    if _EVENT_TYPE_PATTERN.fullmatch(event_type) is None:
        raise ValueError("event_type invalide: fait passe attendu")
    if event_type.startswith(_COMMAND_PREFIXES):
        raise ValueError("event_type invalide: fait passe attendu")
    if not event_type.endswith(tuple(sorted(ALLOWED_PAST_EVENT_SUFFIXES))):
        raise ValueError("event_type invalide: fait passe attendu")
    return event_type


def _required_event_version(payload: Mapping[str, Any]) -> int:
    event_version = _required_positive_integer(payload, "event_version")
    if event_version not in SUPPORTED_EVENT_VERSIONS:
        raise ValueError(f"event_version non supportee: {event_version}")
    return event_version


def _required_aggregate_type(payload: Mapping[str, Any]) -> str:
    aggregate_type = _required_text(payload, "aggregate_type")
    if _EVENT_TYPE_PATTERN.fullmatch(aggregate_type) is None:
        raise ValueError("aggregate_type invalide")
    return aggregate_type


def _required_aggregate_id(payload: Mapping[str, Any]) -> str:
    aggregate_id = _required_text(payload, "aggregate_id")
    try:
        return str(DomainIdentifier.parse(aggregate_id))
    except ValueError as exc:
        raise ValueError(f"aggregate_id invalide: {exc}") from exc


def _required_correlation_id(payload: Mapping[str, Any]) -> str:
    correlation_id = _required_text(payload, "correlation_id")
    if _CORRELATION_ID_PATTERN.fullmatch(correlation_id) is None:
        raise ValueError("correlation_id invalide")
    return correlation_id


def _required_causation_id(payload: Mapping[str, Any]) -> str:
    causation_id = _required_text(payload, "causation_id")
    if _CAUSATION_ID_PATTERN.fullmatch(causation_id) is None:
        raise ValueError("causation_id invalide")
    return causation_id


def _required_producer_context(payload: Mapping[str, Any]) -> str:
    producer_context = _required_text(payload, "producer_context")
    if producer_context not in ALLOWED_EVENT_PRODUCER_CONTEXTS:
        raise ValueError(f"producer_context inconnu: {producer_context}")
    return producer_context


def _required_event_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if "payload" not in payload:
        raise ValueError("payload absent")
    event_payload = payload["payload"]
    if not isinstance(event_payload, Mapping):
        raise ValueError("payload non objet")
    return _copy_event_payload_mapping(event_payload, "payload")


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


def _required_positive_integer(payload: Mapping[str, Any], field_name: str) -> int:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_utc_instant(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    return value


def _copy_event_payload_mapping(value: Mapping[str, Any], field_name: str) -> dict[str, Any]:
    copied_value: dict[str, Any] = {}
    for key, child_value in value.items():
        if not isinstance(key, str) or key.strip() == "" or key != key.strip():
            raise ValueError(f"{field_name} invalide")
        copied_value[key] = _copy_event_payload_value(child_value)
    return copied_value


def _copy_event_payload_value(value: Any) -> Any:
    if value is None:
        raise ValueError("payload invalide")
    if isinstance(value, str):
        if value.strip() == "" or value != value.strip():
            raise ValueError("payload invalide")
        return value
    if isinstance(value, Mapping):
        return _copy_event_payload_mapping(value, "payload")
    if isinstance(value, list):
        return [_copy_event_payload_value(child_value) for child_value in value]
    if isinstance(value, tuple):
        return [_copy_event_payload_value(child_value) for child_value in value]
    if isinstance(value, (bool, int, float)):
        return value
    raise ValueError("payload invalide")


def _loads_event_json(serialized_payload: str) -> Mapping[str, Any]:
    _ensure_text_value(serialized_payload, "evenement serialise")
    payload = json.loads(serialized_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("EventEnvelope non objet")
    return payload


def _dumps_event_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _ensure_mapping(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
