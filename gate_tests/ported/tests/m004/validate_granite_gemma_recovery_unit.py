"""Contrat unitaire de récupération Gemma après un échec Granite autorisé."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.source_processing.application.convert_routed_pages import (
    ConvertRoutedPagesCommand,
    ConvertRoutedPagesHandler,
    PageConversionRequest,
)
from app.source_processing.application.granite_gemma_recovery import (
    GraniteConversionFailure,
    GraniteThenGemmaPageConverter,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    PageDecision,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRouteName,
    PageRoutingConfiguration,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PageConversionFallbackTrace,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


def _request() -> PageConversionRequest:
    return PageConversionRequest(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-GEMMA-UNIT"),
        document_id=DocumentId.from_value("DOC-0000000000000001"),
        page_number=PageNumber.from_value(1),
        route_name=PageRouteName.SCAN_GRANITE,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        source_artifact_ref=(
            "artifact:source_processing.original_sources/"
            "DOC-0000000000000001/original.pdf"
        ),
        expected_output_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            "RUN-M004-GEMMA-UNIT/page-001-scan_granite.json"
        ),
    )


def _item(text: str) -> PageConversionItem:
    return PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text=text,
        geometry=PageItemGeometry(
            left=0.1,
            top=0.1,
            right=0.9,
            bottom=0.2,
            page_width=1.0,
            page_height=1.0,
        ),
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _gemma_output(
    request: PageConversionRequest,
    *,
    granite_error_code: str,
) -> PageConversionArtifact:
    text = "Trading on Momentum"
    return PageConversionArtifact(
        page_number=request.page_number,
        route_name=request.route_name,
        tool_name=ConversionToolName.GEMMA_VISION,
        tool_version="google/gemma-4-26B-A4B-it@immutable;nim-1.7.0",
        artifact_hash="a" * 64,
        audit_artifact_ref=request.expected_output_artifact_ref,
        fallback_trace=PageConversionFallbackTrace(
            triggering_tool_name=ConversionToolName.GRANITE_DOCLING,
            triggering_error_code=granite_error_code,
        ),
        items=(_item(text),),
    )


class _GraniteWithoutProvenance:
    def __init__(self, code: str) -> None:
        self.code = code
        self.requests: list[PageConversionRequest] = []

    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        self.requests.append(request)
        raise GraniteConversionFailure(self.code)


class _GemmaAfterGranite:
    def __init__(self) -> None:
        self.calls: list[tuple[PageConversionRequest, str]] = []

    def recover_page(
        self,
        request: PageConversionRequest,
        *,
        granite_error_code: str,
    ) -> PageConversionArtifact:
        self.calls.append((request, granite_error_code))
        return _gemma_output(request, granite_error_code=granite_error_code)


class _Native:
    def convert_page(self, request: PageConversionRequest) -> PageConversionArtifact:
        raise AssertionError("La route Granite ne doit pas appeler Docling standard.")


class _NoOcr:
    def preprocess_page(self, request: object) -> object:
        raise AssertionError("SCAN_GRANITE ne doit pas appeler OCRmyPDF.")


def _source_and_run() -> tuple[SourceDocument, DocumentProcessingRun]:
    content = b"%PDF-1.7\nGemma recovery\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Récupération Gemma explicite",
                "authors": ["OSTrading"],
                "publication_year": 2026,
                "edition": "1re édition",
            }
        ),
    )
    manifest = PageManifest.from_entries(
        source_page_count=1,
        entries=(
            PageManifestEntry(
                page_number=PageNumber.from_value(1),
                state=PageManifestEntryState.PRESENT,
            ),
        ),
    )
    run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-GEMMA-HANDLER"),
        source_document=source,
        page_manifest=manifest,
    ).record_page_diagnostics(
        (
            PageDecision(
                page_number=PageNumber.from_value(1),
                page_state=PageDecisionState.SCAN_CLEAN,
                signals=PageDiagnosticSignals(
                    native_text_state="ABSENT",
                    image_state="SCAN_CLEAN",
                    existing_ocr_state="NONE",
                    layout_complexity="SIMPLE",
                    corruption_state="NONE",
                    mixed_content_detected=False,
                    has_table=False,
                    has_formula=False,
                ),
                diagnostic_version=DiagnosticVersion.from_value("diag-gemma-v1"),
                justification="Scan sans texte natif.",
            ),
        )
    ).decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-gemma-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )
    return source, run


def _verifier_recuperation_granite_autorisee(granite_error_code: str) -> None:
    # Given Granite a réellement reçu une page SCAN_GRANITE et retourne un échec terminal autorisé.
    # When la récupération explicitement décidée par ADR-036 est exécutée.
    # Then Gemma 4 est appelée une seule fois, le motif Granite est persisté et Gemma devient l'autorité unique.
    granite = _GraniteWithoutProvenance(granite_error_code)
    gemma = _GemmaAfterGranite()
    converter = GraniteThenGemmaPageConverter(
        granite_converter=granite,
        gemma_converter=gemma,
    )
    request = _request()

    recovered = converter.convert_page(request)

    assert granite.requests == [request]
    assert gemma.calls == [(request, granite_error_code)]
    assert recovered.tool_name is ConversionToolName.GEMMA_VISION
    assert recovered.fallback_trace == PageConversionFallbackTrace(
        triggering_tool_name=ConversionToolName.GRANITE_DOCLING,
        triggering_error_code=granite_error_code,
    )
    source, run = _source_and_run()
    handler = ConvertRoutedPagesHandler(
        native_converter=_Native(),
        granite_converter=converter,
        ocrmypdf_preprocessor=_NoOcr(),
    )
    result = handler.handle(
        ConvertRoutedPagesCommand(
            source_document=source,
            processing_run=run,
            canonical_version_id="CVER-M004-GEMMA-RECOVERY",
        )
    )
    payload = result.docling_document.to_payload()
    assert payload["pages"][0]["conversion_tool_name"] == "GEMMA_VISION"
    assert payload["pages"][0]["fallback_trace"] == {
        "triggering_tool_name": "GRANITE_DOCLING",
        "triggering_error_code": granite_error_code,
    }


def _verifier_absence_de_recuperation_sur_echec_hors_contrat() -> None:
    # Given Granite échoue avec un code qui ne fait pas partie de l'ADR-036.
    # When la conversion de page est demandée.
    # Then Gemma ne reçoit aucun appel et l'échec Granite reste terminal.
    granite = _GraniteWithoutProvenance("SOURCE_FINGERPRINT_MISMATCH")
    gemma = _GemmaAfterGranite()
    converter = GraniteThenGemmaPageConverter(
        granite_converter=granite,
        gemma_converter=gemma,
    )

    with pytest.raises(GraniteConversionFailure, match="SOURCE_FINGERPRINT_MISMATCH"):
        converter.convert_page(_request())

    assert gemma.calls == []


def _verifier_trace_gemma_obligatoire() -> None:
    # Given une sortie déclarée GEMMA_VISION sans la trace Granite obligatoire.
    # When le domaine valide l'artefact pagewise.
    # Then l'artefact est refusé et ne peut pas atteindre le canonique.
    request = _request()
    with pytest.raises(ValueError, match="trace de récupération Gemma obligatoire"):
        PageConversionArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.GEMMA_VISION,
            tool_version="google/gemma-4-26B-A4B-it@immutable;nim-1.7.0",
            artifact_hash="b" * 64,
            audit_artifact_ref=request.expected_output_artifact_ref,
            fallback_trace=None,
            items=(_item("Texte non traçable"),),
        )


def _verifier_adaptateur_gemma_apres_indisponibilite_granite(tmp_path: Path) -> None:
    # Given Granite a échoué après son essai réel avec GRANITE_DOCLING_UNAVAILABLE.
    # When l'adaptateur Gemma concret reçoit la récupération autorisée par ADR-036.
    # Then il appelle le port Gemma, conserve le code Granite et produit l'autorité Gemma.
    from app.source_processing.adapters.gemma_vision_conversion import (
        GemmaVisionConversionResponse,
        GemmaVisionPageItem,
    )
    from app.source_processing.application.routed_document_conversion_worker import (
        _GemmaVisionFallbackPageConverter,
    )

    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.7\nGemma concrete recovery\n%%EOF\n")
    request = _request()

    class _ConcreteGemmaPort:
        def __init__(self) -> None:
            self.requests = []

        def convert(self, gemma_request):
            self.requests.append(gemma_request)
            return GemmaVisionConversionResponse(
                tool_version="google/gemma-4-26B-A4B-it@immutable;nim-1.7.0",
                items=(
                    GemmaVisionPageItem(
                        text="Texte récupéré",
                        bbox=(0.0, 0.0, 1000.0, 1000.0),
                    ),
                ),
            )

    gemma_port = _ConcreteGemmaPort()
    converter = _GemmaVisionFallbackPageConverter(
        converter=gemma_port,
        resolve_source_path=lambda artifact_ref: source_path,
        gateway_endpoint_url="http://llm-gateway.local/v1/infer",
        gateway_timeout_seconds=120,
        gateway_max_output_tokens=2048,
        expected_model_id="google/gemma-4-26B-A4B-it",
    )

    recovered = converter.recover_page(
        request,
        granite_error_code="GRANITE_DOCLING_UNAVAILABLE",
    )

    assert len(gemma_port.requests) == 1
    assert gemma_port.requests[0].max_output_tokens == 2048
    assert recovered.tool_name is ConversionToolName.GEMMA_VISION
    assert recovered.fallback_trace == PageConversionFallbackTrace(
        triggering_tool_name=ConversionToolName.GRANITE_DOCLING,
        triggering_error_code="GRANITE_DOCLING_UNAVAILABLE",
    )


def _verifier_contrat_gemma_compact_pour_table_dense() -> None:
    # Given une page non native contient un tableau dense et lisible.
    # When Gemma prépare sa sortie canonique après Granite.
    # Then il regroupe explicitement les cellules en régions TSV bornées,
    #      sans tronquer la réponse ni omettre silencieusement la table.
    from app.source_processing.adapters.gemma_vision_worker import (
        _PAGE_TRANSCRIPTION_PROMPT,
        _output_schema,
    )

    schema = _output_schema()
    assert schema["properties"]["items"]["maxItems"] == 16
    assert "tableau dense" in _PAGE_TRANSCRIPTION_PROMPT
    assert "TSV" in _PAGE_TRANSCRIPTION_PROMPT
    assert "N’omets aucun texte lisible" in _PAGE_TRANSCRIPTION_PROMPT


def test_recuperation_gemma_explicite_apres_absence_de_provenance_granite(tmp_path: Path) -> None:
    """Exécute un unique scénario atomique, conformément au manifeste de gate."""
    _verifier_recuperation_granite_autorisee("DOCLING_PROVENANCE_MISSING")
    _verifier_recuperation_granite_autorisee("GRANITE_DOCLING_UNAVAILABLE")
    _verifier_absence_de_recuperation_sur_echec_hors_contrat()
    _verifier_trace_gemma_obligatoire()
    _verifier_adaptateur_gemma_apres_indisponibilite_granite(tmp_path)
    _verifier_contrat_gemma_compact_pour_table_dense()
