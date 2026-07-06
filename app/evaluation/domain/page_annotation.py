"""Oracle humain page par page pour l'evaluation pilote M-012."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.source_references import SourceLocator, SourceLocatorValidationPolicy
from app.evaluation.domain.pilot_corpus import PilotCorpus


EVALUABLE = "EVALUABLE"
EMPTY_DECLARED = "EMPTY_DECLARED"
REJECTED_DECLARED = "REJECTED_DECLARED"
NO_ROUTE = "NO_ROUTE"
HUMAN_REVIEWER = "HUMAN_REVIEWER"

EXPECTED_PAGE_STATES = frozenset({EVALUABLE, EMPTY_DECLARED, REJECTED_DECLARED})
EXPECTED_ROUTES = frozenset({"NATIVE_TEXT", "OCR", "OCR_WITH_TABLES", "TABLE_EXTRACTION", NO_ROUTE})

_ANNOTATION_SET_FIELDS = frozenset(
    {
        "schema_version",
        "annotation_set_id",
        "corpus_id",
        "policy_version",
        "annotation_version",
        "frozen",
        "frozen_at",
        "replaces_annotation_set_id",
        "historical_annotation_versions",
        "benchmark_pages",
        "annotations",
        "frozen_annotation_sha256",
    }
)
_PAGE_REF_FIELDS = frozenset({"pilot_document_id", "source_document_id", "canonical_version_id", "page_pdf"})
_ANNOTATION_FIELDS = frozenset(
    {
        "annotation_id",
        "page_ref",
        "annotation_version",
        "annotation_author_type",
        "generated_by_evaluated_system",
        "expected_state",
        "expected_route",
        "reference_transcription",
        "empty_or_rejection_reason",
        "critical_numeric_values",
        "table_cells",
        "reading_order",
        "provenance_zones",
    }
)
_NUMERIC_VALUE_FIELDS = frozenset({"value_id", "signed_value", "unit", "context", "provenance_zone_id"})
_TABLE_CELL_FIELDS = frozenset({"table_id", "row_index", "column_index", "text", "provenance_zone_id"})
_READING_ORDER_FIELDS = frozenset({"order_index", "role", "provenance_zone_id"})
_PROVENANCE_ZONE_FIELDS = frozenset({"provenance_zone_id", "source_locator", "human_label"})

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
_IDENTIFIER_PATTERN = re.compile(r"^[A-Z]+-[A-Z0-9][A-Z0-9-]*$")
_UTC_INSTANT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


@dataclass(frozen=True)
class PageReference:
    pilot_document_id: str
    source_document_id: str
    canonical_version_id: str
    page_pdf: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PageReference":
        parsed = _ensure_mapping(payload, "PageReference")
        _ensure_allowed_fields(parsed, _PAGE_REF_FIELDS, "PageReference")
        return cls(
            pilot_document_id=_required_identifier(parsed, "pilot_document_id", "PDOC"),
            source_document_id=_required_identifier(parsed, "source_document_id", "DOC"),
            canonical_version_id=_required_identifier(parsed, "canonical_version_id", "CVER"),
            page_pdf=_required_positive_integer(parsed, "page_pdf"),
        )

    @property
    def key(self) -> tuple[str, str, str, int]:
        return (
            self.pilot_document_id,
            self.source_document_id,
            self.canonical_version_id,
            self.page_pdf,
        )


@dataclass(frozen=True)
class ProvenanceZone:
    provenance_zone_id: str
    source_locator: SourceLocator
    human_label: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "ProvenanceZone":
        parsed = _ensure_mapping(payload, "ProvenanceZone")
        _ensure_allowed_fields(parsed, _PROVENANCE_ZONE_FIELDS, "ProvenanceZone")
        return cls(
            provenance_zone_id=_required_identifier(parsed, "provenance_zone_id", "ZONE"),
            source_locator=SourceLocator.from_payload(
                _ensure_mapping(_required_field(parsed, "source_locator"), "source_locator"),
                validation_policy=source_locator_validation_policy,
            ),
            human_label=_required_text(parsed, "human_label"),
        )


@dataclass(frozen=True)
class CriticalNumericValue:
    value_id: str
    signed_value: str
    unit: str
    context: str
    provenance_zone_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "CriticalNumericValue":
        parsed = _ensure_mapping(payload, "CriticalNumericValue")
        _ensure_allowed_fields(parsed, _NUMERIC_VALUE_FIELDS, "CriticalNumericValue")
        signed_value = _required_text(parsed, "signed_value")
        if not (signed_value.startswith("+") or signed_value.startswith("-")):
            raise ValueError("valeur numerique critique sans signe")
        return cls(
            value_id=_required_identifier(parsed, "value_id", "NUM"),
            signed_value=signed_value,
            unit=_required_text(parsed, "unit"),
            context=_required_text(parsed, "context"),
            provenance_zone_id=_required_identifier(parsed, "provenance_zone_id", "ZONE"),
        )


@dataclass(frozen=True)
class TableCellAnnotation:
    table_id: str
    row_index: int
    column_index: int
    text: str
    provenance_zone_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TableCellAnnotation":
        parsed = _ensure_mapping(payload, "TableCellAnnotation")
        _ensure_allowed_fields(parsed, _TABLE_CELL_FIELDS, "TableCellAnnotation")
        return cls(
            table_id=_required_identifier(parsed, "table_id", "TABLE"),
            row_index=_required_positive_integer(parsed, "row_index"),
            column_index=_required_positive_integer(parsed, "column_index"),
            text=_required_text(parsed, "text"),
            provenance_zone_id=_required_identifier(parsed, "provenance_zone_id", "ZONE"),
        )


@dataclass(frozen=True)
class ReadingOrderItem:
    order_index: int
    role: str
    provenance_zone_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReadingOrderItem":
        parsed = _ensure_mapping(payload, "ReadingOrderItem")
        _ensure_allowed_fields(parsed, _READING_ORDER_FIELDS, "ReadingOrderItem")
        return cls(
            order_index=_required_positive_integer(parsed, "order_index"),
            role=_required_text(parsed, "role"),
            provenance_zone_id=_required_identifier(parsed, "provenance_zone_id", "ZONE"),
        )


@dataclass(frozen=True)
class PageAnnotation:
    annotation_id: str
    page_ref: PageReference
    annotation_version: str
    annotation_author_type: str
    generated_by_evaluated_system: bool
    expected_state: str
    expected_route: str
    reference_transcription: str | None
    empty_or_rejection_reason: str | None
    critical_numeric_values: tuple[CriticalNumericValue, ...]
    table_cells: tuple[TableCellAnnotation, ...]
    reading_order: tuple[ReadingOrderItem, ...]
    provenance_zones: tuple[ProvenanceZone, ...]

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "PageAnnotation":
        parsed = _ensure_mapping(payload, "PageAnnotation")
        _ensure_allowed_fields(parsed, _ANNOTATION_FIELDS, "PageAnnotation")
        return cls(
            annotation_id=_required_identifier(parsed, "annotation_id", "PANN"),
            page_ref=PageReference.from_payload(_ensure_mapping(_required_field(parsed, "page_ref"), "page_ref")),
            annotation_version=_required_identifier(parsed, "annotation_version", "ANN"),
            annotation_author_type=_required_text(parsed, "annotation_author_type"),
            generated_by_evaluated_system=_required_boolean(parsed, "generated_by_evaluated_system"),
            expected_state=_required_expected_state(parsed),
            expected_route=_required_expected_route(parsed),
            reference_transcription=_optional_text(parsed, "reference_transcription"),
            empty_or_rejection_reason=_optional_text(parsed, "empty_or_rejection_reason"),
            critical_numeric_values=tuple(
                CriticalNumericValue.from_payload(item) for item in _required_sequence(parsed, "critical_numeric_values")
            ),
            table_cells=tuple(
                TableCellAnnotation.from_payload(item) for item in _required_sequence(parsed, "table_cells")
            ),
            reading_order=tuple(ReadingOrderItem.from_payload(item) for item in _required_sequence(parsed, "reading_order")),
            provenance_zones=tuple(
                ProvenanceZone.from_payload(item, source_locator_validation_policy=source_locator_validation_policy)
                for item in _required_sequence(parsed, "provenance_zones")
            ),
        )


@dataclass(frozen=True)
class AnnotationSet:
    annotation_set_id: str
    corpus_id: str
    policy_version: str
    annotation_version: str
    frozen_at: str
    replaces_annotation_set_id: str | None
    historical_annotation_versions: tuple[str, ...]
    benchmark_pages: tuple[PageReference, ...]
    annotations: tuple[PageAnnotation, ...]
    frozen_annotation_sha256: str

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> "AnnotationSet":
        parsed = _ensure_mapping(payload, "AnnotationSet")
        _ensure_allowed_fields(parsed, _ANNOTATION_SET_FIELDS, "AnnotationSet")
        _ensure_frozen_annotation_set(parsed)
        if _required_text(parsed, "schema_version") != "1.0":
            raise ValueError("schema_version annotations non supportee")
        if parsed.get("frozen") is not True:
            raise ValueError("jeu annote non fige")

        return cls(
            annotation_set_id=_required_identifier(parsed, "annotation_set_id", "ASET"),
            corpus_id=_required_identifier(parsed, "corpus_id", "PCORP"),
            policy_version=_required_text(parsed, "policy_version"),
            annotation_version=_required_identifier(parsed, "annotation_version", "ANN"),
            frozen_at=_required_utc_instant(parsed, "frozen_at"),
            replaces_annotation_set_id=_optional_identifier(parsed, "replaces_annotation_set_id", "ASET"),
            historical_annotation_versions=tuple(
                _ensure_identifier_value(item, "historical_annotation_version", "ANN")
                for item in _required_sequence(parsed, "historical_annotation_versions")
            ),
            benchmark_pages=tuple(PageReference.from_payload(item) for item in _required_sequence(parsed, "benchmark_pages")),
            annotations=tuple(
                PageAnnotation.from_payload(item, source_locator_validation_policy=source_locator_validation_policy)
                for item in _required_sequence(parsed, "annotations")
            ),
            frozen_annotation_sha256=_required_sha256(parsed, "frozen_annotation_sha256"),
        )

    @property
    def annotation_count(self) -> int:
        return len(self.annotations)

    @property
    def benchmark_page_count(self) -> int:
        return len(self.benchmark_pages)


@dataclass(frozen=True)
class AnnotationCompletenessPolicy:
    policy_version: str

    def __init__(self) -> None:
        object.__setattr__(self, "policy_version", "AnnotationCompletenessPolicy-1.0")

    def validate_payload(
        self,
        payload: Mapping[str, Any],
        *,
        pilot_corpus: PilotCorpus,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> AnnotationSet:
        annotation_set = AnnotationSet.from_payload(
            payload,
            source_locator_validation_policy=source_locator_validation_policy,
        )
        self.validate(annotation_set, pilot_corpus=pilot_corpus)
        return annotation_set

    def validate(self, annotation_set: AnnotationSet, *, pilot_corpus: PilotCorpus) -> None:
        if not isinstance(annotation_set, AnnotationSet):
            raise ValueError("AnnotationSet requis")
        if not isinstance(pilot_corpus, PilotCorpus):
            raise ValueError("PilotCorpus requis")
        if annotation_set.corpus_id != pilot_corpus.corpus_id:
            raise ValueError("corpus_id incoherent avec PilotCorpus")
        if annotation_set.policy_version != self.policy_version:
            raise ValueError("policy_version annotations incoherente")
        if annotation_set.replaces_annotation_set_id is not None and len(annotation_set.historical_annotation_versions) == 0:
            raise ValueError("suppression historique sans nouvelle version")
        if annotation_set.annotation_version in annotation_set.historical_annotation_versions:
            raise ValueError("version d'annotation historique non remplacee")

        known_pages = self._known_pages(pilot_corpus, annotation_set)
        self._ensure_benchmark_pages_known(annotation_set, known_pages)
        annotations_by_page = self._annotations_by_page(annotation_set)
        self._ensure_benchmark_pages_annotated(annotation_set, annotations_by_page)

        for annotation in annotation_set.annotations:
            self._validate_annotation(annotation, known_pages)

    def _known_pages(self, pilot_corpus: PilotCorpus, annotation_set: AnnotationSet) -> set[tuple[str, str, str, int]]:
        corpus_document_refs = {
            (
                document.pilot_document_id,
                document.source_document_id,
                document.source_processing_ref["canonical_version_id"],
            )
            for document in pilot_corpus.documents
        }
        known_pages: set[tuple[str, str, str, int]] = set()
        for page_ref in annotation_set.benchmark_pages:
            document_ref = (page_ref.pilot_document_id, page_ref.source_document_id, page_ref.canonical_version_id)
            if document_ref not in corpus_document_refs:
                raise ValueError(f"page benchmark hors corpus pilote: {page_ref.pilot_document_id}")
            known_pages.add(page_ref.key)
        return known_pages

    def _ensure_benchmark_pages_known(
        self, annotation_set: AnnotationSet, known_pages: set[tuple[str, str, str, int]]
    ) -> None:
        if len(annotation_set.benchmark_pages) == 0:
            raise ValueError("pages benchmark absentes")
        if len(known_pages) != len(annotation_set.benchmark_pages):
            raise ValueError("page benchmark dupliquee")

    def _annotations_by_page(self, annotation_set: AnnotationSet) -> Mapping[tuple[str, str, str, int], PageAnnotation]:
        annotations_by_page: dict[tuple[str, str, str, int], PageAnnotation] = {}
        for annotation in annotation_set.annotations:
            page_key = annotation.page_ref.key
            if page_key in annotations_by_page:
                raise ValueError(f"annotation dupliquee: {annotation.annotation_id}")
            annotations_by_page[page_key] = annotation
        return annotations_by_page

    def _ensure_benchmark_pages_annotated(
        self,
        annotation_set: AnnotationSet,
        annotations_by_page: Mapping[tuple[str, str, str, int], PageAnnotation],
    ) -> None:
        for page_ref in annotation_set.benchmark_pages:
            if page_ref.key not in annotations_by_page:
                raise ValueError(f"annotation absente pour page benchmark: {page_ref.page_pdf}")

    def _validate_annotation(
        self, annotation: PageAnnotation, known_pages: set[tuple[str, str, str, int]]
    ) -> None:
        if annotation.page_ref.key not in known_pages:
            raise ValueError(f"annotation hors pages benchmark: {annotation.annotation_id}")
        if annotation.annotation_author_type != HUMAN_REVIEWER or annotation.generated_by_evaluated_system:
            raise ValueError("annotation generee par systeme evalue refusee")

        zone_ids = self._validate_provenance_zones(annotation)
        self._validate_state_route(annotation)
        self._validate_references_to_zones(annotation, zone_ids)

    def _validate_provenance_zones(self, annotation: PageAnnotation) -> set[str]:
        if len(annotation.provenance_zones) == 0:
            raise ValueError("zones de provenance absentes")
        zone_ids: set[str] = set()
        for zone in annotation.provenance_zones:
            if zone.provenance_zone_id in zone_ids:
                raise ValueError(f"zone de provenance dupliquee: {zone.provenance_zone_id}")
            if zone.source_locator.page_pdf != annotation.page_ref.page_pdf:
                raise ValueError("zone de provenance hors page annotee")
            if zone.source_locator.document_id != annotation.page_ref.source_document_id:
                raise ValueError("zone de provenance hors document annote")
            if zone.source_locator.canonical_version_id != annotation.page_ref.canonical_version_id:
                raise ValueError("zone de provenance hors version annotee")
            zone_ids.add(zone.provenance_zone_id)
        return zone_ids

    def _validate_state_route(self, annotation: PageAnnotation) -> None:
        if annotation.expected_state == EVALUABLE:
            if annotation.expected_route == NO_ROUTE:
                raise ValueError("conflit entre route attendue et etat attendu")
            if annotation.empty_or_rejection_reason is not None:
                raise ValueError("raison de rejet interdite sur page evaluable")
            if annotation.reference_transcription is None:
                raise ValueError("transcription de reference absente")
            if len(annotation.reading_order) == 0:
                raise ValueError("ordre de lecture absent")
            return

        if annotation.expected_route != NO_ROUTE:
            raise ValueError("conflit entre route attendue et etat attendu")
        if annotation.empty_or_rejection_reason is None:
            if annotation.expected_state == EMPTY_DECLARED:
                raise ValueError("page vide non declaree")
            raise ValueError("page rejetee non declaree")
        if annotation.reference_transcription is not None:
            raise ValueError("transcription interdite sur page non evaluable")
        if len(annotation.critical_numeric_values) > 0 or len(annotation.table_cells) > 0 or len(annotation.reading_order) > 0:
            raise ValueError("oracle de contenu interdit sur page non evaluable")

    def _validate_references_to_zones(self, annotation: PageAnnotation, zone_ids: set[str]) -> None:
        for numeric_value in annotation.critical_numeric_values:
            if numeric_value.provenance_zone_id not in zone_ids:
                raise ValueError("valeur numerique critique sans provenance resolvable")
        for table_cell in annotation.table_cells:
            if table_cell.provenance_zone_id not in zone_ids:
                raise ValueError("cellule de tableau sans provenance resolvable")
        seen_order_indexes: set[int] = set()
        for order_item in annotation.reading_order:
            if order_item.provenance_zone_id not in zone_ids:
                raise ValueError("ordre de lecture sans provenance resolvable")
            if order_item.order_index in seen_order_indexes:
                raise ValueError("ordre de lecture duplique")
            seen_order_indexes.add(order_item.order_index)


@dataclass(frozen=True)
class AnnotationSetManifestValidator:
    completeness_policy: AnnotationCompletenessPolicy

    def __init__(self) -> None:
        object.__setattr__(self, "completeness_policy", AnnotationCompletenessPolicy())

    def validate_payload(
        self,
        payload: Mapping[str, Any],
        *,
        pilot_corpus: PilotCorpus,
        source_locator_validation_policy: SourceLocatorValidationPolicy,
    ) -> AnnotationSet:
        return self.completeness_policy.validate_payload(
            payload,
            pilot_corpus=pilot_corpus,
            source_locator_validation_policy=source_locator_validation_policy,
        )


def freeze_page_annotation_set(payload: Mapping[str, Any]) -> dict[str, Any]:
    manifest = _json_ready(payload)
    if not isinstance(manifest, dict):
        raise ValueError("jeu annote non objet")
    manifest.pop("frozen_annotation_sha256", None)
    manifest["frozen_annotation_sha256"] = _stable_manifest_hash(manifest)
    return manifest


def _ensure_frozen_annotation_set(payload: Mapping[str, Any]) -> None:
    declared_hash = _required_sha256(payload, "frozen_annotation_sha256")
    actual_hash = _stable_manifest_hash(_manifest_without_hash(payload))
    if declared_hash != actual_hash:
        raise ValueError("jeu annote modifie apres gel")


def _manifest_without_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    manifest = _json_ready(payload)
    if not isinstance(manifest, dict):
        raise ValueError("jeu annote non objet")
    manifest.pop("frozen_annotation_sha256", None)
    return manifest


def _stable_manifest_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(_json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _required_expected_state(payload: Mapping[str, Any]) -> str:
    value = _required_text(payload, "expected_state")
    if value not in EXPECTED_PAGE_STATES:
        raise ValueError(f"expected_state inconnu: {value}")
    return value


def _required_expected_route(payload: Mapping[str, Any]) -> str:
    value = _required_text(payload, "expected_route")
    if value not in EXPECTED_ROUTES:
        raise ValueError(f"expected_route inconnue: {value}")
    return value


def _required_field(payload: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return payload[field_name]


def _required_identifier(payload: Mapping[str, Any], field_name: str, expected_prefix: str) -> str:
    return _ensure_identifier_value(_required_text(payload, field_name), field_name, expected_prefix)


def _optional_identifier(payload: Mapping[str, Any], field_name: str, expected_prefix: str) -> str | None:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if value is None:
        return None
    return _ensure_identifier_value(value, field_name, expected_prefix)


def _ensure_identifier_value(value: Any, field_name: str, expected_prefix: str) -> str:
    text_value = _ensure_text(value, field_name)
    if _IDENTIFIER_PATTERN.fullmatch(text_value) is None:
        raise ValueError(f"{field_name} invalide")
    if not text_value.startswith(expected_prefix + "-"):
        raise ValueError(f"{field_name} prefixe invalide")
    return text_value


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    return _ensure_text(payload[field_name], field_name)


def _optional_text(payload: Mapping[str, Any], field_name: str) -> str | None:
    if field_name not in payload:
        return None
    value = payload[field_name]
    if value is None:
        return None
    return _ensure_text(value, field_name)


def _ensure_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} non textuel")
    if value.strip() == "":
        raise ValueError(f"{field_name} vide")
    if value != value.strip():
        raise ValueError(f"{field_name} non normalise")
    return value


def _required_boolean(payload: Mapping[str, Any], field_name: str) -> bool:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} non booleen")
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


def _required_positive_integer(payload: Mapping[str, Any], field_name: str) -> int:
    if field_name not in payload:
        raise ValueError(f"{field_name} absent")
    value = payload[field_name]
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
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


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "AnnotationCompletenessPolicy",
    "AnnotationSet",
    "AnnotationSetManifestValidator",
    "CriticalNumericValue",
    "EMPTY_DECLARED",
    "EVALUABLE",
    "EXPECTED_PAGE_STATES",
    "EXPECTED_ROUTES",
    "HUMAN_REVIEWER",
    "NO_ROUTE",
    "PageAnnotation",
    "PageReference",
    "ProvenanceZone",
    "REJECTED_DECLARED",
    "ReadingOrderItem",
    "TableCellAnnotation",
    "freeze_page_annotation_set",
]
