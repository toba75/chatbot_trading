"""Politique de couverture du corpus pilote M-012."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.contracts.source_references import CanonicalSourceRef


DIGITAL_NATIVE_CLEAN = "DIGITAL_NATIVE_CLEAN"
CLEAN_SCAN = "CLEAN_SCAN"
SKEWED_SCAN = "SKEWED_SCAN"
NOISY_SCAN = "NOISY_SCAN"
DEFECTIVE_OCR_LAYER = "DEFECTIVE_OCR_LAYER"
MIXED_DOCUMENT = "MIXED_DOCUMENT"
FRENCH_TEXT = "FRENCH_TEXT"
ENGLISH_TEXT = "ENGLISH_TEXT"
FINANCIAL_TABLES = "FINANCIAL_TABLES"
EQUATIONS = "EQUATIONS"
GRAPHICS = "GRAPHICS"
MULTI_COLUMNS = "MULTI_COLUMNS"
DIFFERENT_EDITION = "DIFFERENT_EDITION"

DOCUMENTARY_STRATA = frozenset(
    {
        DIGITAL_NATIVE_CLEAN,
        CLEAN_SCAN,
        SKEWED_SCAN,
        NOISY_SCAN,
        DEFECTIVE_OCR_LAYER,
        MIXED_DOCUMENT,
        FRENCH_TEXT,
        ENGLISH_TEXT,
        FINANCIAL_TABLES,
        EQUATIONS,
        GRAPHICS,
        MULTI_COLUMNS,
        DIFFERENT_EDITION,
    }
)
REQUIRED_DOCUMENTARY_STRATA = DOCUMENTARY_STRATA

_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "corpus_id",
        "policy_version",
        "frozen",
        "frozen_at",
        "documents",
        "exclusions",
        "frozen_manifest_sha256",
    }
)
_DOCUMENT_FIELDS = frozenset(
    {
        "pilot_document_id",
        "source_document_id",
        "original_path",
        "original_sha256",
        "original_immutable",
        "source_processing_status",
        "source_processing_ref",
        "strata",
        "edition_family_id",
        "edition_label",
        "inclusion_justification",
    }
)
_SOURCE_PROCESSING_REF_FIELDS = frozenset(
    {
        "schema_version",
        "canonical_source_id",
        "document_id",
        "canonical_version_id",
        "source_sha256",
        "canonical_artifact_sha256",
        "page_count",
        "accepted_at",
        "quality_policy_version",
    }
)
_EXCLUSION_FIELDS = frozenset({"candidate_document_id", "exclusion_reason"})

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Z]+-[A-Z0-9][A-Z0-9-]*$")
_ACCEPTED_SOURCE_PROCESSING_STATUS = "DIAGNOSED_ROUTED_CANONICAL_PUBLISHED"


@dataclass(frozen=True)
class PilotDocument:
    pilot_document_id: str
    source_document_id: str
    original_path: Path
    original_sha256: str
    source_processing_status: str
    source_processing_ref: Mapping[str, str]
    strata: frozenset[str]
    edition_family_id: str
    edition_label: str
    inclusion_justification: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        manifest_directory: Path | None,
    ) -> "PilotDocument":
        parsed = _ensure_mapping(payload, "PilotDocument")
        _ensure_allowed_fields(parsed, _DOCUMENT_FIELDS, "PilotDocument")

        pilot_document_id = _required_identifier(
            parsed,
            "pilot_document_id",
            "PDOC",
            missing_message="identifiant stable absent",
        )
        source_document_id = _required_identifier(parsed, "source_document_id", "DOC")
        original_path = _resolve_existing_file(
            _required_text(parsed, "original_path"),
            manifest_directory=manifest_directory,
        )
        original_sha256 = _required_sha256(parsed, "original_sha256")
        if _sha256_file(original_path) != original_sha256:
            raise ValueError(f"original_sha256 incoherent: {pilot_document_id}")

        if parsed.get("original_immutable") is not True:
            raise ValueError(f"original immuable requis: {pilot_document_id}")

        source_processing_status = _required_text(parsed, "source_processing_status")
        if source_processing_status != _ACCEPTED_SOURCE_PROCESSING_STATUS:
            raise ValueError(f"document non diagnostique par SP: {pilot_document_id}")

        source_processing_ref = _source_processing_ref(parsed, pilot_document_id)
        if source_processing_ref["document_id"] != source_document_id:
            raise ValueError(f"reference SP incoherente: {pilot_document_id}")

        strata = _required_strata(parsed, pilot_document_id)
        edition_family_id = _required_text(parsed, "edition_family_id")
        edition_label = _required_text(parsed, "edition_label")
        inclusion_justification = _required_text(parsed, "inclusion_justification")

        return cls(
            pilot_document_id=pilot_document_id,
            source_document_id=source_document_id,
            original_path=original_path,
            original_sha256=original_sha256,
            source_processing_status=source_processing_status,
            source_processing_ref=source_processing_ref,
            strata=strata,
            edition_family_id=edition_family_id,
            edition_label=edition_label,
            inclusion_justification=inclusion_justification,
        )


@dataclass(frozen=True)
class PilotExclusion:
    candidate_document_id: str
    exclusion_reason: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PilotExclusion":
        parsed = _ensure_mapping(payload, "PilotExclusion")
        _ensure_allowed_fields(parsed, _EXCLUSION_FIELDS, "PilotExclusion")
        return cls(
            candidate_document_id=_required_identifier(parsed, "candidate_document_id", "DOC"),
            exclusion_reason=_required_text(parsed, "exclusion_reason"),
        )


@dataclass(frozen=True)
class PilotCorpus:
    corpus_id: str
    policy_version: str
    frozen_at: str
    documents: tuple[PilotDocument, ...]
    exclusions: tuple[PilotExclusion, ...]
    frozen_manifest_sha256: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        manifest_directory: Path | None,
    ) -> "PilotCorpus":
        parsed = _ensure_mapping(payload, "PilotCorpus")
        _ensure_allowed_fields(parsed, _MANIFEST_FIELDS, "PilotCorpus")
        _ensure_frozen_manifest(parsed)

        if _required_text(parsed, "schema_version") != "1.0":
            raise ValueError("schema_version corpus pilote non supportee")
        if parsed.get("frozen") is not True:
            raise ValueError("manifeste de corpus non fige")

        documents_payload = _required_sequence(parsed, "documents")
        documents = tuple(
            PilotDocument.from_payload(document, manifest_directory=manifest_directory)
            for document in documents_payload
        )
        exclusions_payload = _required_sequence(parsed, "exclusions")
        exclusions = tuple(PilotExclusion.from_payload(exclusion) for exclusion in exclusions_payload)

        return cls(
            corpus_id=_required_identifier(parsed, "corpus_id", "PCORP"),
            policy_version=_required_text(parsed, "policy_version"),
            frozen_at=_required_utc_instant(parsed, "frozen_at"),
            documents=documents,
            exclusions=exclusions,
            frozen_manifest_sha256=_required_sha256(parsed, "frozen_manifest_sha256"),
        )

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def covered_strata(self) -> frozenset[str]:
        covered: set[str] = set()
        for document in self.documents:
            covered.update(document.strata)
        return frozenset(covered)


@dataclass(frozen=True)
class PilotCoveragePolicy:
    minimum_document_count: int = 50
    maximum_document_count: int = 100
    required_strata: frozenset[str] = REQUIRED_DOCUMENTARY_STRATA

    def validate_manifest_payload(
        self,
        payload: Mapping[str, Any],
        *,
        manifest_directory: Path | None = None,
    ) -> PilotCorpus:
        corpus = PilotCorpus.from_payload(payload, manifest_directory=manifest_directory)
        self.validate(corpus)
        return corpus

    def validate(self, corpus: PilotCorpus) -> None:
        if not isinstance(corpus, PilotCorpus):
            raise ValueError("PilotCorpus requis")
        if corpus.document_count < self.minimum_document_count or corpus.document_count > self.maximum_document_count:
            raise ValueError("PilotCorpus doit contenir entre 50 et 100 PDF")

        missing_strata = sorted(self.required_strata.difference(corpus.covered_strata))
        if len(missing_strata) > 0:
            raise ValueError(f"strates documentaires manquantes: {', '.join(missing_strata)}")

        self._ensure_unique_stable_identities(corpus)
        self._ensure_no_binary_duplicates(corpus)
        self._ensure_different_editions(corpus)

    def _ensure_unique_stable_identities(self, corpus: PilotCorpus) -> None:
        seen_pilot_ids: set[str] = set()
        seen_source_ids: set[str] = set()
        for document in corpus.documents:
            if document.pilot_document_id in seen_pilot_ids:
                raise ValueError(f"identifiant stable duplique: {document.pilot_document_id}")
            if document.source_document_id in seen_source_ids:
                raise ValueError(f"reference SP dupliquee: {document.source_document_id}")
            seen_pilot_ids.add(document.pilot_document_id)
            seen_source_ids.add(document.source_document_id)

    def _ensure_no_binary_duplicates(self, corpus: PilotCorpus) -> None:
        seen_hashes: set[str] = set()
        for document in corpus.documents:
            if document.original_sha256 in seen_hashes:
                raise ValueError(f"doublon binaire: {document.original_sha256}")
            seen_hashes.add(document.original_sha256)

    def _ensure_different_editions(self, corpus: PilotCorpus) -> None:
        editions_by_family: dict[str, set[str]] = {}
        for document in corpus.documents:
            if DIFFERENT_EDITION not in document.strata:
                continue
            editions_by_family.setdefault(document.edition_family_id, set()).add(document.edition_label)

        if not any(len(editions) >= 2 for editions in editions_by_family.values()):
            raise ValueError("DIFFERENT_EDITION requiert au moins deux editions distinctes")


@dataclass(frozen=True)
class PilotCorpusManifestValidator:
    coverage_policy: PilotCoveragePolicy = PilotCoveragePolicy()

    def validate_file(self, manifest_path: Path | str) -> PilotCorpus:
        resolved_manifest_path = Path(manifest_path)
        if not resolved_manifest_path.is_file():
            raise ValueError(f"manifeste de corpus absent: {resolved_manifest_path}")
        payload = json.loads(resolved_manifest_path.read_text(encoding="utf-8-sig"))
        return self.validate_payload(payload, manifest_directory=resolved_manifest_path.parent)

    def validate_payload(
        self,
        payload: Mapping[str, Any],
        *,
        manifest_directory: Path | None = None,
    ) -> PilotCorpus:
        return self.coverage_policy.validate_manifest_payload(
            payload,
            manifest_directory=manifest_directory,
        )


def freeze_pilot_corpus_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    manifest = _json_ready(payload)
    if not isinstance(manifest, dict):
        raise ValueError("manifeste de corpus non objet")
    manifest.pop("frozen_manifest_sha256", None)
    manifest["frozen_manifest_sha256"] = _stable_manifest_hash(manifest)
    return manifest


def _ensure_frozen_manifest(payload: Mapping[str, Any]) -> None:
    declared_hash = _required_sha256(payload, "frozen_manifest_sha256")
    actual_hash = _stable_manifest_hash(_manifest_without_hash(payload))
    if declared_hash != actual_hash:
        raise ValueError("manifeste modifie apres gel")


def _manifest_without_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    manifest = _json_ready(payload)
    if not isinstance(manifest, dict):
        raise ValueError("manifeste de corpus non objet")
    manifest.pop("frozen_manifest_sha256", None)
    return manifest


def _stable_manifest_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _source_processing_ref(payload: Mapping[str, Any], pilot_document_id: str) -> Mapping[str, str]:
    if "source_processing_ref" not in payload:
        raise ValueError(f"reference SP absente: {pilot_document_id}")
    source_processing_ref = _ensure_mapping(payload["source_processing_ref"], "source_processing_ref")
    _ensure_allowed_fields(source_processing_ref, _SOURCE_PROCESSING_REF_FIELDS, "source_processing_ref")
    canonical_ref = CanonicalSourceRef.from_payload(source_processing_ref)
    return {
        "schema_version": canonical_ref.schema_version,
        "canonical_source_id": canonical_ref.canonical_source_id,
        "document_id": canonical_ref.document_id,
        "canonical_version_id": canonical_ref.canonical_version_id,
        "source_sha256": canonical_ref.source_sha256,
        "canonical_artifact_sha256": canonical_ref.canonical_artifact_sha256,
        "page_count": str(canonical_ref.page_count),
        "accepted_at": canonical_ref.accepted_at,
        "quality_policy_version": canonical_ref.quality_policy_version,
    }


def _required_strata(payload: Mapping[str, Any], pilot_document_id: str) -> frozenset[str]:
    values = _required_sequence(payload, "strata")
    strata = frozenset(_ensure_text(item, "stratum") for item in values)
    if len(strata) == 0:
        raise ValueError(f"strates absentes: {pilot_document_id}")
    unknown_strata = sorted(strata.difference(DOCUMENTARY_STRATA))
    if len(unknown_strata) > 0:
        raise ValueError(f"strates inconnues: {', '.join(unknown_strata)}")
    return strata


def _required_identifier(
    payload: Mapping[str, Any],
    field_name: str,
    expected_prefix: str,
    *,
    missing_message: str | None = None,
) -> str:
    if field_name not in payload and missing_message is not None:
        raise ValueError(missing_message)
    value = _required_text(payload, field_name)
    if _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    if not value.startswith(expected_prefix + "-"):
        raise ValueError(f"{field_name} prefixe invalide")
    return value


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return _ensure_text(payload[field_name], field_name)


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_sha256(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name).lower()
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_utc_instant(payload: Mapping[str, Any], field_name: str) -> str:
    value = _required_text(payload, field_name)
    if _UTC_INSTANT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} invalide")
    return value


def _required_sequence(payload: Mapping[str, Any], field_name: str) -> tuple[Any, ...]:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} invalide")
    return tuple(value)


def _ensure_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} non objet")
    return value


def _ensure_allowed_fields(payload: Mapping[str, Any], allowed_fields: frozenset[str], label: str) -> None:
    unknown_fields = sorted(set(payload).difference(allowed_fields))
    if len(unknown_fields) > 0:
        raise ValueError(f"{label} champs inconnus: {', '.join(unknown_fields)}")


def _resolve_existing_file(path_value: str, *, manifest_directory: Path | None) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        if manifest_directory is None:
            raise ValueError(f"chemin non resolvable: {path_value}")
        path = manifest_directory / path
    resolved_path = path.resolve()
    if manifest_directory is not None:
        resolved_manifest_directory = manifest_directory.resolve()
        try:
            resolved_path.relative_to(resolved_manifest_directory)
        except ValueError as exc:
            raise ValueError(f"chemin hors corpus pilote: {path_value}") from exc
    if not resolved_path.is_file():
        raise ValueError(f"chemin non resolvable: {path_value}")
    return resolved_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "DOCUMENTARY_STRATA",
    "REQUIRED_DOCUMENTARY_STRATA",
    "PilotCorpus",
    "PilotCorpusManifestValidator",
    "PilotCoveragePolicy",
    "PilotDocument",
    "PilotExclusion",
    "freeze_pilot_corpus_manifest",
]
