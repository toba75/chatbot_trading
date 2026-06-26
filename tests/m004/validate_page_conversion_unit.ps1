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
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
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


def registered_source(suffix="UNIT"):
    original_content = f"%PDF-1.7\nsource {suffix}\n%%EOF\n".encode("utf-8")
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
                "title": f"Conversion unitaire {suffix}",
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


def native_signals():
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


def scan_clean_signals():
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


def scan_degraded_signals():
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


def decision(page_number, page_state, signals):
    return PageDecision(
        page_number=PageNumber.from_value(page_number),
        page_state=page_state,
        signals=signals,
        diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
        justification=f"Diagnostic explicite page {page_number}.",
    )


def planned_run(source_document):
    started_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M004-T003-UNIT"),
        source_document=source_document,
        page_manifest=manifest_for(3),
    )
    diagnosed_run = started_run.record_page_diagnostics(
        (
            decision(1, PageDecisionState.NATIVE_OK, native_signals()),
            decision(2, PageDecisionState.SCAN_CLEAN, scan_clean_signals()),
            decision(3, PageDecisionState.SCAN_DEGRADED, scan_degraded_signals()),
        )
    )
    return diagnosed_run.decide_route_plan(
        PageRoutingConfiguration(
            routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
            auto_confidence_min=0.90,
            benchmark_confidence_min=0.85,
        )
    )


def geometry(left=10, top=20, right=90, bottom=70, width=100, height=200):
    return PageItemGeometry(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        page_width=width,
        page_height=height,
    )


def conversion_item(label=PageConversionItemLabel.TEXT, text="Texte contrôlé.", content_hash="1" * 64):
    return PageConversionItem(
        label=label,
        text=text,
        geometry=geometry(),
        content_hash=content_hash,
    )


def artifact(page_number, route_name, tool_name, content_hash="1" * 64):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=route_name,
        tool_name=tool_name,
        tool_version=f"{tool_name.value.lower()}-v1",
        artifact_hash=str(page_number) * 64,
        audit_artifact_ref=f"artifact:source_processing.page_conversion/RUN-M004-T003-UNIT/page-{page_number:03d}.json",
        items=(
            conversion_item(
                label=PageConversionItemLabel.TABLE if page_number == 2 else PageConversionItemLabel.TEXT,
                text=f"Contenu page {page_number}.",
                content_hash=content_hash,
            ),
        ),
    )


def merge_outputs(source_document, page_outputs):
    return PagewiseDoclingFusionService().merge(
        document_id=source_document.document_id,
        canonical_version_id="CVER-M004-T003",
        source_sha256=source_document.fingerprint,
        original_storage_ref=source_document.original_storage_ref,
        page_manifest=manifest_for(3),
        page_outputs=page_outputs,
    )


# Les objets-valeur refusent les sorties partiellement valides.
assert_equal(geometry().normalized_bbox(), (0.1, 0.1, 0.9, 0.35), "Les coordonnées doivent être normalisées.")
assert_raises(
    "page invalides",
    lambda: PageItemGeometry(left=90, top=20, right=10, bottom=70, page_width=100, page_height=200),
)
assert_raises(
    "content_hash vide",
    lambda: PageConversionItem(
        label=PageConversionItemLabel.TEXT,
        text="Texte sans provenance.",
        geometry=geometry(),
        content_hash="",
    ),
)
assert_raises(
    "version d'outil invalide",
    lambda: PageConversionArtifact(
        page_number=PageNumber.from_value(1),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="",
        artifact_hash="a" * 64,
        audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-UNIT/page-001.json",
        items=(conversion_item(),),
    ),
)
assert_raises(
    "hash d'artefact invalide",
    lambda: PageConversionArtifact(
        page_number=PageNumber.from_value(1),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-standard-v1",
        artifact_hash="",
        audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-UNIT/page-001.json",
        items=(conversion_item(),),
    ),
)
assert_raises(
    "items de conversion vides",
    lambda: PageConversionArtifact(
        page_number=PageNumber.from_value(1),
        route_name=PageRouteName.NATIVE_STANDARD,
        tool_name=ConversionToolName.DOCLING_STANDARD,
        tool_version="docling-standard-v1",
        artifact_hash="a" * 64,
        audit_artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-UNIT/page-001.json",
        items=(),
    ),
)
assert_raises(
    "hash d'artefact invalide",
    lambda: PreprocessedPageArtifact(
        page_number=PageNumber.from_value(3),
        route_name=PageRouteName.PREPROCESS_GRANITE,
        tool_name=ConversionToolName.OCRMYPDF,
        tool_version="ocrmypdf-v1",
        artifact_hash="",
        artifact_ref="artifact:source_processing.page_conversion/RUN-M004-T003-UNIT/page-003-preprocessed.pdf",
    ),
)

# La fusion pagewise refuse les pages manquantes, le désordre et les routes incohérentes.
source_document = registered_source()
native_output = artifact(1, PageRouteName.NATIVE_STANDARD, ConversionToolName.DOCLING_STANDARD)
granite_output = artifact(2, PageRouteName.SCAN_GRANITE, ConversionToolName.GRANITE_DOCLING, content_hash="2" * 64)
preprocess_output = artifact(3, PageRouteName.PREPROCESS_GRANITE, ConversionToolName.GRANITE_DOCLING, content_hash="3" * 64)

docling_document = merge_outputs(source_document, (native_output, granite_output, preprocess_output))
assert_equal(tuple(page.page_number.value for page in docling_document.pages), (1, 2, 3), "La fusion doit conserver l'ordre PDF.")
assert_equal(
    tuple(item.item_id for page in docling_document.pages for item in page.items),
    (
        f"{source_document.document_id.value}-P001-I001",
        f"{source_document.document_id.value}-P002-I001",
        f"{source_document.document_id.value}-P003-I001",
    ),
    "Les item_id doivent être canoniques et uniques.",
)
assert_equal(docling_document.pages[1].items[0].label, "TABLE", "Les labels de table doivent être conservés.")
assert_equal(docling_document.pages[0].items[0].provenance.bbox, (0.1, 0.1, 0.9, 0.35), "La provenance doit porter les coordonnées normalisées.")
assert_equal(docling_document.to_payload()["pages"][0]["items"][0]["provenance"]["item_id"], f"{source_document.document_id.value}-P001-I001", "La sérialisation doit conserver la provenance.")

assert_raises(
    "ordre strict des pages invalide",
    lambda: merge_outputs(source_document, (granite_output, native_output, preprocess_output)),
)
assert_raises(
    "page de conversion manquante",
    lambda: merge_outputs(source_document, (native_output, granite_output)),
)


class StaticNativeConverter:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.requests = []

    def convert_page(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise RuntimeError(self.error)
        return self.output


class StaticGraniteConverter:
    def __init__(self):
        self.requests = []

    def convert_page(self, request):
        self.requests.append(request)
        if request.page_number.value == 2:
            return artifact(2, PageRouteName.SCAN_GRANITE, ConversionToolName.GRANITE_DOCLING, content_hash="2" * 64)
        return artifact(3, PageRouteName.PREPROCESS_GRANITE, ConversionToolName.GRANITE_DOCLING, content_hash="3" * 64)


class StaticOcrPreprocessor:
    def __init__(self):
        self.requests = []

    def preprocess_page(self, request):
        self.requests.append(request)
        return PreprocessedPageArtifact(
            page_number=request.page_number,
            route_name=request.route_name,
            tool_name=ConversionToolName.OCRMYPDF,
            tool_version="ocrmypdf-v1",
            artifact_hash="d" * 64,
            artifact_ref=request.expected_output_artifact_ref,
        )


processing_run = planned_run(source_document)
native_converter = StaticNativeConverter(output=native_output)
granite_converter = StaticGraniteConverter()
ocr_preprocessor = StaticOcrPreprocessor()
handler = ConvertRoutedPagesHandler(
    native_converter=native_converter,
    granite_converter=granite_converter,
    ocrmypdf_preprocessor=ocr_preprocessor,
)
result = handler.handle(
    ConvertRoutedPagesCommand(
        source_document=source_document,
        processing_run=processing_run,
        canonical_version_id="CVER-M004-T003",
    )
)
assert_equal(tuple(request.page_number.value for request in native_converter.requests), (1,), "La route native doit utiliser uniquement le port natif.")
assert_equal(tuple(request.page_number.value for request in granite_converter.requests), (2, 3), "Les routes Granite doivent utiliser uniquement le port Granite.")
assert_equal(tuple(request.page_number.value for request in ocr_preprocessor.requests), (3,), "OCRmyPDF doit rester conditionnel.")
assert_equal(result.preprocessed_artifacts[0].artifact_ref, granite_converter.requests[1].source_artifact_ref, "Le prétraitement doit être transmis explicitement à Granite.")

wrong_tool_native = StaticNativeConverter(
    output=artifact(1, PageRouteName.NATIVE_STANDARD, ConversionToolName.GRANITE_DOCLING)
)
assert_raises(
    "outil de conversion",
    lambda: ConvertRoutedPagesHandler(
        native_converter=wrong_tool_native,
        granite_converter=StaticGraniteConverter(),
        ocrmypdf_preprocessor=StaticOcrPreprocessor(),
    ).handle(
        ConvertRoutedPagesCommand(
            source_document=source_document,
            processing_run=processing_run,
            canonical_version_id="CVER-M004-T003",
        )
    ),
)

failing_native = StaticNativeConverter(error="Docling standard indisponible")
fallback_granite = StaticGraniteConverter()
assert_raises(
    "Docling standard indisponible",
    lambda: ConvertRoutedPagesHandler(
        native_converter=failing_native,
        granite_converter=fallback_granite,
        ocrmypdf_preprocessor=StaticOcrPreprocessor(),
    ).handle(
        ConvertRoutedPagesCommand(
            source_document=source_document,
            processing_run=processing_run,
            canonical_version_id="CVER-M004-T003",
        )
    ),
)
assert_equal(fallback_granite.requests, [], "Un échec Docling ne doit pas déclencher Granite silencieusement.")

other_source = registered_source("OTHER")
assert_raises(
    "document_id",
    lambda: handler.handle(
        ConvertRoutedPagesCommand(
            source_document=other_source,
            processing_run=processing_run,
            canonical_version_id="CVER-M004-T003",
        )
    ),
)
assert_raises(
    "canonical_version_id invalide",
    lambda: ConvertRoutedPagesCommand(
        source_document=source_document,
        processing_run=processing_run,
        canonical_version_id="version-sans-prefixe",
    ),
)

print("Tests unitaires T-003 conversion pagewise M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_page_conversion_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-003 conversion pagewise M-004: OK"
