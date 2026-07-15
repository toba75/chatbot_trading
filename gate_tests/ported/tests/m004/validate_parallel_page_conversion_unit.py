from __future__ import annotations

import hashlib
import threading
import time

from app.source_processing.application.convert_routed_pages import (
    ConvertRoutedPagesCommand,
    ConvertRoutedPagesHandler,
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
    PageRoutingConfiguration,
    ProcessingRunId,
    RoutingPolicyVersion,
)
from app.source_processing.domain.page_conversion import (
    ConversionToolName,
    PageConversionArtifact,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


def test_parallel_page_conversion_preserves_pdf_order_and_reports_completed_units() -> None:
    # Given un PDF route sur quatre pages natives lentes.
    source_document = _registered_source()
    processing_run = _planned_native_run(source_document, page_count=4)
    native_converter = _BlockingNativeConverter()
    completed_pages: list[int] = []
    handler = ConvertRoutedPagesHandler(
        native_converter=native_converter,
        granite_converter=_UnusedConverter(),
        ocrmypdf_preprocessor=_UnusedPreprocessor(),
        max_parallel_pages=4,
    )

    result_holder: dict[str, object] = {}

    def run_conversion() -> None:
        try:
            result_holder["result"] = handler.handle(
                ConvertRoutedPagesCommand(
                    source_document=source_document,
                    processing_run=processing_run,
                    canonical_version_id="CVER-M004-PARALLEL",
                ),
                on_page_converted=lambda output: completed_pages.append(output.page_number.value),
            )
        except BaseException as exc:  # pragma: no cover - relayed to the test thread
            result_holder["error"] = exc

    worker_thread = threading.Thread(target=run_conversion)
    worker_thread.start()
    started_count = native_converter.wait_until_started(expected=4, timeout_seconds=1.5)
    native_converter.release()
    worker_thread.join(timeout=5)

    if worker_thread.is_alive():
        raise AssertionError("La conversion parallèle ne s'est pas terminée.")
    if "error" in result_holder:
        raise result_holder["error"]  # type: ignore[misc]

    # When les pages sont libérées ensemble.
    # Then les quatre conversions ont bien été actives en parallèle.
    assert started_count == 4
    assert native_converter.max_active >= 4

    result = result_holder["result"]
    assert tuple(output.page_number.value for output in result.page_outputs) == (1, 2, 3, 4)  # type: ignore[attr-defined]
    assert tuple(page.page_number.value for page in result.docling_document.pages) == (1, 2, 3, 4)  # type: ignore[attr-defined]
    assert sorted(completed_pages) == [1, 2, 3, 4]


class _BlockingNativeConverter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._release = threading.Event()
        self.started_pages: list[int] = []
        self.active = 0
        self.max_active = 0

    def convert_page(self, request) -> PageConversionArtifact:
        with self._lock:
            self.started_pages.append(request.page_number.value)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if not self._release.wait(timeout=3):
                raise RuntimeError("PAGE_CONVERSION_PARALLEL_RELEASE_TIMEOUT")
            return _page_output(request)
        finally:
            with self._lock:
                self.active -= 1

    def wait_until_started(self, *, expected: int, timeout_seconds: float) -> int:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            with self._lock:
                count = len(self.started_pages)
            if count >= expected:
                return count
            time.sleep(0.01)
        with self._lock:
            return len(self.started_pages)

    def release(self) -> None:
        self._release.set()


class _UnusedConverter:
    def convert_page(self, request):
        raise AssertionError(f"Convertisseur non attendu: {request!r}")


class _UnusedPreprocessor:
    def preprocess_page(self, request):
        raise AssertionError(f"Préprocesseur non attendu: {request!r}")


def _registered_source() -> SourceDocument:
    content = b"%PDF-1.7\nparallel conversion\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=OriginalStorageRef.from_value(
            f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
        ),
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Conversion parallèle",
                "authors": ["OSTrading"],
                "publication_year": 2026,
                "edition": "1",
            }
        ),
    )


def _planned_native_run(source_document: SourceDocument, *, page_count: int) -> DocumentProcessingRun:
    manifest = PageManifest.from_entries(
        source_page_count=page_count,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(number),
                state=PageManifestEntryState.PRESENT,
            )
            for number in range(1, page_count + 1)
        ),
    )
    run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-PARALLEL"),
        source_document=source_document,
        page_manifest=manifest,
    )
    diagnosed = run.record_page_diagnostics(
        tuple(_native_decision(number) for number in range(1, page_count + 1))
    )
    return diagnosed.decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )


def _native_decision(number: int) -> PageDecision:
    return PageDecision(
        page_number=PageNumber.from_value(number),
        page_state=PageDecisionState.NATIVE_OK,
        signals=PageDiagnosticSignals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
        justification=f"Page native fiable {number}.",
    )


def _page_output(request) -> PageConversionArtifact:
    text = f"Page {request.page_number.value} convertie."
    return PageConversionArtifact(
        page_number=request.page_number,
        route_name=request.route_name,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-standard-test",
        artifact_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        audit_artifact_ref=request.expected_output_artifact_ref,
        items=(
            PageConversionItem(
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
            ),
        ),
    )
