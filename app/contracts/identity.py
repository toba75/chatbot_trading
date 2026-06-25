"""Identifiants opaques et version minimale des contrats publies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


ALLOWED_DOMAIN_IDENTIFIER_PREFIXES = frozenset(
    {
        "DOC",
        "CSRC",
        "CVER",
        "PROJ",
        "CLM",
        "VER",
        "DEP",
        "RSC",
        "EVS",
        "ANS",
        "CONV",
        "TURN",
        "STRAT",
        "SVER",
        "EXP",
        "DATA",
    }
)

_DOMAIN_IDENTIFIER_PATTERN = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<opaque>[A-Z0-9][A-Z0-9-]*)$")
_SCHEMA_VERSION_PATTERN = re.compile(r"^[1-9][0-9]*\.[0-9]+$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_RAW_HASH_PATTERN = re.compile(r"^[0-9a-f]{32}$|^[0-9a-f]{64}$", re.IGNORECASE)
_TECHNICAL_IDENTITY_PREFIXES = (
    "artifact:",
    "cache:",
    "graph:",
    "hash:",
    "log:",
    "outbox:",
    "postgres:",
    "postgres_schema:",
    "prompt_hash:",
    "qdrant:",
    "queue:",
    "report:",
    "snapshot:",
    "uuid:",
)
_FILE_PATH_SUFFIXES = (
    ".csv",
    ".json",
    ".md",
    ".parquet",
    ".pdf",
    ".txt",
)


@dataclass(frozen=True)
class DomainIdentifier:
    """Identifiant de domaine opaque publie entre contextes."""

    prefix: str
    value: str

    @classmethod
    def parse(cls, value: str) -> "DomainIdentifier":
        _ensure_text(value)
        _ensure_identifier_has_content(value)
        _ensure_not_file_path(value)
        _ensure_not_technical_identity(value)

        match = _DOMAIN_IDENTIFIER_PATTERN.fullmatch(value)
        if match is None:
            raise ValueError(f"Format d'identifiant invalide: {value}")

        prefix = match.group("prefix")
        if prefix not in ALLOWED_DOMAIN_IDENTIFIER_PREFIXES:
            raise ValueError(f"Prefixe inconnu: {prefix}")

        return cls(prefix=prefix, value=value)

    @classmethod
    def parse_with_prefix(cls, value: str, expected_prefix: str) -> "DomainIdentifier":
        if expected_prefix not in ALLOWED_DOMAIN_IDENTIFIER_PREFIXES:
            raise ValueError(f"Prefixe attendu inconnu: {expected_prefix}")

        identifier = cls.parse(value)
        if identifier.prefix != expected_prefix:
            raise ValueError(f"Prefixe attendu {expected_prefix}, obtenu {identifier.prefix}")

        return identifier

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ContractSchemaVersion:
    """Version de schema explicitement declaree par un contrat publie."""

    value: str

    @classmethod
    def parse(
        cls,
        value: str,
        supported_schema_versions: Iterable[str],
    ) -> "ContractSchemaVersion":
        supported_versions = _get_supported_versions(supported_schema_versions)
        _ensure_schema_version_has_content(value)

        if _SCHEMA_VERSION_PATTERN.fullmatch(value) is None:
            raise ValueError(f"Format de schema_version invalide: {value}")

        if value not in supported_versions:
            raise ValueError(f"schema_version non supportee: {value}")

        return cls(value=value)

    @classmethod
    def require_in_payload(
        cls,
        payload: Mapping[str, Any],
        supported_schema_versions: Iterable[str],
    ) -> "ContractSchemaVersion":
        if not isinstance(payload, Mapping):
            raise ValueError("Contrat publié non objet.")

        if "schema_version" not in payload:
            raise ValueError("schema_version absent")

        return cls.parse(
            payload["schema_version"],
            supported_schema_versions=supported_schema_versions,
        )

    def __str__(self) -> str:
        return self.value


def validate_contract_payload(
    payload: Mapping[str, Any],
    supported_schema_versions: Iterable[str],
) -> dict[str, Any]:
    """Valide les primitives communes d'un contrat publie."""

    schema_version = ContractSchemaVersion.require_in_payload(
        payload,
        supported_schema_versions=supported_schema_versions,
    )

    if "primary_identity" not in payload:
        raise ValueError("primary_identity absent")
    primary_identity = DomainIdentifier.parse(payload["primary_identity"])

    if "identities" not in payload:
        raise ValueError("identities absent")
    identities = payload["identities"]
    if not isinstance(identities, Mapping):
        raise ValueError("identities non objet")
    if len(identities) == 0:
        raise ValueError("identities vide")

    parsed_identities: dict[str, str] = {}
    for identity_name, identity_value in identities.items():
        if not isinstance(identity_name, str) or identity_name.strip() == "":
            raise ValueError("Nom d'identite vide")
        parsed_identities[identity_name] = str(DomainIdentifier.parse(identity_value))

    if str(primary_identity) not in parsed_identities.values():
        raise ValueError("primary_identity absent des identites")

    validated = dict(payload)
    validated["schema_version"] = str(schema_version)
    validated["primary_identity"] = str(primary_identity)
    validated["identities"] = parsed_identities
    return validated


def serialize_contract_payload(
    payload: Mapping[str, Any],
    supported_schema_versions: Iterable[str],
) -> str:
    """Serialise un contrat seulement apres validation de ses primitives."""

    validated_payload = validate_contract_payload(
        payload,
        supported_schema_versions=supported_schema_versions,
    )
    return json.dumps(validated_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _ensure_text(value: str) -> None:
    if not isinstance(value, str):
        raise ValueError("Identifiant non textuel")


def _ensure_identifier_has_content(value: str) -> None:
    if value.strip() == "":
        raise ValueError("Identifiant vide")
    if value != value.strip():
        raise ValueError("Identifiant non normalise")


def _ensure_schema_version_has_content(value: str) -> None:
    if not isinstance(value, str):
        raise ValueError("schema_version non textuelle")
    if value.strip() == "":
        raise ValueError("schema_version vide")
    if value != value.strip():
        raise ValueError("schema_version non normalisee")


def _get_supported_versions(supported_schema_versions: Iterable[str]) -> frozenset[str]:
    if supported_schema_versions is None:
        raise ValueError("Versions de schema supportees absentes")

    supported_versions = frozenset(supported_schema_versions)
    if len(supported_versions) == 0:
        raise ValueError("Versions de schema supportees absentes")

    for version in supported_versions:
        _ensure_schema_version_has_content(version)
        if _SCHEMA_VERSION_PATTERN.fullmatch(version) is None:
            raise ValueError(f"Format de schema_version supportee invalide: {version}")

    return supported_versions


def _ensure_not_file_path(value: str) -> None:
    lower_value = value.lower()
    if "\\" in value or "/" in value or lower_value.endswith(_FILE_PATH_SUFFIXES):
        raise ValueError("Chemin de fichier interdit comme identite metier principale")


def _ensure_not_technical_identity(value: str) -> None:
    lower_value = value.lower()
    if lower_value.startswith(_TECHNICAL_IDENTITY_PREFIXES):
        raise ValueError("Identifiant technique interdit comme identite metier principale")
    if _UUID_PATTERN.fullmatch(value) is not None:
        raise ValueError("Identifiant technique interdit comme identite metier principale")
    if _RAW_HASH_PATTERN.fullmatch(value) is not None:
        raise ValueError("Identifiant technique interdit comme identite metier principale")
