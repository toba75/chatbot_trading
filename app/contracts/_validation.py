"""Validation interne partagee par les contrats publies."""

from __future__ import annotations

import json
import math
from datetime import datetime
from types import MappingProxyType
from typing import Any, Iterable, Mapping


FORBIDDEN_CONTRACT_KEYS = frozenset(
    {
        "answer_draft",
        "answer_repository_id",
        "api_key",
        "authorization",
        "broker",
        "claim_record_id",
        "claim_repository_id",
        "compiled_strategy",
        "delivery_topic",
        "eg_graph_node_id",
        "event_store",
        "evidence_link_id",
        "evidence_set_id",
        "extractor_prompt_hash",
        "job_id",
        "job_name",
        "nli_trace",
        "outbox_id",
        "password",
        "qdrant_id",
        "queue",
        "ra_internal_state",
        "research_case_status",
        "retry_policy",
        "rule_expression",
        "secret",
        "source_processing_model",
        "sp_table",
        "strategy_candidate_id",
        "strategy_rule",
        "token",
        "verification_case_id",
    }
)


class FrozenList(tuple):
    """Sequence immuable qui conserve l'egalite avec les listes d'entree."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, list):
            return tuple(self) == tuple(other)
        return tuple.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


def ensure_allowed_fields(
    payload: Mapping[str, Any],
    allowed_fields: Iterable[str],
    contract_name: str,
) -> None:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{contract_name} non objet")

    allowed_field_set = frozenset(allowed_fields)
    for key in payload:
        _ensure_mapping_key(key, contract_name)
        if key not in allowed_field_set:
            raise ValueError(f"champ interdit: {key}")


def ensure_no_forbidden_contract_keys(value: Any, field_name: str) -> None:
    if isinstance(value, Mapping):
        for key, child_value in value.items():
            _ensure_mapping_key(key, field_name)
            if key.lower() in FORBIDDEN_CONTRACT_KEYS:
                raise ValueError(f"cle interdite: {key}")
            ensure_no_forbidden_contract_keys(child_value, field_name)
    elif isinstance(value, (list, tuple)):
        for child_value in value:
            ensure_no_forbidden_contract_keys(child_value, field_name)


def ensure_utc_instant_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{field_name} invalide") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(f"{field_name} invalide")
    return value


def freeze_contract_value(
    value: Any,
    field_name: str,
    *,
    allow_empty_mapping: bool = False,
    allow_empty_sequence: bool = False,
) -> Any:
    if value is None:
        raise ValueError(f"{field_name} invalide")
    if isinstance(value, str):
        if value.strip() == "" or value != value.strip():
            raise ValueError(f"{field_name} invalide")
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} invalide")
        return value
    if isinstance(value, Mapping):
        if len(value) == 0 and not allow_empty_mapping:
            raise ValueError(f"{field_name} invalide")
        frozen_mapping: dict[str, Any] = {}
        for key, child_value in value.items():
            _ensure_mapping_key(key, field_name)
            if key.lower() in FORBIDDEN_CONTRACT_KEYS:
                raise ValueError(f"cle interdite: {key}")
            frozen_mapping[key] = freeze_contract_value(
                child_value,
                field_name,
                allow_empty_mapping=allow_empty_mapping,
                allow_empty_sequence=allow_empty_sequence,
            )
        return MappingProxyType(frozen_mapping)
    if isinstance(value, (list, tuple)):
        if len(value) == 0 and not allow_empty_sequence:
            raise ValueError(f"{field_name} invalide")
        return FrozenList(
            freeze_contract_value(
                child_value,
                field_name,
                allow_empty_mapping=allow_empty_mapping,
                allow_empty_sequence=allow_empty_sequence,
            )
            for child_value in value
        )
    raise ValueError(f"{field_name} invalide")


def thaw_contract_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: thaw_contract_value(child_value) for key, child_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw_contract_value(child_value) for child_value in value]
    return value


def dumps_contract_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _ensure_mapping_key(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or value.strip() == "" or value != value.strip():
        raise ValueError(f"{field_name} invalide")
    return value
