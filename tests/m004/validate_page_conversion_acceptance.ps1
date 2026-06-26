$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.application.convert_routed_pages import (
    ConvertRoutedPagesCommand,
    ConvertRoutedPagesHandler,
)
from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
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
    PreprocessedPageArtifact,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except (RuntimeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def registered_source():
    original_content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 3 >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    fingerprint = SourceFingerprint.from_content(original_content)
    document_id = DocumentId.from_fingerprint(fingerprint)
    storage_ref = OriginalStorageRef.from_value(
        f"artifact:source_processing.original_sources/{document_id.value}/{fingerprint.value}.pdf"
    )
    return SourceDocument.register_original(
        document_id=document_id,
        fingerprint=fingerprint,
        original_storage_ref=storage_ref,
        metadata=BibliographicMetadata.from_payload(
            {
                "title": "Conversion documentaire M-004",
                "authors": ["Perry J. Kaufman"],
                "publication_year": 2020,
                "edition": "1re édition",
            }
        ),
    )


def manifest_for(page_count):
    return PageManifest.from_entries(
        source_page_count=page_count,
        entries=tuple(
            PageManifestEntry(
                page_number=PageNumber.from_value(page_number),
                state=PageManifestEntryState.PRESENT,
            )
            for page_number in range(1, page_count + 1)
        ),
    )


def signals_for(page_state):
    if page_state is PageDecisionState.NATIVE_OK:
        return PageDiagnosticSignals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )
    if page_state is PageDecisionState.SCAN_CLEAN:
        return PageDiagnosticSignals(
            native_text_state="ABSENT",
            image_state="SCAN_CLEAN",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=True,
            has_formula=False,
        )
    if page_state is PageDecisionState.SCAN_DEGRADED:
        return PageDiagnosticSignals(
            native_text_state="ABSENT",
            image_state="SCAN_DEGRADED",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=True,
        )
    raise AssertionError(f"État non prévu par ce test: {page_state!r}")


def decision(page_number, page_state):
    return PageDecision(
        page_number=PageNumber.from_value(page_number),
        page_state=page_state,
        signals=signals_for(page_state),
        diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
        justification=f"Diagnostic explicite {page_state.value}.",
    )


def planned_run(source_document):
    started_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T003-ACCEPTANCE"),
        source_document=source_document,
        page_manifest=manifest_for(3),
    )
    diagnosed_run = started_run.record_page_diagnostics(
        (
            decision(1, PageDecisionState.NATIVE_OK),
            decision(2, PageDecisionState.SCAN_CLEAN),
            decision(3, PageDecisionState.SCAN_DEGRADED),
        )
    )
    return diagnosed_run.decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )


def diagnosed_run(source_document):
    started_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T003-DIAGNOSED"),
        source_document=source_document,
        page_manifest=manifest_for(1),
    )
    return started_run.record_page_diagnostics((decision(1, PageDecisionState.NATIVE_OK),))


def item(label, text, left, top, right, bottom, content_hash):
    return PageConversionItem(
        label=label,
        text=text,
        geometry=PageItemGeometry(
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            page_width=1000,
            page_height=1000,
        ),
        content_hash=content_hash,
    )


class NativeDoclingConverter:
    def __init__(self):
        self.requests = []

    def convert_page(self, request):
        self.requests.append(request)
        return PageConversionArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.DOCLING_STANDARD,
            tool_version="docling-standard-2.0.0",
            artifact_hash="a" * 64,
            audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-ACCEPTANCE/page-001-native.json",
            items=(
                item(
                    PageConversionItemLabel.TEXT,
                    "Texte natif fiable.",
                    100,
                    100,
                    900,
                    180,
                    "1" * 64,
                ),
            ),
        )


class GraniteDoclingConverter:
    def __init__(self):
        self.requests = []

    def convert_page(self, request):
        self.requests.append(request)
        if request.page_number.value == 2:
            return PageConversionArtifact(
                page_number=request.page_number,
                route_name=request.route_name,
                tool_name=ConversionToolName.GRANITE_DOCLING,
                tool_version="granite-docling-258m-1.0.0",
                artifact_hash="b" * 64,
                audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-ACCEPTANCE/page-002-granite.json",
                items=(
                    item(
                        PageConversionItemLabel.TABLE,
                        "Tableau de performance.",
                        50,
                        220,
                        950,
                        620,
                        "2" * 64,
                    ),
                ),
            )

        return PageConversionArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.GRANITE_DOCLING,
            tool_version="granite-docling-258m-1.0.0",
            artifact_hash="c" * 64,
            audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-ACCEPTANCE/page-003-granite.json",
            items=(
                item(
                    PageConversionItemLabel.FIGURE,
                    "Figure issue du scan prétraité.",
                    150,
                    300,
                    850,
                    900,
                    "3" * 64,
                ),
            ),
        )


class OcrMyPdfPreprocessor:
    def __init__(self):
        self.requests = []

    def preprocess_page(self, request):
        self.requests.append(request)
        return PreprocessedPageArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.OCRMYPDF,
            tool_version="ocrmypdf-16.0.0",
            artifact_hash="d" * 64,
            artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-ACCEPTANCE/page-003-preprocessed.pdf",
        )


source_document = registered_source()
processing_run = planned_run(source_document)
native_converter = NativeDoclingConverter()
granite_converter = GraniteDoclingConverter()
ocr_preprocessor = OcrMyPdfPreprocessor()
handler = ConvertRoutedPagesHandler(
    native_converter=native_converter,
    granite_converter=granite_converter,
    ocrmypdf_preprocessor=ocr_preprocessor,
)
original_storage_ref_before = source_document.original_storage_ref.value

# Given un DocumentProcessingRun M-003 avec un RoutePlan approuvé pour toutes les pages.
# When la conversion documentaire M-004 est demandée.
result = handler.handle(
    ConvertRoutedPagesCommand(
        source_document=source_document,
        processing_run=processing_run,
        canonical_version_id="CVER-M004-T003",
    )
)

# Then chaque page est convertie uniquement par sa route explicite, puis fusionnée dans un DoclingDocument unique.
assert_equal(processing_run.status, DocumentProcessingRunStatus.ROUTE_PLANNED, "La précondition métier doit rester ROUTE_PLANNED.")
assert_equal(tuple(request.page_number.value for request in native_converter.requests), (1,), "La route native ne doit appeler que Docling standard.")
assert_equal(tuple(request.page_number.value for request in granite_converter.requests), (2, 3), "Granite doit traiter uniquement les routes Granite explicites.")
assert_equal(tuple(request.page_number.value for request in ocr_preprocessor.requests), (3,), "OCRmyPDF doit être appelé seulement sur PREPROCESS_GRANITE.")
assert_equal(granite_converter.requests[1].source_artifact_ref, ocr_preprocessor.requests[0].expected_output_artifact_ref, "Granite doit consommer l'artefact OCRmyPDF explicitement produit.")
assert_equal(source_document.original_storage_ref.value, original_storage_ref_before, "L'original ne doit pas être modifié.")

assert_equal(tuple(output.page_number.value for output in result.page_outputs), (1, 2, 3), "Les sorties pagewise doivent suivre l'ordre PDF.")
assert_true(all(output.route_name == route.route_name for output, route in zip(result.page_outputs, processing_run.route_plan.page_routes)), "Chaque sortie doit conserver sa route.")
assert_true(all(output.tool_version for output in result.page_outputs), "Chaque sortie doit conserver la version d'outil.")
assert_true(all(len(output.artifact_hash) == 64 for output in result.page_outputs), "Chaque sortie doit conserver un hash d'artefact.")

docling_document = result.docling_document
assert_equal(docling_document.document_id.value, source_document.document_id.value, "Le document fusionné doit conserver le document_id.")
assert_equal(docling_document.original_storage_ref.value, source_document.original_storage_ref.value, "Le document fusionné doit référencer l'original immuable.")
assert_equal(tuple(page.page_number.value for page in docling_document.pages), (1, 2, 3), "Le DoclingDocument unique doit conserver l'ordre strict des pages.")

canonical_items = tuple(item for page in docling_document.pages for item in page.items)
assert_equal(len(canonical_items), 3, "Chaque page doit produire un item canonique dans ce scénario.")
assert_equal(len({canonical_item.item_id for canonical_item in canonical_items}), 3, "Les item_id canoniques doivent être uniques.")
assert_equal(
    tuple(canonical_item.item_id for canonical_item in canonical_items),
    (
        f"{source_document.document_id.value}-P001-I001",
        f"{source_document.document_id.value}-P002-I001",
        f"{source_document.document_id.value}-P003-I001",
    ),
    "Les item_id canoniques doivent être déterministes par document, page et ordre.",
)
assert_equal(tuple(item.label for item in canonical_items), ("TEXT", "TABLE", "FIGURE"), "Les labels, tables et figures doivent être conservés.")
assert_equal(canonical_items[0].bbox, (0.1, 0.1, 0.9, 0.18), "Les coordonnées doivent être normalisées.")
assert_true(all(item.provenance.item_id == item.item_id for item in canonical_items), "Chaque item doit porter sa provenance.")
assert_true(all(item.provenance.document_id == source_document.document_id.value for item in canonical_items), "Chaque provenance doit pointer le document source.")
assert_true(all(item.provenance.canonical_version_id == "CVER-M004-T003" for item in canonical_items), "Chaque provenance doit pointer la version candidate.")
assert_true(all(item.provenance.content_hash == item.content_hash for item in canonical_items), "Chaque provenance doit conserver le hash de contenu.")

assert_raises(
    "tentative M-003 non publiable",
    lambda: handler.handle(
        ConvertRoutedPagesCommand(
            source_document=source_document,
            processing_run=diagnosed_run(source_document),
            canonical_version_id="CVER-M004-T003",
        )
    ),
)
assert_raises(
    "source documentaire non publiable",
    lambda: handler.handle(
        ConvertRoutedPagesCommand(
            source_document=source_document.quarantine("Quarantaine explicite avant conversion."),
            processing_run=processing_run,
            canonical_version_id="CVER-M004-T003",
        )
    ),
)


class MissingProvenanceNativeConverter(NativeDoclingConverter):
    def convert_page(self, request):
        self.requests.append(request)
        return PageConversionArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.DOCLING_STANDARD,
            tool_version="docling-standard-2.0.0",
            artifact_hash="e" * 64,
            audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-ACCEPTANCE/page-001-native.json",
            items=(
                item(
                    PageConversionItemLabel.TEXT,
                    "Item sans hash de contenu.",
                    100,
                    100,
                    900,
                    180,
                    "",
                ),
            ),
        )


assert_raises(
    "content_hash vide",
    lambda: ConvertRoutedPagesHandler(
        native_converter=MissingProvenanceNativeConverter(),
        granite_converter=GraniteDoclingConverter(),
        ocrmypdf_preprocessor=OcrMyPdfPreprocessor(),
    ).handle(
        ConvertRoutedPagesCommand(
            source_document=source_document,
            processing_run=processing_run,
            canonical_version_id="CVER-M004-T003",
        )
    ),
)

print("Test d'acceptation T-003 conversion pagewise M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_page_conversion_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $env:PYTHONIOENCODING = "utf-8"
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation T-003 conversion pagewise M-004: OK"
