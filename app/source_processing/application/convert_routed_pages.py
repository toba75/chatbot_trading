"""Cas d'usage M-004 de conversion selon RoutePlan explicite."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.contracts.identity import DomainIdentifier
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    PageNumber,
    PageRoute,
    PageRouteName,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PagewiseDoclingDocument,
    PagewiseDoclingFusionService,
    PreprocessedPageArtifact,
)
from app.source_processing.domain.source_document import DocumentId, SourceDocument


_GRANITE_ROUTE_NAMES = frozenset(
    {
        PageRouteName.SCAN_GRANITE,
        PageRouteName.BAD_OCR_TO_GRANITE,
        PageRouteName.MIXED_PAGEWISE,
        PageRouteName.TARGETED_ENRICHMENT,
    }
)


class PageConverter(Protocol):
    """Port mince vers un outil de conversion de page."""

    def convert_page(self, request: "PageConversionRequest") -> PageConversionArtifact:
        """Convertit une page avec l'artefact source explicitement fourni."""


class PagePreprocessor(Protocol):
    """Port mince vers OCRmyPDF conditionnel."""

    def preprocess_page(
        self,
        request: "PagePreprocessingRequest",
    ) -> PreprocessedPageArtifact:
        """Produit un artefact prétraité sans modifier l'original."""


@dataclass(frozen=True)
class PageConversionRequest:
    """Requête applicative transmise à un convertisseur de page."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_number: PageNumber
    route_name: PageRouteName
    routing_policy_version: RoutingPolicyVersion
    source_artifact_ref: str
    expected_output_artifact_ref: str

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "route_name", PageRouteName.from_value(self.route_name))
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(
            self,
            "source_artifact_ref",
            _ensure_artifact_ref(self.source_artifact_ref),
        )
        object.__setattr__(
            self,
            "expected_output_artifact_ref",
            _ensure_artifact_ref(self.expected_output_artifact_ref),
        )


@dataclass(frozen=True)
class PagePreprocessingRequest:
    """Requête applicative transmise au préprocesseur OCRmyPDF."""

    processing_run_id: ProcessingRunId
    document_id: DocumentId
    page_number: PageNumber
    route_name: PageRouteName
    routing_policy_version: RoutingPolicyVersion
    source_artifact_ref: str
    expected_output_artifact_ref: str

    def __post_init__(self) -> None:
        _ensure_processing_run_id(self.processing_run_id)
        _ensure_document_id(self.document_id)
        _ensure_page_number(self.page_number)
        object.__setattr__(self, "route_name", PageRouteName.from_value(self.route_name))
        _ensure_routing_policy_version(self.routing_policy_version)
        object.__setattr__(
            self,
            "source_artifact_ref",
            _ensure_artifact_ref(self.source_artifact_ref),
        )
        object.__setattr__(
            self,
            "expected_output_artifact_ref",
            _ensure_artifact_ref(self.expected_output_artifact_ref),
        )


@dataclass(frozen=True)
class ConvertRoutedPagesCommand:
    """Commande M-004 de conversion d'une tentative M-003 routée."""

    source_document: SourceDocument
    processing_run: DocumentProcessingRun
    canonical_version_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_document, SourceDocument):
            raise ValueError("source_document invalide")
        if not isinstance(self.processing_run, DocumentProcessingRun):
            raise ValueError("processing_run invalide")
        object.__setattr__(
            self,
            "canonical_version_id",
            _ensure_canonical_version_id(self.canonical_version_id),
        )


@dataclass(frozen=True)
class DocumentConversionResult:
    """Résultat pagewise et document fusionné de T-003."""

    page_outputs: tuple[PageConversionArtifact, ...]
    preprocessed_artifacts: tuple[PreprocessedPageArtifact, ...]
    docling_document: PagewiseDoclingDocument

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_outputs", _ensure_page_outputs(self.page_outputs))
        object.__setattr__(
            self,
            "preprocessed_artifacts",
            _ensure_preprocessed_artifacts(self.preprocessed_artifacts),
        )
        if not isinstance(self.docling_document, PagewiseDoclingDocument):
            raise ValueError("DoclingDocument fusionné invalide")


class ConvertRoutedPagesHandler:
    """Orchestre les ports selon la route déjà décidée par M-003."""

    def __init__(
        self,
        *,
        native_converter: PageConverter,
        granite_converter: PageConverter,
        ocrmypdf_preprocessor: PagePreprocessor,
    ) -> None:
        if not callable(getattr(native_converter, "convert_page", None)):
            raise ValueError("native_converter invalide")
        if not callable(getattr(granite_converter, "convert_page", None)):
            raise ValueError("granite_converter invalide")
        if not callable(getattr(ocrmypdf_preprocessor, "preprocess_page", None)):
            raise ValueError("ocrmypdf_preprocessor invalide")
        self._native_converter = native_converter
        self._granite_converter = granite_converter
        self._ocrmypdf_preprocessor = ocrmypdf_preprocessor

    def handle(self, command: ConvertRoutedPagesCommand) -> DocumentConversionResult:
        if not isinstance(command, ConvertRoutedPagesCommand):
            raise ValueError("commande ConvertRoutedPages invalide")

        command.source_document.ensure_documentary_publication_allowed()
        if command.source_document.document_id != command.processing_run.document_id:
            raise ValueError("document_id incohérent")
        command.processing_run.ensure_documentary_publication_allowed()
        route_plan = command.processing_run.route_plan
        if route_plan is None:
            raise ValueError("plan de routage absent")

        page_outputs: list[PageConversionArtifact] = []
        preprocessed_artifacts: list[PreprocessedPageArtifact] = []
        for page_route in route_plan.page_routes:
            conversion_result = self._convert_page_route(
                source_document=command.source_document,
                processing_run=command.processing_run,
                page_route=page_route,
            )
            page_outputs.append(conversion_result.page_output)
            if conversion_result.preprocessed_artifact is not None:
                preprocessed_artifacts.append(conversion_result.preprocessed_artifact)

        docling_document = PagewiseDoclingFusionService().merge(
            document_id=command.source_document.document_id,
            canonical_version_id=command.canonical_version_id,
            source_sha256=command.source_document.fingerprint,
            original_storage_ref=command.source_document.original_storage_ref,
            page_manifest=command.processing_run.page_manifest,
            page_outputs=tuple(page_outputs),
        )
        return DocumentConversionResult(
            page_outputs=tuple(page_outputs),
            preprocessed_artifacts=tuple(preprocessed_artifacts),
            docling_document=docling_document,
        )

    def _convert_page_route(
        self,
        *,
        source_document: SourceDocument,
        processing_run: DocumentProcessingRun,
        page_route: PageRoute,
    ) -> "_PageConversionOrchestrationResult":
        if not isinstance(page_route, PageRoute):
            raise ValueError("route de page invalide")

        if page_route.route_name is PageRouteName.NATIVE_STANDARD:
            request = _conversion_request(
                source_document=source_document,
                processing_run=processing_run,
                page_route=page_route,
                source_artifact_ref=source_document.original_storage_ref.value,
            )
            page_output = self._native_converter.convert_page(request)
            _ensure_conversion_output(
                page_output=page_output,
                page_route=page_route,
                expected_tool_name=ConversionToolName.DOCLING_STANDARD,
                expected_artifact_ref=request.expected_output_artifact_ref,
            )
            return _PageConversionOrchestrationResult(
                page_output=page_output,
                preprocessed_artifact=None,
            )

        if page_route.route_name is PageRouteName.PREPROCESS_GRANITE:
            preprocessing_request = _preprocessing_request(
                source_document=source_document,
                processing_run=processing_run,
                page_route=page_route,
            )
            preprocessed_artifact = self._ocrmypdf_preprocessor.preprocess_page(
                preprocessing_request
            )
            _ensure_preprocessed_artifact_for_route(
                preprocessed_artifact=preprocessed_artifact,
                page_route=page_route,
                expected_artifact_ref=preprocessing_request.expected_output_artifact_ref,
            )
            request = _conversion_request(
                source_document=source_document,
                processing_run=processing_run,
                page_route=page_route,
                source_artifact_ref=preprocessed_artifact.artifact_ref,
            )
            page_output = self._granite_converter.convert_page(request)
            _ensure_conversion_output(
                page_output=page_output,
                page_route=page_route,
                expected_tool_name=ConversionToolName.GRANITE_DOCLING,
                expected_artifact_ref=request.expected_output_artifact_ref,
            )
            return _PageConversionOrchestrationResult(
                page_output=page_output,
                preprocessed_artifact=preprocessed_artifact,
            )

        if page_route.route_name in _GRANITE_ROUTE_NAMES:
            request = _conversion_request(
                source_document=source_document,
                processing_run=processing_run,
                page_route=page_route,
                source_artifact_ref=source_document.original_storage_ref.value,
            )
            page_output = self._granite_converter.convert_page(request)
            _ensure_conversion_output(
                page_output=page_output,
                page_route=page_route,
                expected_tool_name=ConversionToolName.GRANITE_DOCLING,
                expected_artifact_ref=request.expected_output_artifact_ref,
            )
            return _PageConversionOrchestrationResult(
                page_output=page_output,
                preprocessed_artifact=None,
            )

        raise ValueError(f"route de conversion non supportée: {page_route.route_name.value}")


@dataclass(frozen=True)
class _PageConversionOrchestrationResult:
    page_output: PageConversionArtifact
    preprocessed_artifact: PreprocessedPageArtifact | None

    def __post_init__(self) -> None:
        if not isinstance(self.page_output, PageConversionArtifact):
            raise ValueError("sortie de conversion invalide")
        if self.preprocessed_artifact is not None and not isinstance(
            self.preprocessed_artifact,
            PreprocessedPageArtifact,
        ):
            raise ValueError("artefact de prétraitement invalide")


def _conversion_request(
    *,
    source_document: SourceDocument,
    processing_run: DocumentProcessingRun,
    page_route: PageRoute,
    source_artifact_ref: str,
) -> PageConversionRequest:
    return PageConversionRequest(
        processing_run_id=processing_run.processing_run_id,
        document_id=processing_run.document_id,
        page_number=page_route.page_number,
        route_name=page_route.route_name,
        routing_policy_version=page_route.routing_policy_version,
        source_artifact_ref=source_artifact_ref,
        expected_output_artifact_ref=_conversion_output_artifact_ref(
            processing_run_id=processing_run.processing_run_id,
            page_number=page_route.page_number,
            route_name=page_route.route_name,
        ),
    )


def _preprocessing_request(
    *,
    source_document: SourceDocument,
    processing_run: DocumentProcessingRun,
    page_route: PageRoute,
) -> PagePreprocessingRequest:
    return PagePreprocessingRequest(
        processing_run_id=processing_run.processing_run_id,
        document_id=source_document.document_id,
        page_number=page_route.page_number,
        route_name=page_route.route_name,
        routing_policy_version=page_route.routing_policy_version,
        source_artifact_ref=source_document.original_storage_ref.value,
        expected_output_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"{processing_run.processing_run_id.value}/"
            f"page-{page_route.page_number.value:03d}-preprocessed.pdf"
        ),
    )


def _conversion_output_artifact_ref(
    *,
    processing_run_id: ProcessingRunId,
    page_number: PageNumber,
    route_name: PageRouteName,
) -> str:
    return (
        "artifact:source_processing.page_conversion/"
        f"{processing_run_id.value}/"
        f"page-{page_number.value:03d}-{route_name.value.lower()}.json"
    )


def _ensure_conversion_output(
    *,
    page_output: PageConversionArtifact,
    page_route: PageRoute,
    expected_tool_name: ConversionToolName,
    expected_artifact_ref: str,
) -> PageConversionArtifact:
    if not isinstance(page_output, PageConversionArtifact):
        raise ValueError("sortie de conversion invalide")
    if page_output.page_number != page_route.page_number:
        raise ValueError("page de conversion incohérente")
    if page_output.route_name != page_route.route_name:
        raise ValueError("route de conversion incohérente")
    if page_output.tool_name is not expected_tool_name:
        raise ValueError("outil de conversion incohérent")
    if page_output.audit_artifact_ref != expected_artifact_ref:
        raise ValueError("artefact de conversion incohérent")
    return page_output


def _ensure_preprocessed_artifact_for_route(
    *,
    preprocessed_artifact: PreprocessedPageArtifact,
    page_route: PageRoute,
    expected_artifact_ref: str,
) -> PreprocessedPageArtifact:
    if not isinstance(preprocessed_artifact, PreprocessedPageArtifact):
        raise ValueError("artefact de prétraitement invalide")
    if preprocessed_artifact.page_number != page_route.page_number:
        raise ValueError("page de prétraitement incohérente")
    if preprocessed_artifact.route_name is not page_route.route_name:
        raise ValueError("route de prétraitement incohérente")
    if preprocessed_artifact.tool_name is not ConversionToolName.OCRMYPDF:
        raise ValueError("outil de prétraitement incohérent")
    if preprocessed_artifact.artifact_ref != expected_artifact_ref:
        raise ValueError("artefact de prétraitement incohérent")
    return preprocessed_artifact


def _ensure_canonical_version_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("canonical_version_id invalide")
    try:
        return str(DomainIdentifier.parse_with_prefix(value, "CVER"))
    except ValueError as exc:
        raise ValueError(f"canonical_version_id invalide: {exc}") from exc


def _ensure_artifact_ref(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("référence d'artefact invalide")
    if value.strip() == "":
        raise ValueError("référence d'artefact invalide")
    if value != value.strip():
        raise ValueError("référence d'artefact invalide")
    if not value.startswith("artifact:source_processing."):
        raise ValueError("référence d'artefact invalide")
    return value


def _ensure_page_outputs(
    value: Sequence[PageConversionArtifact],
) -> tuple[PageConversionArtifact, ...]:
    if value is None:
        raise ValueError("sorties de conversion absentes")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("sorties de conversion invalides")
    outputs = tuple(value)
    if len(outputs) == 0:
        raise ValueError("sorties de conversion vides")
    for output in outputs:
        if not isinstance(output, PageConversionArtifact):
            raise ValueError("sortie de conversion invalide")
    return outputs


def _ensure_preprocessed_artifacts(
    value: Sequence[PreprocessedPageArtifact],
) -> tuple[PreprocessedPageArtifact, ...]:
    if value is None:
        raise ValueError("artefacts de prétraitement absents")
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("artefacts de prétraitement invalides")
    artifacts = tuple(value)
    for artifact in artifacts:
        if not isinstance(artifact, PreprocessedPageArtifact):
            raise ValueError("artefact de prétraitement invalide")
    return artifacts


def _ensure_processing_run_id(value: ProcessingRunId) -> ProcessingRunId:
    if not isinstance(value, ProcessingRunId):
        raise ValueError("processing_run_id invalide")
    return value


def _ensure_document_id(value: DocumentId) -> DocumentId:
    if not isinstance(value, DocumentId):
        raise ValueError("document_id invalide")
    return value


def _ensure_page_number(value: PageNumber) -> PageNumber:
    if not isinstance(value, PageNumber):
        raise ValueError("page_number invalide")
    return value


def _ensure_routing_policy_version(
    value: RoutingPolicyVersion,
) -> RoutingPolicyVersion:
    if not isinstance(value, RoutingPolicyVersion):
        raise ValueError("version de politique de routage invalide")
    return value


__all__ = [
    "ConvertRoutedPagesCommand",
    "ConvertRoutedPagesHandler",
    "DocumentConversionResult",
    "PageConversionRequest",
    "PageConverter",
    "PagePreprocessingRequest",
    "PagePreprocessor",
]
