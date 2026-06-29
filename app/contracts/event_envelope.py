"""Enveloppe versionnée des événements intercontextes."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.contracts._validation import (
    dumps_contract_json,
    ensure_allowed_fields,
    ensure_no_forbidden_contract_keys,
    ensure_utc_instant_value,
    freeze_contract_value,
    thaw_contract_value,
)
from app.contracts.identity import ContractSchemaVersion, DomainIdentifier
from app.contracts.source_references import CanonicalSourceRef


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
        "Performed",
        "Published",
        "Registered",
        "Rejected",
        "Requested",
        "Resolved",
        "Retired",
        "Searchable",
        "Stale",
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
_EVENT_ENVELOPE_FIELDS = frozenset(
    {
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "aggregate_type",
        "aggregate_id",
        "aggregate_version",
        "correlation_id",
        "causation_id",
        "producer_context",
        "payload",
    }
)
_CANONICAL_SOURCE_SUPERSEDED_FIELDS = frozenset(
    {
        "schema_version",
        "canonical_source_id",
        "previous_canonical_version_id",
        "new_canonical_version_id",
    }
)
_EVENT_PAYLOAD_SCHEMA_VERSIONS = frozenset({"1.0"})
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
    """Contrat publié minimal d'un événement intercontexte."""

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
        ensure_allowed_fields(payload, _EVENT_ENVELOPE_FIELDS, "EventEnvelope")
        event_type = _required_event_type(payload)
        occurred_at = _required_utc_instant(payload, "occurred_at")
        aggregate_type = _required_aggregate_type(payload)
        aggregate_id = _required_aggregate_id(payload)
        producer_context = _required_producer_context(payload)
        event_payload = _required_event_payload(payload)
        _validate_typed_event_payload(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            occurred_at=occurred_at,
            producer_context=producer_context,
            event_payload=event_payload,
        )
        return cls(
            event_id=_required_event_id(payload),
            event_type=event_type,
            event_version=_required_event_version(payload),
            occurred_at=occurred_at,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=_required_positive_integer(payload, "aggregate_version"),
            correlation_id=_required_correlation_id(payload),
            causation_id=_required_causation_id(payload),
            producer_context=producer_context,
            payload=event_payload,
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
            "payload": thaw_contract_value(self.payload),
        }

    def to_json(self) -> str:
        return _dumps_event_json(self.to_payload())


@dataclass(frozen=True)
class EventIdempotenceDecision:
    """Résultat observable d'une vérification d'idempotence par event_id."""

    event_id: str
    already_processed: bool
    ledger: "EventIdempotenceLedger"


@dataclass
class EventIdempotenceLedger:
    """État de test non persistant des event_id déjà traités."""

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

        self.processed_event_ids = self.processed_event_ids | frozenset({event_id})
        return EventIdempotenceDecision(
            event_id=event_id,
            already_processed=False,
            ledger=self,
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
    if event_type.startswith(_COMMAND_PREFIXES) and not event_type.endswith("Performed"):
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
    ensure_no_forbidden_contract_keys(event_payload, "payload")
    return freeze_contract_value(
        event_payload,
        "payload",
        allow_empty_sequence=True,
    )


def _validate_typed_event_payload(
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    occurred_at: str,
    producer_context: str,
    event_payload: Mapping[str, Any],
) -> None:
    if event_type == "CanonicalSourcePublished":
        _validate_canonical_source_published_payload(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            occurred_at=occurred_at,
            producer_context=producer_context,
            event_payload=event_payload,
        )
        return
    if event_type == "CanonicalSourceSuperseded":
        _validate_canonical_source_superseded_payload(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            producer_context=producer_context,
            event_payload=event_payload,
        )
        return


def _validate_canonical_source_published_payload(
    *,
    aggregate_type: str,
    aggregate_id: str,
    occurred_at: str,
    producer_context: str,
    event_payload: Mapping[str, Any],
) -> None:
    try:
        canonical_source = CanonicalSourceRef.from_payload(thaw_contract_value(event_payload))
    except ValueError as exc:
        raise ValueError(f"payload CanonicalSourcePublished invalide: {exc}") from exc

    if producer_context != "SP":
        raise ValueError("producer_context incoherent avec CanonicalSourcePublished")
    if aggregate_type != "CanonicalSource":
        raise ValueError("aggregate_type incoherent avec CanonicalSourcePublished")
    if aggregate_id != canonical_source.canonical_source_id:
        raise ValueError("aggregate_id incoherent avec CanonicalSourcePublished")
    if occurred_at != canonical_source.accepted_at:
        raise ValueError("occurred_at incoherent avec CanonicalSourcePublished")


def _validate_canonical_source_superseded_payload(
    *,
    aggregate_type: str,
    aggregate_id: str,
    producer_context: str,
    event_payload: Mapping[str, Any],
) -> None:
    payload = thaw_contract_value(event_payload)
    try:
        ensure_allowed_fields(
            payload,
            _CANONICAL_SOURCE_SUPERSEDED_FIELDS,
            "CanonicalSourceSuperseded",
        )
        ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=_EVENT_PAYLOAD_SCHEMA_VERSIONS,
        )
        canonical_source_id = str(
            DomainIdentifier.parse_with_prefix(payload["canonical_source_id"], "CSRC")
        )
        previous_version_id = str(
            DomainIdentifier.parse_with_prefix(
                payload["previous_canonical_version_id"],
                "CVER",
            )
        )
        new_version_id = str(
            DomainIdentifier.parse_with_prefix(
                payload["new_canonical_version_id"],
                "CVER",
            )
        )
    except KeyError as exc:
        raise ValueError(f"payload CanonicalSourceSuperseded invalide: {exc.args[0]} absent") from exc
    except ValueError as exc:
        raise ValueError(f"payload CanonicalSourceSuperseded invalide: {exc}") from exc

    if producer_context != "SP":
        raise ValueError("producer_context incoherent avec CanonicalSourceSuperseded")
    if aggregate_type != "CanonicalSource":
        raise ValueError("aggregate_type incoherent avec CanonicalSourceSuperseded")
    if aggregate_id != canonical_source_id:
        raise ValueError("aggregate_id incoherent avec CanonicalSourceSuperseded")
    if previous_version_id == new_version_id:
        raise ValueError("payload CanonicalSourceSuperseded invalide: versions identiques")


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
    return ensure_utc_instant_value(value, field_name)


def _loads_event_json(serialized_payload: str) -> Mapping[str, Any]:
    _ensure_text_value(serialized_payload, "événement sérialisé")
    payload = json.loads(serialized_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("EventEnvelope non objet")
    return payload


def _dumps_event_json(payload: Mapping[str, Any]) -> str:
    return dumps_contract_json(payload)


def _ensure_mapping(value: Any, field_name: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} non objet")
