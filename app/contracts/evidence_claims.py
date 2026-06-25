"""Contrats publies de preuves et d'affirmations verifiees."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

from app.contracts._validation import (
    dumps_contract_json,
    ensure_allowed_fields,
    freeze_contract_value,
    thaw_contract_value,
)
from app.contracts.identity import ContractSchemaVersion, DomainIdentifier
from app.contracts.source_references import SourceLocator, SourceLocatorValidationPolicy


EVIDENCE_CLAIM_SCHEMA_VERSIONS = frozenset({"1.0"})
SUPPORTS_DIRECTLY_RELATION = "SUPPORTS_DIRECTLY"
ALLOWED_EVIDENCE_RELATIONS = frozenset({SUPPORTS_DIRECTLY_RELATION})
VERIFIED_CLAIM_STATUS = "VERIFIED"
ALLOWED_VERIFIED_CLAIM_STATUSES = frozenset({VERIFIED_CLAIM_STATUS})

_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{64}$", re.IGNORECASE)
_EVIDENCE_REF_FIELDS = frozenset(
    {
        "schema_version",
        "evidence_id",
        "source_locator",
        "relation",
        "quoted_span_hash",
    }
)
_VERIFIED_CLAIM_REF_FIELDS = frozenset(
    {
        "schema_version",
        "claim_id",
        "claim_version",
        "canonical_text",
        "scope",
        "status",
        "verification_id",
        "evidence_refs",
        "dependency_group_ids",
    }
)


@dataclass(frozen=True)
class EvidenceRef:
    """Reference publiee d'une preuve directe verifiee par EG."""

    schema_version: str
    evidence_id: str
    source_locator: SourceLocator
    relation: str
    quoted_span_hash: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "EvidenceRef":
        _ensure_source_locator_validation_policy(source_locator_validation_policy)
        ensure_allowed_fields(payload, _EVIDENCE_REF_FIELDS, "EvidenceRef")
        schema_version = ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=EVIDENCE_CLAIM_SCHEMA_VERSIONS,
        )

        return cls(
            schema_version=str(schema_version),
            evidence_id=_required_domain_identifier(payload, "evidence_id", "EVS"),
            source_locator=_required_source_locator(
                payload,
                source_locator_validation_policy=source_locator_validation_policy,
            ),
            relation=_required_evidence_relation(payload),
            quoted_span_hash=_required_hash(payload, "quoted_span_hash"),
        )

    @classmethod
    def from_json(
        cls,
        serialized_payload: str,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "EvidenceRef":
        return cls.from_payload(
            _loads_contract_json(serialized_payload),
            source_locator_validation_policy=source_locator_validation_policy,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "source_locator": self.source_locator.to_payload(),
            "relation": self.relation,
            "quoted_span_hash": self.quoted_span_hash,
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_payload())


@dataclass(frozen=True)
class VerifiedClaimRef:
    """Reference publiee d'une affirmation verifiee consommable par RA et SD."""

    schema_version: str
    claim_id: str
    claim_version: int
    canonical_text: str
    scope: Mapping[str, Any]
    status: str
    verification_id: str
    evidence_refs: tuple[EvidenceRef, ...]
    dependency_group_ids: tuple[str, ...]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "VerifiedClaimRef":
        _ensure_source_locator_validation_policy(source_locator_validation_policy)
        ensure_allowed_fields(payload, _VERIFIED_CLAIM_REF_FIELDS, "VerifiedClaimRef")
        schema_version = ContractSchemaVersion.require_in_payload(
            payload,
            supported_schema_versions=EVIDENCE_CLAIM_SCHEMA_VERSIONS,
        )
        status = _required_verified_claim_status(payload)
        evidence_refs = _required_evidence_refs(
            payload,
            status=status,
            source_locator_validation_policy=source_locator_validation_policy,
        )

        return cls(
            schema_version=str(schema_version),
            claim_id=_required_domain_identifier(payload, "claim_id", "CLM"),
            claim_version=_required_positive_integer(payload, "claim_version"),
            canonical_text=_required_text(payload, "canonical_text"),
            scope=_required_scope(payload),
            status=status,
            verification_id=_required_domain_identifier(payload, "verification_id", "VER"),
            evidence_refs=evidence_refs,
            dependency_group_ids=_required_dependency_group_ids(payload),
        )

    @classmethod
    def from_json(
        cls,
        serialized_payload: str,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "VerifiedClaimRef":
        return cls.from_payload(
            _loads_contract_json(serialized_payload),
            source_locator_validation_policy=source_locator_validation_policy,
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "claim_id": self.claim_id,
            "claim_version": self.claim_version,
            "canonical_text": self.canonical_text,
            "scope": thaw_contract_value(self.scope),
            "status": self.status,
            "verification_id": self.verification_id,
            "evidence_refs": [evidence_ref.to_payload() for evidence_ref in self.evidence_refs],
            "dependency_group_ids": list(self.dependency_group_ids),
        }

    def to_json(self) -> str:
        return _dumps_contract_json(self.to_payload())


def _ensure_source_locator_validation_policy(value: Any) -> None:
    if not isinstance(value, SourceLocatorValidationPolicy):
        raise ValueError("source_locator_validation_policy invalide")


def _required_source_locator(
    payload: Mapping[str, Any],
    source_locator_validation_policy: SourceLocatorValidationPolicy,
) -> SourceLocator:
    if "source_locator" not in payload:
        raise ValueError("source_locator absent")
    source_locator_payload = payload["source_locator"]
    if not isinstance(source_locator_payload, Mapping):
        raise ValueError("source_locator non objet")

    try:
        return SourceLocator.from_payload(
            source_locator_payload,
            validation_policy=source_locator_validation_policy,
        )
    except ValueError as exc:
        raise ValueError(f"source_locator invalide: {exc}") from exc


def _required_evidence_relation(payload: Mapping[str, Any]) -> str:
    relation = _required_text(payload, "relation")
    if relation not in ALLOWED_EVIDENCE_RELATIONS:
        raise ValueError(f"relation non autorisee: {relation}")
    return relation


def _required_verified_claim_status(payload: Mapping[str, Any]) -> str:
    status = _required_text(payload, "status")
    if status not in ALLOWED_VERIFIED_CLAIM_STATUSES:
        raise ValueError(f"status non autorise: {status}")
    return status


def _required_evidence_refs(
    payload: Mapping[str, Any],
    status: str,
    source_locator_validation_policy: SourceLocatorValidationPolicy,
) -> tuple[EvidenceRef, ...]:
    if "evidence_refs" not in payload:
        raise ValueError("evidence_refs absent")

    evidence_ref_payloads = payload["evidence_refs"]
    if isinstance(evidence_ref_payloads, str) or not hasattr(evidence_ref_payloads, "__iter__"):
        raise ValueError("evidence_refs non liste")

    evidence_refs = []
    for evidence_ref_payload in evidence_ref_payloads:
        if not isinstance(evidence_ref_payload, Mapping):
            raise ValueError("evidence_refs invalide")
        try:
            evidence_refs.append(
                EvidenceRef.from_payload(
                    evidence_ref_payload,
                    source_locator_validation_policy=source_locator_validation_policy,
                )
            )
        except ValueError as exc:
            raise ValueError(f"evidence_refs invalide: {exc}") from exc

    evidence_refs_tuple = tuple(evidence_refs)
    if status == VERIFIED_CLAIM_STATUS and len(evidence_refs_tuple) == 0:
        raise ValueError("evidence_refs requis pour VERIFIED")

    if status == VERIFIED_CLAIM_STATUS and not any(
        evidence_ref.relation == SUPPORTS_DIRECTLY_RELATION for evidence_ref in evidence_refs_tuple
    ):
        raise ValueError("evidence_refs sans preuve directe")

    return evidence_refs_tuple


def _required_scope(payload: Mapping[str, Any]) -> dict[str, Any]:
    if "scope" not in payload:
        raise ValueError("scope absent")
    scope = payload["scope"]
    if not isinstance(scope, Mapping):
        raise ValueError("scope non objet")
    if len(scope) == 0:
        raise ValueError("scope vide")

    return freeze_contract_value(scope, "scope")


def _required_dependency_group_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    if "dependency_group_ids" not in payload:
        raise ValueError("dependency_group_ids absent")

    dependency_group_ids = payload["dependency_group_ids"]
    if isinstance(dependency_group_ids, str) or not hasattr(dependency_group_ids, "__iter__"):
        raise ValueError("dependency_group_ids non liste")

    parsed_dependency_group_ids = []
    for dependency_group_id in dependency_group_ids:
        try:
            parsed_dependency_group_ids.append(
                str(DomainIdentifier.parse_with_prefix(dependency_group_id, "DEP"))
            )
        except ValueError as exc:
            raise ValueError(f"dependency_group_ids invalide: {exc}") from exc

    if len(parsed_dependency_group_ids) == 0:
        raise ValueError("dependency_group_ids vide")

    return tuple(parsed_dependency_group_ids)


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
    value = payload[field_name]
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_hash(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_positive_integer(payload: Mapping[str, Any], field_name: str) -> int:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} invalide")
    return value


def _loads_contract_json(serialized_payload: str) -> Mapping[str, Any]:
    if not isinstance(serialized_payload, str):
        raise ValueError("contrat serialise non textuel")
    if serialized_payload.strip() == "":
        raise ValueError("contrat serialise vide")
    payload = json.loads(serialized_payload)
    if not isinstance(payload, Mapping):
        raise ValueError("Contrat publie non objet.")
    return payload


def _dumps_contract_json(payload: Mapping[str, Any]) -> str:
    return dumps_contract_json(payload)
