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
    PagePreprocessingAction,
    PageRoute,
    PageRouteName,
    PageRoutingConfiguration,
    PageRoutingPolicy,
    ProcessingRunId,
    RouteDecisionMode,
    RoutePlanningOutcome,
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


def route_configuration(auto_min=0.90, benchmark_min=0.85):
    return PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        auto_confidence_min=auto_min,
        benchmark_confidence_min=benchmark_min,
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
    if page_state is PageDecisionState.NATIVE_SUSPECT:
        return signals(
            native_text_state="SUSPECT",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )
    if page_state is PageDecisionState.SCAN_CLEAN:
        return signals(
            native_text_state="ABSENT",
            image_state="SCAN_CLEAN",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )
    if page_state is PageDecisionState.SCAN_DEGRADED:
        return signals(
            native_text_state="ABSENT",
            image_state="SCAN_DEGRADED",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )
    if page_state is PageDecisionState.OCR_BAD:
        return signals(
            native_text_state="ABSENT",
            image_state="NONE",
            existing_ocr_state="BAD",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=False,
            has_formula=False,
        )
    if page_state is PageDecisionState.MIXED_CONTENT:
        return signals(
            native_text_state="RELIABLE",
            image_state="SCAN_CLEAN",
            existing_ocr_state="NONE",
            layout_complexity="SIMPLE",
            corruption_state="NONE",
            mixed_content_detected=True,
            has_table=True,
            has_formula=False,
        )
    if page_state is PageDecisionState.COMPLEX_VISUAL:
        return signals(
            native_text_state="RELIABLE",
            image_state="NONE",
            existing_ocr_state="NONE",
            layout_complexity="COMPLEX",
            corruption_state="NONE",
            mixed_content_detected=False,
            has_table=True,
            has_formula=True,
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
    raise AssertionError(f"État non testé: {page_state!r}")


def decision(page_number, page_state):
    return PageDecision(
        page_number=PageNumber.from_value(page_number),
        page_state=page_state,
        signals=state_signals(page_state),
        diagnostic_version=DiagnosticVersion.from_value("diag-v1"),
        justification=f"Diagnostic explicite {page_state.value}.",
    )


def assert_route_mapping(page_state, expected_route, expected_mode, expected_preprocessing):
    route = PageRoutingPolicy().decide_page_route(
        page_decision=decision(1, page_state),
        routing_configuration=route_configuration(),
    )
    assert_equal(route.route_name, expected_route, f"Mapping route invalide pour {page_state.value}.")
    assert_equal(route.decision_mode, expected_mode, f"Mode de décision invalide pour {page_state.value}.")
    assert_equal(route.preprocessing_action, expected_preprocessing, f"Prétraitement invalide pour {page_state.value}.")
    assert_equal(route.routing_policy_version.value, "routing-v1", "La version de politique doit être stockée sur la route.")


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
                "title": "Routage documentaire",
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


def diagnosed_run():
    started_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value("RUN-M003-T006-UNIT"),
        source_document=registered_source(),
        page_manifest=manifest_for(3),
    )
    return started_run.record_page_diagnostics(
        (
            decision(1, PageDecisionState.NATIVE_OK),
            decision(2, PageDecisionState.NATIVE_OK),
            decision(3, PageDecisionState.SCAN_CLEAN),
        )
    )


# Les états diagnostiques publiés sont mappés vers des routes explicites.
assert_route_mapping(
    PageDecisionState.NATIVE_OK,
    PageRouteName.NATIVE_STANDARD,
    RouteDecisionMode.AUTO,
    PagePreprocessingAction.NONE,
)
assert_route_mapping(
    PageDecisionState.NATIVE_SUSPECT,
    PageRouteName.NATIVE_STANDARD,
    RouteDecisionMode.BENCHMARK,
    PagePreprocessingAction.NONE,
)
assert_route_mapping(
    PageDecisionState.SCAN_CLEAN,
    PageRouteName.SCAN_GRANITE,
    RouteDecisionMode.AUTO,
    PagePreprocessingAction.NONE,
)
assert_route_mapping(
    PageDecisionState.SCAN_DEGRADED,
    PageRouteName.PREPROCESS_GRANITE,
    RouteDecisionMode.AUTO,
    PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING,
)
assert_route_mapping(
    PageDecisionState.OCR_BAD,
    PageRouteName.BAD_OCR_TO_GRANITE,
    RouteDecisionMode.AUTO,
    PagePreprocessingAction.NONE,
)
assert_route_mapping(
    PageDecisionState.MIXED_CONTENT,
    PageRouteName.MIXED_PAGEWISE,
    RouteDecisionMode.AUTO,
    PagePreprocessingAction.NONE,
)
assert_route_mapping(
    PageDecisionState.COMPLEX_VISUAL,
    PageRouteName.TARGETED_ENRICHMENT,
    RouteDecisionMode.BENCHMARK,
    PagePreprocessingAction.NONE,
)

# Les seuils refusent une route dont le score ne suffit pas au benchmark.
strict_result = PageRoutingPolicy().plan_routes(
    page_decisions=(decision(1, PageDecisionState.COMPLEX_VISUAL),),
    routing_configuration=route_configuration(auto_min=0.95, benchmark_min=0.87),
)
assert_equal(strict_result.outcome, RoutePlanningOutcome.MANUAL_REVIEW, "Un score insuffisant doit demander une revue manuelle.")
assert_is_none(strict_result.route_plan, "Un refus de seuil ne doit pas produire de route implicite.")
assert_true("score de confiance" in strict_result.manual_review_reason, "La justification doit nommer le seuil refusé.")

# Une page corrompue ne reçoit jamais une autre route par défaut.
unsupported_result = PageRoutingPolicy().plan_routes(
    page_decisions=(decision(1, PageDecisionState.UNSUPPORTED_OR_CORRUPT),),
    routing_configuration=route_configuration(),
)
assert_equal(unsupported_result.outcome, RoutePlanningOutcome.MANUAL_REVIEW, "Une page corrompue doit demander une revue manuelle.")
assert_is_none(unsupported_result.route_plan, "Une page corrompue ne doit pas recevoir de plan de remplacement.")
assert_true("page 1" in unsupported_result.manual_review_reason, "La page refusée doit être nommée.")

# La configuration de seuils est explicite et versionnée.
assert_raises(
    "version de politique de routage invalide",
    lambda: PageRoutingConfiguration(
        routing_policy_version="routing-v1",
        auto_confidence_min=0.90,
        benchmark_confidence_min=0.85,
    ),
)
assert_raises(
    "seuil de confiance de routage invalide",
    lambda: PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        auto_confidence_min=1.10,
        benchmark_confidence_min=0.85,
    ),
)
assert_raises(
    "ordre des seuils de routage invalide",
    lambda: PageRoutingConfiguration(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        auto_confidence_min=0.80,
        benchmark_confidence_min=0.85,
    ),
)

# OCRmyPDF est refusé hors diagnostic admissible.
assert_raises(
    "prétraitement OCRmyPDF inadmissible",
    lambda: PageRoute(
        page_number=PageNumber.from_value(1),
        route_name=PageRouteName.NATIVE_STANDARD,
        decision_mode=RouteDecisionMode.AUTO,
        confidence_score=0.98,
        preprocessing_action=PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-v1"),
        justification="Prétraitement interdit sur une page native.",
    ),
)

# Le run refuse un routage sans diagnostic et interdit toute modification d'un plan approuvé.
started_run = DocumentProcessingRun.start(
    processing_run_id=ProcessingRunId.from_value("RUN-M003-T006-NO-DIAG"),
    source_document=registered_source(),
    page_manifest=manifest_for(1),
)
assert_raises("transition de routage interdite", lambda: started_run.decide_route_plan(route_configuration()))

planned_run = diagnosed_run().decide_route_plan(route_configuration())
assert_equal(planned_run.status, DocumentProcessingRunStatus.ROUTE_PLANNED, "Le run diagnostiqué doit passer à ROUTE_PLANNED.")
assert_equal(
    tuple(page_route.page_number.value for page_route in planned_run.route_plan.page_exceptions),
    (3,),
    "Les exceptions par page doivent être conservées.",
)
assert_raises("transition de routage interdite", lambda: planned_run.decide_route_plan(route_configuration()))

print("Tests unitaires T-006 plan de routage explicite: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_route_plan_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-006 plan de routage explicite: OK"
