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


def route_configuration():
    return PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        auto_confidence_min=0.90,
        benchmark_confidence_min=0.85,
    )


def routing_policy_version():
    return RoutingPolicyVersion.from_value("routing-v1")


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


def state_signals(page_state):
    if page_state is PageDecisionState.NATIVE_OK:
        return signals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )
    if page_state is PageDecisionState.UNSUPPORTED_OR_CORRUPT:
        return signals(
            native_text_state="ABSENT",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="CORRUPT",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )
    raise AssertionError(f"État non testable dans T-007: {page_state!r}")


def decision(page_number, page_state):
    return PageDecision(
        page_number=PageNumber.from_value(page_number),
        page_state=page_state,
        signals=state_signals(page_state),
        diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
        justification=f"Diagnostic explicite {page_state.value}.",
    )


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
                "title": "Transitions de blocage M-003",
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


def started_run(processing_run_id):
    return DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value(processing_run_id),
        source_document=registered_source(),
        page_manifest=manifest_for(2),
    )


def diagnosed_routeable_run(processing_run_id):
    return started_run(processing_run_id).record_page_diagnostics(
        (
            decision(1, PageDecisionState.NATIVE_OK),
            decision(2, PageDecisionState.NATIVE_OK),
        )
    )


def diagnosed_corrupt_run(processing_run_id):
    return started_run(processing_run_id).record_page_diagnostics(
        (
            decision(1, PageDecisionState.NATIVE_OK),
            decision(2, PageDecisionState.UNSUPPORTED_OR_CORRUPT),
        )
    )


def manual_review_run(processing_run_id):
    return diagnosed_corrupt_run(processing_run_id).decide_route_plan(route_configuration())


# Les transitions bloquantes autorisées conservent justification et version de politique.
manual_run = manual_review_run("RUN-M003-T007-UNIT-MANUAL")
quarantine_reason = "Corruption confirmée; source isolée avant publication documentaire."
quarantined_run = manual_run.quarantine(
    routing_policy_version=routing_policy_version(),
    reason=quarantine_reason,
)
assert_equal(quarantined_run.status, DocumentProcessingRunStatus.QUARANTINED, "La revue manuelle doit pouvoir devenir QUARANTINED.")
assert_equal(quarantined_run.blocking_reason, quarantine_reason, "La quarantaine doit conserver la justification bloquante.")
assert_equal(quarantined_run.blocking_policy_version.value, "routing-v1", "La quarantaine doit conserver la version de politique.")
assert_is_none(quarantined_run.route_plan, "Une quarantaine ne doit pas conserver de plan publiable.")
assert_true(isinstance(quarantined_run.events[-1], ProcessingRunQuarantined), "La quarantaine doit produire un événement dédié.")

direct_quarantine = diagnosed_corrupt_run("RUN-M003-T007-UNIT-DIRECT").quarantine(
    routing_policy_version=routing_policy_version(),
    reason="Diagnostic corrompu isolé sans route automatique.",
)
assert_equal(direct_quarantine.status, DocumentProcessingRunStatus.QUARANTINED, "Un diagnostic corrompu doit pouvoir être quarantiné directement.")

manifest_quarantine = started_run("RUN-M003-T007-UNIT-MANIFEST").quarantine(
    routing_policy_version=routing_policy_version(),
    reason="Manifeste illisible isolé avant diagnostic.",
)
assert_equal(manifest_quarantine.status, DocumentProcessingRunStatus.QUARANTINED, "Un manifeste créé doit pouvoir être quarantiné directement.")
assert_equal(manifest_quarantine.page_decisions, (), "La quarantaine depuis manifeste ne doit pas fabriquer de diagnostics.")

quarantined_source = registered_source().quarantine(reason="Source isolée avant nouvelle tentative.")
assert_raises(
    "source documentaire non publiable: QUARANTINED",
    lambda: DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M003-T007-SOURCE-BLOCKED"),
        source_document=quarantined_source,
        page_manifest=manifest_for(2),
    ),
)

reject_reason = "Route insuffisamment justifiée après revue manuelle."
rejected_run = manual_review_run("RUN-M003-T007-UNIT-REJECT").reject(
    routing_policy_version=routing_policy_version(),
    reason=reject_reason,
)
assert_equal(rejected_run.status, DocumentProcessingRunStatus.REJECTED, "La revue manuelle doit pouvoir être rejetée.")
assert_equal(rejected_run.blocking_reason, reject_reason, "Le rejet doit conserver sa justification.")
assert_equal(rejected_run.blocking_policy_version.value, "routing-v1", "Le rejet doit conserver la version de politique.")
assert_true(isinstance(rejected_run.events[-1], ProcessingRunRejected), "Le rejet doit produire un événement dédié.")

# Les transitions interdites ne rouvrent pas une tentative finalisée.
assert_raises(
    "transition de rejet interdite",
    lambda: started_run("RUN-M003-T007-UNIT-STARTED").reject(
        routing_policy_version=routing_policy_version(),
        reason="Rejet sans diagnostic interdit.",
    ),
)

planned_run = diagnosed_routeable_run("RUN-M003-T007-UNIT-PLANNED").decide_route_plan(route_configuration())
assert_equal(planned_run.status, DocumentProcessingRunStatus.ROUTE_PLANNED, "Le plan routé reste le seul état prêt pour l'aval.")
assert_raises(
    "transition de quarantaine interdite",
    lambda: planned_run.quarantine(
        routing_policy_version=routing_policy_version(),
        reason="Quarantaine tardive interdite.",
    ),
)
assert_raises(
    "transition de rejet interdite",
    lambda: quarantined_run.reject(
        routing_policy_version=routing_policy_version(),
        reason="Rejet après quarantaine interdit.",
    ),
)
assert_raises(
    "transition de diagnostic interdite",
    lambda: rejected_run.record_page_diagnostics(
        (
            decision(1, PageDecisionState.NATIVE_OK),
            decision(2, PageDecisionState.NATIVE_OK),
        )
    ),
)
assert_raises("transition de routage interdite", lambda: rejected_run.decide_route_plan(route_configuration()))

# Les états bloquants refusent explicitement la publication documentaire.
assert_raises(
    "tentative M-003 non publiable: MANUAL_REVIEW",
    manual_run.ensure_documentary_publication_allowed,
)
assert_raises(
    "tentative M-003 non publiable: QUARANTINED",
    quarantined_run.ensure_documentary_publication_allowed,
)
assert_raises(
    "tentative M-003 non publiable: REJECTED",
    rejected_run.ensure_documentary_publication_allowed,
)

planned_run.ensure_documentary_publication_allowed()

print("Tests unitaires T-007 blocages revue quarantaine: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_review_quarantine_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-007 blocages revue quarantaine: OK"
