$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.application.record_page_diagnostics import (
    PageDiagnosticInput,
    RecordPageDiagnosticsCommand,
    RecordPageDiagnosticsHandler,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    ProcessingRunId,
)
from app.source_processing.domain.source_document import (
    BibliographicMetadata,
    DocumentId,
    OriginalStorageRef,
    SourceDocument,
    SourceFingerprint,
)


class InMemoryProcessingRunRepository:
    def __init__(self):
        self.saved_runs = []

    def save(self, processing_run):
        self.saved_runs.append(processing_run)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def registered_source():
    original_content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 8 >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
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
                "title": "Source mixte pour diagnostic",
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


def signals(
    *,
    native_text_state,
    image_state,
    existing_ocr_state,
    layout_complexity,
    corruption_state,
    mixed_content_detected,
    has_table,
    has_formula,
):
    return PageDiagnosticSignals(
        native_text_state=native_text_state,
        image_state=image_state,
        existing_ocr_state=existing_ocr_state,
        layout_complexity=layout_complexity,
        corruption_state=corruption_state,
        mixed_content_detected=mixed_content_detected,
        has_table=has_table,
        has_formula=has_formula,
    )


def diagnostic(page_number, page_signals, justification):
    return PageDiagnosticInput(
        page_number=page_number,
        signals=page_signals,
        diagnostic_version="diag-v1",
        justification=justification,
    )


source_document = registered_source()
processing_run = DocumentProcessingRun.start(
    processing_run_id=ProcessingRunId.from_value("RUN-M003-T005-DIAGNOSTIC"),
    source_document=source_document,
    page_manifest=manifest_for(8),
)
repository = InMemoryProcessingRunRepository()
handler = RecordPageDiagnosticsHandler(processing_run_repository=repository)

all_diagnostics = (
    diagnostic(
        1,
        signals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        "Texte natif fiable et page simple.",
    ),
    diagnostic(
        2,
        signals(
            native_text_state="SUSPECT",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        "Texte natif présent mais qualité suspecte.",
    ),
    diagnostic(
        3,
        signals(
            native_text_state="ABSENT",
            image_state="SCAN_CLEAN",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        "Page scannée propre sans couche textuelle fiable.",
    ),
    diagnostic(
        4,
        signals(
            native_text_state="ABSENT",
            image_state="SCAN_DEGRADED",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        "Page scannée dégradée par rotation et contraste insuffisant.",
    ),
    diagnostic(
        5,
        signals(
            native_text_state="ABSENT",
            image_state="NONE",
            existing_ocr_state="BAD",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        "Couche OCR existante incohérente.",
    ),
    diagnostic(
        6,
        signals(
            native_text_state="RELIABLE",
            image_state="SCAN_CLEAN",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=True,
            has_table=True,
            has_formula=False,
        ),
        "Contenu mixte avec texte natif et zone scannée.",
    ),
    diagnostic(
        7,
        signals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="COMPLEX",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=True,
            has_formula=True,
        ),
        "Page visuelle complexe avec tableau et formule.",
    ),
    diagnostic(
        8,
        signals(
            native_text_state="ABSENT",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="CORRUPT",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
        "Page corrompue illisible.",
    ),
)

# Given un manifeste complet contient des pages natives, scannées et corrompues.
# When un diagnostic de page manque.
# Then la tentative refuse le diagnostic incomplet sans persister de route implicite.
assert_raises(
    "diagnostic de page manquant",
    lambda: handler.handle(
        RecordPageDiagnosticsCommand(
            processing_run=processing_run,
            diagnostics=all_diagnostics[:-1],
        )
    ),
)
assert_equal(len(repository.saved_runs), 0, "Un diagnostic incomplet ne doit pas être persisté.")

# Given le même manifeste complet.
# When les diagnostics de pages sont enregistrés.
diagnosed_run = handler.handle(
    RecordPageDiagnosticsCommand(
        processing_run=processing_run,
        diagnostics=all_diagnostics,
    )
)

# Then chaque page reçoit un état diagnostique explicite, justifié et versionné.
assert_equal(diagnosed_run.status, DocumentProcessingRunStatus.DIAGNOSED, "La tentative doit passer à DIAGNOSED.")
assert_equal(len(diagnosed_run.page_decisions), 8, "Chaque page du manifeste doit recevoir un PageDecision.")
decisions_by_page = {
    page_decision.page_number.value: page_decision
    for page_decision in diagnosed_run.page_decisions
}
assert_equal(
    tuple(decisions_by_page[page].page_state for page in range(1, 9)),
    (
        PageDecisionState.NATIVE_OK,
        PageDecisionState.NATIVE_SUSPECT,
        PageDecisionState.SCAN_CLEAN,
        PageDecisionState.SCAN_DEGRADED,
        PageDecisionState.OCR_BAD,
        PageDecisionState.MIXED_CONTENT,
        PageDecisionState.COMPLEX_VISUAL,
        PageDecisionState.UNSUPPORTED_OR_CORRUPT,
    ),
    "Les états diagnostiques publiés par M-003 doivent être conservés.",
)
assert_equal(
    tuple(page_decision.diagnostic_version.value for page_decision in diagnosed_run.page_decisions),
    ("diag-v1",) * 8,
    "La version de diagnostic doit être conservée pour chaque PageDecision.",
)
assert_equal(
    decisions_by_page[8].justification,
    "Page corrompue illisible.",
    "La page corrompue doit conserver sa justification explicite.",
)
assert_true(
    decisions_by_page[8].page_state == PageDecisionState.UNSUPPORTED_OR_CORRUPT,
    "Une page corrompue ne doit pas être classée comme native ou scannée par défaut.",
)
assert_equal(repository.saved_runs, [diagnosed_run], "Le run diagnostiqué doit être persisté une seule fois.")

print("Test d'acceptation T-005 diagnostic page par page: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_page_diagnostics_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-005 diagnostic page par page: OK"
