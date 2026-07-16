from __future__ import annotations

import hashlib
from pathlib import Path
import sys


def test_validate_empty_page_conversion_acceptance() -> None:
    repository_root = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "pyproject.toml").is_file()
    )
    sys.path.insert(0, str(repository_root))

    from app.source_processing.application.convert_routed_pages import (
        ConvertRoutedPagesCommand,
        ConvertRoutedPagesHandler,
    )
    from app.source_processing.domain.document_processing_run import (
        DiagnosticVersion,
        DocumentProcessingRun,
        NativeTextSignal,
        PageDiagnosticSignals,
        PageImageSignal,
        PageManifest,
        PageManifestEntry,
        PageManifestEntryState,
        PageNumber,
        PageRoutingConfiguration,
        ProcessingRunId,
        RoutingPolicyVersion,
    )
    from app.source_processing.domain.page_conversion import (
        CanonicalAcceptancePolicy,
        ConversionToolName,
        PageConversionArtifact,
        PageConversionItem,
        PageConversionItemLabel,
        PageItemGeometry,
        QualityDecisionStatus,
    )
    from app.source_processing.application.routed_document_conversion_worker import (
        _authority_manifest,
        _pre_conversion_report,
    )
    from app.source_processing.domain.source_document import (
        DocumentId,
        OriginalStorageRef,
        SourceDocument,
        SourceFingerprint,
    )

    class NativeConverter:
        def __init__(self) -> None:
            self.pages: list[int] = []

        def convert_page(self, request):
            self.pages.append(request.page_number.value)
            text = f"Contenu page {request.page_number.value}"
            return PageConversionArtifact(
                page_number=request.page_number,
                route_name=request.route_name,
                tool_name=ConversionToolName.DOCLING_STANDARD,
                tool_version="docling-test-v1",
                artifact_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                audit_artifact_ref=request.expected_output_artifact_ref,
                items=(
                    PageConversionItem(
                        label=PageConversionItemLabel.TEXT,
                        text=text,
                        geometry=PageItemGeometry(
                            left=0,
                            top=0,
                            right=100,
                            bottom=20,
                            page_width=100,
                            page_height=100,
                        ),
                        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    ),
                ),
            )

    class ForbiddenGranite:
        def convert_page(self, request):
            raise AssertionError(f"Granite ne doit pas recevoir la page {request.page_number.value}")

    class ForbiddenPreprocessor:
        def preprocess_page(self, request):
            raise AssertionError(f"OCRmyPDF ne doit pas recevoir la page {request.page_number.value}")

    fingerprint = SourceFingerprint.from_content(b"%PDF-1.7\nthree-pages\n%%EOF")
    document_id = DocumentId.from_fingerprint(fingerprint)
    source = SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=None,
    )
    manifest = PageManifest.from_entries(
        source_page_count=3,
        entries=(
            PageManifestEntry(PageNumber.from_value(1), PageManifestEntryState.PRESENT),
            PageManifestEntry(PageNumber.from_value(2), PageManifestEntryState.EMPTY),
            PageManifestEntry(PageNumber.from_value(3), PageManifestEntryState.PRESENT),
        ),
    )

    def diagnostic(page_number: int, *, empty: bool):
        from app.source_processing.domain.document_processing_run import PageDecision

        return PageDecision(
            page_number=PageNumber.from_value(page_number),
            page_state="EMPTY" if empty else "NATIVE_OK",
            signals=PageDiagnosticSignals(
                native_text_state=NativeTextSignal.ABSENT if empty else NativeTextSignal.RELIABLE,
                image_state=PageImageSignal.NONE,
                existing_ocr_state="NONE",
                layout_complexity="SIMPLE",
                corruption_state="NONE",
                mixed_content_detected=False,
                has_table=False,
                has_formula=False,
            ),
            diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
            justification=f"Page {page_number} {'vide' if empty else 'native'}.",
        )

    routed = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-EMPTY-SKIP"),
        source_document=source,
        page_manifest=manifest,
    ).record_page_diagnostics(
        (diagnostic(1, empty=False), diagnostic(2, empty=True), diagnostic(3, empty=False))
    ).decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )
    native = NativeConverter()
    result = ConvertRoutedPagesHandler(
        native_converter=native,
        granite_converter=ForbiddenGranite(),
        ocrmypdf_preprocessor=ForbiddenPreprocessor(),
        max_parallel_pages=3,
    ).handle(
        ConvertRoutedPagesCommand(
            source_document=source,
            processing_run=routed,
            canonical_version_id="CVER-M004-EMPTY-SKIP",
        )
    )

    assert native.pages == [1, 3]
    assert tuple(page.value for page in result.skipped_page_numbers) == (2,)
    assert tuple(page.page_number.value for page in result.docling_document.pages) == (1, 3)
    assert tuple(output.page_number.value for output in result.page_outputs) == (1, 3)

    # Given la page 2 est diagnostiquée EMPTY et explicitement ignorée par SKIP_EMPTY.
    authority_manifest = _authority_manifest(
        processing_run=routed,
        page_outputs=result.page_outputs,
    )
    acceptance_policy = CanonicalAcceptancePolicy(
        policy_version="m004-routed-docling-v1"
    )

    # When la QA post-conversion contrôle le document canonique sans page 2.
    post_report = acceptance_policy.evaluate_post_conversion(
        page_manifest=routed.page_manifest,
        text_authority_manifest=authority_manifest,
        docling_document=result.docling_document,
        findings=(),
    )
    quality_decision = acceptance_policy.decide(
        source_document=source,
        page_manifest=routed.page_manifest,
        text_authority_manifest=authority_manifest,
        pre_conversion_report=_pre_conversion_report(
            processing_run=routed,
            policy_version=acceptance_policy.policy_version,
        ),
        post_conversion_report=post_report,
    )

    # Then la page vide n'est pas une omission et la publication reste autorisée.
    assert post_report.status is QualityDecisionStatus.PASS
    assert post_report.findings == ()
    assert quality_decision.publication_allowed is True
