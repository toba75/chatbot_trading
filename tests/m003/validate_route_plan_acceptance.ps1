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
from app.source_processing.application.record_page_diagnostics import (
    PageDiagnosticInput,
    RecordPageDiagnosticsCommand,
    RecordPageDiagnosticsHandler,
)
from app.source_processing.domain.document_processing_run import (
    DocumentProcessingRun,
    DocumentProcessingRunStatus,
    ManualReviewRequested,
    PageDecisionState,
    PageDiagnosticSignals,
    PageManifest,
    PageManifestEntry,
    PageManifestEntryState,
    PageNumber,
    PagePreprocessingAction,
    PageRouteDecided,
    PageRouteName,
    PageRoutingConfiguration,
    ProcessingRunId,
    RouteDecisionMode,
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
        self.saved_transition_statuses = []

    def save(self, processing_run):
        self.saved_runs.append(processing_run)

    def save_transition(self, processing_run, *, expected_status):
        self.saved_runs.append(processing_run)
        self.saved_transition_statuses.append(expected_status)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def assert_is_none(value, message):
    if value is not None:
        raise AssertionError(f"{message} Valeur obtenue: {value!r}")


def assert_not_none(value, message):
    if value is None:
        raise AssertionError(message)


def registered_source():
    original_content = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 5 >>\nendobj\ntrailer\n<<>>\n%%EOF\n"
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
                "title": "Source routée par page",
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


def diagnosed_run(processing_run_id, diagnostics):
    source_document = registered_source()
    processing_run = DocumentProcessingRun.start(
        processing_run_id=ProcessingRunId.from_value(processing_run_id),
        source_document=source_document,
        page_manifest=manifest_for(len(diagnostics)),
    )
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


routeable_diagnostics = (
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
        "Texte natif fiable sur page simple.",
    ),
    diagnostic(
        2,
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
        "Deuxième page native fiable.",
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
        "Scan propre sans texte natif.",
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
        "Scan dégradé nécessitant un prétraitement physique.",
    ),
    diagnostic(
        5,
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
        "Page complexe avec tableau et formule critique.",
    ),
)

# Given toutes les pages d'une source ont un état diagnostique et une version de politique.
diagnosed_routeable_run = diagnosed_run("RUN-M003-T006-ACCEPTANCE", routeable_diagnostics)
route_repository = InMemoryProcessingRunRepository()
route_handler = ApproveRoutePlanHandler(processing_run_repository=route_repository)

# When le plan de routage est décidé.
planned_run = route_handler.handle(
    ApproveRoutePlanCommand(
        processing_run=diagnosed_routeable_run,
        routing_configuration=route_configuration(),
    )
)

# Then chaque page reçoit une route et une justification, ou le traitement est refusé explicitement.
assert_equal(planned_run.status, DocumentProcessingRunStatus.ROUTE_PLANNED, "La tentative doit passer à ROUTE_PLANNED.")
assert_not_none(planned_run.route_plan, "Un plan approuvé doit être conservé dans la tentative.")
assert_is_none(planned_run.manual_review_reason, "Un plan approuvé ne doit pas conserver de revue manuelle.")
assert_equal(
    planned_run.route_plan.routing_policy_version.value,
    "routing-v1",
    "La version de configuration appliquée doit être stockée.",
)
assert_equal(len(planned_run.route_plan.page_routes), 5, "Chaque page diagnostiquée doit recevoir une route explicite.")
routes_by_page = {
    page_route.page_number.value: page_route
    for page_route in planned_run.route_plan.page_routes
}
assert_equal(routes_by_page[1].route_name, PageRouteName.NATIVE_STANDARD, "La page native doit utiliser la route native.")
assert_equal(routes_by_page[1].decision_mode, RouteDecisionMode.AUTO, "La page native fiable doit être routée en AUTO.")
assert_equal(routes_by_page[3].route_name, PageRouteName.SCAN_GRANITE, "Le scan propre doit utiliser la route Granite.")
assert_equal(routes_by_page[4].route_name, PageRouteName.PREPROCESS_GRANITE, "Le scan dégradé doit utiliser la route avec prétraitement.")
assert_equal(
    routes_by_page[4].preprocessing_action,
    PagePreprocessingAction.OCR_PHYSICAL_PREPROCESSING,
    "Le prétraitement OCRmyPDF doit rester conditionnel au diagnostic admissible.",
)
assert_equal(
    routes_by_page[5].route_name,
    PageRouteName.TARGETED_ENRICHMENT,
    "La page complexe doit utiliser l'enrichissement ciblé.",
)
assert_equal(
    routes_by_page[5].decision_mode,
    RouteDecisionMode.BENCHMARK,
    "La page complexe doit passer en benchmark et non en route automatique silencieuse.",
)
assert_equal(
    tuple(page_route.page_number.value for page_route in planned_run.route_plan.page_exceptions),
    (3, 4, 5),
    "Les exceptions par page doivent exclure la route dominante native.",
)
assert_equal(
    planned_run.route_plan.dominant_route_name,
    PageRouteName.NATIVE_STANDARD,
    "La route dominante doit être calculée explicitement.",
)
assert_equal(round(planned_run.route_plan.confidence_score, 3), 0.934, "Le score de confiance du plan doit être conservé.")
assert_true(
    all(page_route.justification.strip() == page_route.justification for page_route in planned_run.route_plan.page_routes),
    "Chaque route doit conserver une justification non ambiguë.",
)
assert_true(
    all(isinstance(event, PageRouteDecided) for event in planned_run.events[-5:]),
    "Chaque route décidée doit produire un événement PageRouteDecided.",
)
assert_equal(route_repository.saved_runs, [planned_run], "Le plan routé doit être persisté une seule fois.")
assert_equal(
    route_repository.saved_transition_statuses,
    [diagnosed_routeable_run.status],
    "Le plan routé doit être persisté avec le statut source attendu.",
)

uncertain_diagnostics = (
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

# Given une page diagnostiquée reste impossible à router.
diagnosed_uncertain_run = diagnosed_run("RUN-M003-T006-MANUAL", uncertain_diagnostics)
manual_repository = InMemoryProcessingRunRepository()
manual_handler = ApproveRoutePlanHandler(processing_run_repository=manual_repository)

# When le plan de routage est demandé.
manual_run = manual_handler.handle(
    ApproveRoutePlanCommand(
        processing_run=diagnosed_uncertain_run,
        routing_configuration=route_configuration(),
    )
)

# Then la tentative passe en MANUAL_REVIEW sans route de remplacement implicite.
assert_equal(manual_run.status, DocumentProcessingRunStatus.MANUAL_REVIEW, "Une route incertaine doit demander une revue manuelle.")
assert_is_none(manual_run.route_plan, "La revue manuelle ne doit pas fabriquer de plan de remplacement.")
assert_true("page 2" in manual_run.manual_review_reason, "La revue manuelle doit nommer la page refusée.")
assert_true(isinstance(manual_run.events[-1], ManualReviewRequested), "La revue manuelle doit produire un événement explicite.")
assert_equal(manual_repository.saved_runs, [manual_run], "La revue manuelle doit être persistée une seule fois.")
assert_equal(
    manual_repository.saved_transition_statuses,
    [diagnosed_uncertain_run.status],
    "La revue manuelle doit être persistée avec le statut source attendu.",
)

print("Test d'acceptation T-006 plan de routage explicite: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m003_route_plan_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-006 plan de routage explicite: OK"
