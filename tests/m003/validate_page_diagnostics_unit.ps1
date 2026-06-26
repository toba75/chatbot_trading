$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageDecision,
    PageDecisionState,
    PageDiagnosticPolicy,
    PageDiagnosticSignals,
    PageDiagnosticRecorded,
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
                "title": "Diagnostic documentaire",
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


def created_run():
    source_document = registered_source()
    return DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M003-T005-UNIT"),
        source_document=source_document,
        page_manifest=manifest_for(3),
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


def decision_for(page_number, page_signals, justification="Justification diagnostique explicite."):
    return PageDiagnosticPolicy().classify(
        page_number=PageNumber.from_value(page_number),
        signals=page_signals,
        diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
        justification=justification,
    )


def assert_classification(page_signals, expected_state, message):
    page_decision = decision_for(1, page_signals)
    assert_equal(page_decision.page_state, expected_state, message)
    assert_equal(page_decision.diagnostic_version.value, "diag-v1", "La version de diagnostic doit être conservée.")
    assert_equal(page_decision.signals, page_signals, "Les signaux techniques doivent être conservés.")


# La politique classe uniquement les états publiés par la spécification M-003.
assert_classification(
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
    PageDecisionState.NATIVE_OK,
    "Un texte natif fiable doit produire NATIVE_OK.",
)
assert_classification(
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
    PageDecisionState.NATIVE_SUSPECT,
    "Un texte natif suspect doit produire NATIVE_SUSPECT.",
)
assert_classification(
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
    PageDecisionState.SCAN_CLEAN,
    "Un scan propre doit produire SCAN_CLEAN.",
)
assert_classification(
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
    PageDecisionState.SCAN_DEGRADED,
    "Un scan dégradé doit produire SCAN_DEGRADED.",
)
assert_classification(
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
    PageDecisionState.OCR_BAD,
    "Une couche OCR défectueuse doit produire OCR_BAD.",
)
assert_classification(
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
    PageDecisionState.MIXED_CONTENT,
    "Un contenu mixte doit produire MIXED_CONTENT.",
)
assert_classification(
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
    PageDecisionState.COMPLEX_VISUAL,
    "Une page visuelle complexe doit produire COMPLEX_VISUAL.",
)
assert_classification(
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
    PageDecisionState.UNSUPPORTED_OR_CORRUPT,
    "Une page corrompue doit produire UNSUPPORTED_OR_CORRUPT.",
)

# Aucun état ou signal inconnu ne peut être accepté silencieusement.
assert_raises("version de diagnostic invalide", lambda: DiagnosticVersion.from_value(""))
assert_raises("diagnostic inconnu", lambda: PageDecisionState.from_value("UNKNOWN"))
assert_raises(
    "diagnostic inconnu",
    lambda: PageDecision(
        page_number=PageNumber.from_value(1),
        page_state="UNKNOWN",
        signals=signals(
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
        justification="Justification explicite.",
    ),
)
assert_raises(
    "signaux diagnostiques insuffisants",
    lambda: decision_for(
        1,
        signals(
            native_text_state="ABSENT",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        ),
    ),
)
assert_raises(
    "justification de diagnostic invalide",
    lambda: PageDiagnosticPolicy().classify(
        page_number=PageNumber.from_value(1),
        signals=signals(
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
        justification="",
    ),
)

# Le run refuse tout diagnostic non exhaustif, dupliqué ou hors manifeste.
run = created_run()
page_1 = decision_for(
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
)
page_2 = decision_for(
    2,
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
)
page_3 = decision_for(
    3,
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
    justification="Page corrompue explicitement diagnostiquée.",
)
page_4 = decision_for(
    4,
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
)

assert_raises("diagnostic de page manquant", lambda: run.record_page_diagnostics((page_1, page_2)))
assert_raises("diagnostic de page dupliqu", lambda: run.record_page_diagnostics((page_1, page_1, page_2)))
assert_raises("diagnostic hors manifeste", lambda: run.record_page_diagnostics((page_1, page_2, page_4)))

diagnosed_run = run.record_page_diagnostics((page_1, page_2, page_3))
assert_equal(diagnosed_run.status, DocumentProcessingRunStatus.DIAGNOSED, "Le run complet doit passer à DIAGNOSED.")
assert_equal(diagnosed_run.page_decisions, (page_1, page_2, page_3), "Les décisions de pages doivent être conservées.")
assert_equal(len(diagnosed_run.events), 4, "Un événement de diagnostic doit être enregistré par page.")
assert_true(
    all(isinstance(event, PageDiagnosticRecorded) for event in diagnosed_run.events[1:]),
    "Les événements de diagnostic doivent être typés PageDiagnosticRecorded.",
)
assert_equal(
    tuple(event.page_state for event in diagnosed_run.events[1:]),
    (PageDecisionState.NATIVE_OK, PageDecisionState.SCAN_CLEAN, PageDecisionState.UNSUPPORTED_OR_CORRUPT),
    "Les événements doivent conserver les états diagnostiqués.",
)

# Une tentative déjà diagnostiquée ne peut pas recevoir un second diagnostic par mutation logique.
assert_raises("transition de diagnostic interdite", lambda: diagnosed_run.record_page_diagnostics((page_1, page_2, page_3)))

print("Tests unitaires T-005 diagnostic page par page: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_page_diagnostics_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires T-005 diagnostic page par page: OK"
