$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.application.approve_route_plan import (
    ApproveRoutePlanCommand,
    ApproveRoutePlanHandler,
)
from app.source_processing.application.quarantine_processing_run import (
    QuarantineProcessingRunCommand,
    QuarantineProcessingRunHandler,
)
from app.source_processing.application.record_page_diagnostics import (
    PageDiagnosticInput,
    RecordPageDiagnosticsCommand,
    RecordPageDiagnosticsHandler,
)
from app.source_processing.application.reject_processing_run import (
    RejectProcessingRunCommand,
    RejectProcessingRunHandler,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PageRoutingConfiguration,
    ProcessingRunId,
    ProcessingRunQuarantined,
    ProcessingRunRejected,
    RoutingPolicyVersion,
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


class InMemorySourceDocumentRepository:
    def __init__(self):
        self.saved_sources = []

    def save(self, source_document):
        self.saved_sources.append(source_document)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_is_none(value, message):
    if value is not None:
        raise AssertionError(f"{message} Valeur obtenue: {value!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def registered_source():
    original_content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
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
                "title": "Source bloquée en revue ou quarantaine",
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


def route_configuration():
    return PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        auto_confidence_min=0.90,
        benchmark_confidence_min=0.85,
    )


def started_run(processing_run_id, source_document):
    return DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value(processing_run_id),
        source_document=source_document,
        page_manifest=manifest_for(2),
    )


def diagnosed_run(processing_run_id, source_document, diagnostics):
    processing_run = started_run(processing_run_id, source_document)
    diagnostics_repository = InMemoryProcessingRunRepository()
    diagnostics_handler = RecordPageDiagnosticsHandler(
        processing_run_repository=diagnostics_repository
    )
    return diagnostics_handler.handle(
        RecordPageDiagnosticsCommand(
            processing_run=processing_run,
            diagnostics=diagnostics,
        )
    )


corrupt_diagnostics = (
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
        "Page native fiable.",
    ),
    diagnostic(
        2,
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
        "Page corrompue sans route documentaire admissible.",
    ),
)


source_document = registered_source()

# Given une tentative contient une page corrompue.
diagnosed_uncertain_run = diagnosed_run(
    "RUN-M003-T007-MANUAL",
    source_document,
    corrupt_diagnostics,
)
manual_repository = InMemoryProcessingRunRepository()
manual_handler = ApproveRoutePlanHandler(processing_run_repository=manual_repository)

# When le traitement tente de poursuivre vers une route prête pour conversion.
manual_run = manual_handler.handle(
    ApproveRoutePlanCommand(
        processing_run=diagnosed_uncertain_run,
        routing_configuration=route_configuration(),
    )
)

# Then la tentative passe en revue manuelle avec justification et reste non publiable.
assert_equal(manual_run.status, DocumentProcessingRunStatus.MANUAL_REVIEW, "La page corrompue doit bloquer la route automatique.")
assert_true("page 2" in manual_run.blocking_reason, "La revue manuelle doit conserver la page bloquante.")
assert_equal(manual_run.blocking_policy_version.value, "routing-v1", "La version de politique bloquante doit être conservée.")
assert_is_none(manual_run.route_plan, "Une tentative en revue ne doit pas porter de plan publiable.")
assert_raises(
    "tentative M-003 non publiable: MANUAL_REVIEW",
    manual_run.ensure_documentary_publication_allowed,
)

# Given la revue confirme que la source doit être isolée.
quarantine_repository = InMemoryProcessingRunRepository()
quarantine_source_repository = InMemorySourceDocumentRepository()
quarantine_handler = QuarantineProcessingRunHandler(
    processing_run_repository=quarantine_repository,
    source_document_repository=quarantine_source_repository,
)
quarantine_reason = "Page 2 corrompue confirmée par contrôle humain."

# When la commande QuarantineProcessingRun est exécutée.
quarantined_run = quarantine_handler.handle(
    QuarantineProcessingRunCommand(
        processing_run=manual_run,
        source_document=source_document,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        reason=quarantine_reason,
    )
)

# Then la quarantaine conserve la justification, bloque la publication et empêche la poursuite.
assert_equal(quarantined_run.status, DocumentProcessingRunStatus.QUARANTINED, "La tentative doit passer en QUARANTINED.")
assert_equal(quarantined_run.blocking_reason, quarantine_reason, "La quarantaine doit conserver sa justification.")
assert_equal(quarantined_run.blocking_policy_version.value, "routing-v1", "La quarantaine doit conserver la version de politique.")
assert_true(isinstance(quarantined_run.events[-1], ProcessingRunQuarantined), "La quarantaine doit produire un événement explicite.")
assert_equal(quarantine_repository.saved_runs, [quarantined_run], "La quarantaine doit être persistée une seule fois.")
assert_equal(len(quarantine_source_repository.saved_sources), 1, "La source quarantinée doit être persistée une seule fois.")
quarantined_source = quarantine_source_repository.saved_sources[0]
assert_equal(quarantined_source.document_id, source_document.document_id, "La quarantaine source conserve le DocumentId.")
assert_raises(
    "source documentaire non publiable: QUARANTINED",
    quarantined_source.ensure_documentary_publication_allowed,
)
assert_raises(
    "tentative M-003 non publiable: QUARANTINED",
    quarantined_run.ensure_documentary_publication_allowed,
)
assert_raises("transition de routage interdite", lambda: quarantined_run.decide_route_plan(route_configuration()))

# Given une revue manuelle conclut que la tentative est rejetée.
diagnosed_rejected_candidate = diagnosed_run(
    "RUN-M003-T007-REJECT",
    source_document,
    corrupt_diagnostics,
)
manual_rejected_candidate = manual_handler.handle(
    ApproveRoutePlanCommand(
        processing_run=diagnosed_rejected_candidate,
        routing_configuration=route_configuration(),
    )
)
reject_repository = InMemoryProcessingRunRepository()
reject_handler = RejectProcessingRunHandler(processing_run_repository=reject_repository)
reject_reason = "Route insuffisamment justifiée après revue manuelle."

# When la commande RejectProcessingRun est exécutée.
rejected_run = reject_handler.handle(
    RejectProcessingRunCommand(
        processing_run=manual_rejected_candidate,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        reason=reject_reason,
    )
)

# Then le rejet est finalisé, non publiable et ne peut pas être rouvert.
assert_equal(rejected_run.status, DocumentProcessingRunStatus.REJECTED, "La tentative doit passer en REJECTED.")
assert_equal(rejected_run.blocking_reason, reject_reason, "Le rejet doit conserver sa justification.")
assert_true(isinstance(rejected_run.events[-1], ProcessingRunRejected), "Le rejet doit produire un événement explicite.")
assert_equal(reject_repository.saved_runs, [rejected_run], "Le rejet doit être persisté une seule fois.")
assert_raises(
    "tentative M-003 non publiable: REJECTED",
    rejected_run.ensure_documentary_publication_allowed,
)
assert_raises("transition de diagnostic interdite", lambda: rejected_run.record_page_diagnostics(()))

# Given une tentative rejetée ne revient jamais à MANIFEST_CREATED.
# When une correction est relancée.
new_attempt = started_run("RUN-M003-T007-NEW", source_document)

# Then la correction crée une nouvelle tentative sans modifier l'ancienne.
assert_equal(new_attempt.status, DocumentProcessingRunStatus.MANIFEST_CREATED, "La correction doit démarrer une nouvelle tentative.")
assert_equal(new_attempt.document_id, rejected_run.document_id, "La nouvelle tentative doit rester liée à la même source.")
assert_true(new_attempt.processing_run_id != rejected_run.processing_run_id, "La nouvelle tentative doit porter un nouvel identifiant.")
assert_equal(rejected_run.status, DocumentProcessingRunStatus.REJECTED, "La tentative rejetée doit rester finalisée.")

print("Test d'acceptation T-007 blocages revue quarantaine: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_review_quarantine_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-007 blocages revue quarantaine: OK"
