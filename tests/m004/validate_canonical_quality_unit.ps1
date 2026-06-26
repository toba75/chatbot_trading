$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.domain.document_processing_run import (
    DiagnosticVersion,
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
    RouteDecisionMode,
    RoutePlan,
    RoutingPolicyVersion,
)
from app.source_processing.domain.page_conversion import (
    CanonicalAcceptancePolicy,
    ConversionToolName,
    CriticalPageSamplingPolicy,
    PageConversionArtifact,
    PageConversionCandidate,
    PageConversionItem,
    PageConversionItemLabel,
    PageItemGeometry,
    PagewiseDoclingFusionService,
    PostConversionQualityFinding,
    PostConversionQualityReport,
    PreConversionRouteComparison,
    PreConversionQualityReport,
    QualityDecisionStatus,
    QualityFindingCode,
    TextAuthorityManifest,
    TextAuthoritySelectionPolicy,
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
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def registered_source(suffix="UNIT"):
    original_content = f"%PDF-1.7\ncanonical quality {suffix}\n%%EOF\n".encode("utf-8")
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
                "title": f"Qualité canonique unitaire {suffix}",
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


def diagnostic(page_number, page_state, *, has_table=False, has_formula=False):
    native_text_state = "RELIABLE"
    image_state = "NONE"
    layout_complexity = "SIMPLE"
    mixed_content_detected = False
    if page_state is PageDecisionState.NATIVE_SUSPECT:
        native_text_state = "SUSPECT"
    if page_state is PageDecisionState.SCAN_CLEAN:
        native_text_state = "ABSENT"
        image_state = "SCAN_CLEAN"
    if page_state is PageDecisionState.COMPLEX_VISUAL:
        native_text_state = "SUSPECT"
        image_state = "SCAN_CLEAN"
        layout_complexity = "COMPLEX"
        mixed_content_detected = True
    return PageDecision(
        page_number=PageNumber.from_value(page_number),
        page_state=page_state,
        signals=PageDiagnosticSignals(
            native_text_state=native_text_state,
            image_state=image_state,
            existing_ocr_state="NONE",
            layout_complexity=layout_complexity,
            corruption_state="NONE",
            mixed_content_detected=mixed_content_detected,
            has_table=has_table,
            has_formula=has_formula,
        ),
        diagnostic_version=DiagnosticVersion.from_value("diag-quality-unit-v1"),
        justification=f"Diagnostic unitaire page {page_number}.",
    )


def route(page_number, route_name, *, confidence_score=0.97, decision_mode=RouteDecisionMode.AUTO):
    return PageRoute(
        page_number=PageNumber.from_value(page_number),
        route_name=route_name,
        decision_mode=decision_mode,
        confidence_score=confidence_score,
        preprocessing_action=PagePreprocessingAction.NONE,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-quality-unit-v1"),
        justification=f"Route unitaire page {page_number}.",
    )


def route_plan_for(page_routes):
    dominant_route = page_routes[0].route_name
    exceptions = tuple(page_route for page_route in page_routes if page_route.route_name is not dominant_route)
    return RoutePlan(
        routing_policy_version=RoutingPolicyVersion.from_value("routing-quality-unit-v1"),
        page_routes=tuple(page_routes),
        dominant_route_name=dominant_route,
        page_exceptions=exceptions,
        confidence_score=sum(page_route.confidence_score for page_route in page_routes) / len(page_routes),
    )


def conversion_item(page_number, *, label=PageConversionItemLabel.TEXT, text=None, content_hash=None):
    return PageConversionItem(
        label=label,
        text=text or f"Texte QA page {page_number}.",
        geometry=PageItemGeometry(
            left=10,
            top=20,
            right=90,
            bottom=70,
            page_width=100,
            page_height=100,
        ),
        content_hash=content_hash or (str(page_number) * 64),
    )


def artifact(page_number, route_name, *, label=PageConversionItemLabel.TEXT, text=None):
    return PageConversionArtifact(
        page_number=PageNumber.from_value(page_number),
        route_name=route_name,
        tool_name=(
            ConversionToolName.DOCLING_STANDARD
            if route_name is PageRouteName.NATIVE_STANDARD
            else ConversionToolName.GRANITE_DOCLING
        ),
        tool_version="quality-unit-tool-v1",
        artifact_hash=hex(page_number + 9)[2:] * 64,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T005-UNIT/page-{page_number:03d}.json"
        ),
        items=(conversion_item(page_number, label=label, text=text),),
    )


def authority_manifest_for(page_manifest, page_routes):
    policy = TextAuthoritySelectionPolicy(policy_version="text-authority-quality-unit-v1")
    decisions = []
    for page_route in page_routes:
        candidate_id = f"page-{page_route.page_number.value:03d}-authority"
        candidate = PageConversionCandidate(
            candidate_id=candidate_id,
            page_output=artifact(page_route.page_number.value, page_route.route_name),
        )
        decisions.append(
            policy.select(
                page_number=page_route.page_number,
                candidates=(candidate,),
                selected_candidate_ids=(candidate_id,),
                justification=f"Autorité unitaire page {page_route.page_number.value}.",
            )
        )
    return TextAuthorityManifest.from_page_decisions(
        page_manifest=page_manifest,
        page_decisions=tuple(decisions),
    )


def complete_docling_document(source_document, page_manifest, page_routes, *, canonical_version_id="CVER-M004-T005"):
    return PagewiseDoclingFusionService().merge(
        document_id=source_document.document_id,
        canonical_version_id=canonical_version_id,
        source_sha256=source_document.fingerprint,
        original_storage_ref=source_document.original_storage_ref,
        page_manifest=page_manifest,
        page_outputs=tuple(
            artifact(page_route.page_number.value, page_route.route_name)
            for page_route in page_routes
        ),
    )


assert_equal(
    tuple(QualityDecisionStatus.from_value(status.value) for status in QualityDecisionStatus),
    tuple(QualityDecisionStatus),
    "Tous les statuts QA publics doivent être acceptés explicitement.",
)
assert_raises("statut QA inconnu", lambda: QualityDecisionStatus.from_value("FALLBACK"))

assert_raises(
    "low_confidence_threshold",
    lambda: CriticalPageSamplingPolicy(policy_version="critical-pages-unit-v1"),
)
assert_raises(
    "version de politique QA obligatoire",
    lambda: CriticalPageSamplingPolicy(policy_version="", low_confidence_threshold=0.90),
)
assert_raises(
    "seuil de confiance critique invalide",
    lambda: CriticalPageSamplingPolicy(policy_version="critical-pages-unit-v1", low_confidence_threshold=1.5),
)

page_manifest = manifest_for(5)
page_diagnostics = (
    diagnostic(1, PageDecisionState.NATIVE_OK),
    diagnostic(2, PageDecisionState.NATIVE_OK),
    diagnostic(3, PageDecisionState.SCAN_CLEAN, has_table=True),
    diagnostic(4, PageDecisionState.NATIVE_SUSPECT, has_formula=True),
    diagnostic(5, PageDecisionState.COMPLEX_VISUAL),
)
page_routes = (
    route(1, PageRouteName.NATIVE_STANDARD),
    route(2, PageRouteName.NATIVE_STANDARD),
    route(3, PageRouteName.SCAN_GRANITE),
    route(4, PageRouteName.NATIVE_STANDARD, confidence_score=0.88, decision_mode=RouteDecisionMode.BENCHMARK),
    route(5, PageRouteName.TARGETED_ENRICHMENT, decision_mode=RouteDecisionMode.BENCHMARK),
)
route_plan = route_plan_for(page_routes)
selection = CriticalPageSamplingPolicy(
    policy_version="critical-pages-unit-v1",
    low_confidence_threshold=0.90,
).select(
    page_manifest=page_manifest,
    page_diagnostics=page_diagnostics,
    route_plan=route_plan,
)

assert_equal(tuple(page.value for page in selection.page_numbers), (1, 2, 3, 4, 5), "L'échantillon critique doit être trié et explicite.")
assert_true("FIRST_CONTENT" in selection.reasons_for(PageNumber.from_value(1)), "La première page de contenu doit être tracée.")
assert_true("FIRST_QUARTER" in selection.reasons_for(PageNumber.from_value(2)), "Le premier quart doit être tracé.")
assert_true("CENTER" in selection.reasons_for(PageNumber.from_value(3)), "La page centrale doit être tracée.")
assert_true("LAST_QUARTER" in selection.reasons_for(PageNumber.from_value(4)), "Le dernier quart doit être tracé.")
assert_true("FINAL_PAGE" in selection.reasons_for(PageNumber.from_value(5)), "La page finale doit être tracée.")
assert_true("TABLE" in selection.reasons_for(PageNumber.from_value(3)), "La table doit être tracée.")
assert_true("FORMULA" in selection.reasons_for(PageNumber.from_value(4)), "La formule doit être tracée.")
assert_true("LOW_CONFIDENCE" in selection.reasons_for(PageNumber.from_value(4)), "La faible confiance doit être tracée.")
assert_true("MINORITY_ROUTE" in selection.reasons_for(PageNumber.from_value(5)), "La route minoritaire doit être tracée.")
assert_raises("page critique absente", lambda: selection.reasons_for(PageNumber.from_value(9)))

retry_comparison = PreConversionRouteComparison(
    page_number=PageNumber.from_value(4),
    current_route_name=PageRouteName.NATIVE_STANDARD,
    alternative_route_name=PageRouteName.TARGETED_ENRICHMENT,
    status=QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE,
    justification="Relance explicite après divergence de signes.",
)
manual_review_comparison = PreConversionRouteComparison(
    page_number=PageNumber.from_value(5),
    current_route_name=PageRouteName.TARGETED_ENRICHMENT,
    alternative_route_name=PageRouteName.SCAN_GRANITE,
    status=QualityDecisionStatus.MANUAL_REVIEW,
    justification="Lecture visuelle ambiguë.",
)
pre_report = PreConversionQualityReport(
    policy_version="canonical-quality-unit-v1",
    critical_page_selection=selection,
    route_comparisons=(retry_comparison,),
    status=QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE,
)
assert_equal(pre_report.status, QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE, "Le statut de retry doit être conservé.")
assert_equal(pre_report.route_comparisons[0].alternative_route_name, PageRouteName.TARGETED_ENRICHMENT, "La route alternative doit être explicitement tracée.")
assert_raises(
    "route alternative obligatoire",
    lambda: PreConversionRouteComparison(
        page_number=PageNumber.from_value(4),
        current_route_name=PageRouteName.NATIVE_STANDARD,
        alternative_route_name=None,
        status=QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE,
        justification="Retry sans route alternative.",
    ),
)
assert_raises(
    "comparaison de route obligatoire",
    lambda: PreConversionQualityReport(
        policy_version="canonical-quality-unit-v1",
        critical_page_selection=selection,
        route_comparisons=(),
        status=QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE,
    ),
)

source_document = registered_source()
authority_manifest = authority_manifest_for(page_manifest, page_routes)
docling_document = complete_docling_document(source_document, page_manifest, page_routes)
acceptance_policy = CanonicalAcceptancePolicy(policy_version="canonical-quality-unit-v1")
clean_post_report = acceptance_policy.evaluate_post_conversion(
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    docling_document=docling_document,
    findings=(),
)
pass_report = PreConversionQualityReport(
    policy_version="canonical-quality-unit-v1",
    critical_page_selection=selection,
    route_comparisons=(),
    status=QualityDecisionStatus.PASS,
)
accepted_decision = acceptance_policy.decide(
    source_document=source_document,
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    pre_conversion_report=pass_report,
    post_conversion_report=clean_post_report,
)
assert_equal(clean_post_report.status, QualityDecisionStatus.PASS, "Un rapport post-conversion sans anomalie doit passer.")
assert_equal(accepted_decision.publication_allowed, True, "Une QA PASS complète doit rendre la candidate publiable.")
assert_equal(accepted_decision.status, QualityDecisionStatus.PASS, "La décision acceptée doit conserver PASS.")

incomplete_docling_document = PagewiseDoclingFusionService().merge(
    document_id=source_document.document_id,
    canonical_version_id="CVER-M004-T005",
    source_sha256=source_document.fingerprint,
    original_storage_ref=source_document.original_storage_ref,
    page_manifest=manifest_for(4),
    page_outputs=tuple(artifact(page_route.page_number.value, page_route.route_name) for page_route in page_routes[:4]),
)
blocking_findings = (
    PostConversionQualityFinding(
        code=QualityFindingCode.NUMERIC_INCONSISTENCY,
        page_number=PageNumber.from_value(4),
        item_id=incomplete_docling_document.pages[3].items[0].item_id,
        expected="100.0",
        actual="10.0",
        detail="Incohérence numérique.",
    ),
    PostConversionQualityFinding(
        code=QualityFindingCode.NEGATIVE_SIGN_ALTERED,
        page_number=PageNumber.from_value(4),
        item_id=incomplete_docling_document.pages[3].items[0].item_id,
        expected="-4.2",
        actual="4.2",
        detail="Signe négatif altéré.",
    ),
    PostConversionQualityFinding(
        code=QualityFindingCode.INCOMPLETE_TABLE,
        page_number=PageNumber.from_value(3),
        item_id=incomplete_docling_document.pages[2].items[0].item_id,
        expected="trois colonnes",
        actual="deux colonnes",
        detail="Tableau incomplet.",
    ),
)
red_post_report = acceptance_policy.evaluate_post_conversion(
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    docling_document=incomplete_docling_document,
    findings=blocking_findings,
)
red_decision = acceptance_policy.decide(
    source_document=source_document,
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    pre_conversion_report=PreConversionQualityReport(
        policy_version="canonical-quality-unit-v1",
        critical_page_selection=selection,
        route_comparisons=(manual_review_comparison,),
        status=QualityDecisionStatus.MANUAL_REVIEW,
    ),
    post_conversion_report=red_post_report,
)

red_codes = tuple(finding.code for finding in red_decision.findings)
assert_equal(red_post_report.status, QualityDecisionStatus.MANUAL_REVIEW, "Les anomalies bloquantes doivent demander revue.")
assert_equal(red_decision.publication_allowed, False, "Une QA RED doit refuser la publication.")
assert_equal(red_decision.status, QualityDecisionStatus.MANUAL_REVIEW, "La revue manuelle doit rester explicite.")
assert_true(QualityFindingCode.PAGE_OMITTED in red_codes, "La page omise doit être détectée.")
assert_true(QualityFindingCode.NUMERIC_INCONSISTENCY in red_codes, "L'incohérence numérique doit être conservée.")
assert_true(QualityFindingCode.NEGATIVE_SIGN_ALTERED in red_codes, "Le signe altéré doit être conservé.")
assert_true(QualityFindingCode.INCOMPLETE_TABLE in red_codes, "Le tableau incomplet doit être conservé.")
assert_equal(red_decision.publication_events, (), "La QA RED ne doit pas produire d'événement de publication.")

warning_post_report = PostConversionQualityReport(
    policy_version="canonical-quality-unit-v1",
    findings=(
        PostConversionQualityFinding(
            code=QualityFindingCode.WARNING_REVIEW_NOTE,
            page_number=PageNumber.from_value(2),
            item_id=docling_document.pages[1].items[0].item_id,
            expected="note audit",
            actual="note audit",
            detail="Avertissement non bloquant.",
        ),
    ),
    status=QualityDecisionStatus.PASS_WITH_WARNINGS,
)
warning_decision = acceptance_policy.decide(
    source_document=source_document,
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    pre_conversion_report=pass_report,
    post_conversion_report=warning_post_report,
)
assert_equal(warning_decision.publication_allowed, True, "PASS_WITH_WARNINGS doit rester publiable.")
assert_equal(warning_decision.status, QualityDecisionStatus.PASS_WITH_WARNINGS, "Les avertissements doivent être conservés.")

quarantine_decision = acceptance_policy.decide(
    source_document=source_document.quarantine("Quarantaine unitaire explicite."),
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    pre_conversion_report=pass_report,
    post_conversion_report=clean_post_report,
)
assert_equal(quarantine_decision.status, QualityDecisionStatus.QUARANTINE, "La quarantaine doit dominer la décision.")
assert_equal(quarantine_decision.publication_allowed, False, "Une source quarantinée ne doit pas être publiable.")
assert_true(QualityFindingCode.SOURCE_QUARANTINED in tuple(finding.code for finding in quarantine_decision.findings), "La quarantaine doit être conservée.")

assert_raises(
    "obligatoire",
    lambda: acceptance_policy.decide(
        source_document=source_document,
        page_manifest=page_manifest,
        text_authority_manifest=authority_manifest,
        pre_conversion_report=None,
        post_conversion_report=clean_post_report,
    ),
)
assert_raises(
    "post-conversion",
    lambda: acceptance_policy.decide(
        source_document=source_document,
        page_manifest=page_manifest,
        text_authority_manifest=authority_manifest,
        pre_conversion_report=pass_report,
        post_conversion_report=None,
    ),
)
assert_raises(
    "incoh",
    lambda: acceptance_policy.decide(
        source_document=source_document,
        page_manifest=page_manifest,
        text_authority_manifest=authority_manifest,
        pre_conversion_report=PreConversionQualityReport(
            policy_version="autre-politique",
            critical_page_selection=selection,
            route_comparisons=(),
            status=QualityDecisionStatus.PASS,
        ),
        post_conversion_report=clean_post_report,
    ),
)
assert_raises(
    "incoh",
    lambda: acceptance_policy.decide(
        source_document=source_document,
        page_manifest=page_manifest,
        text_authority_manifest=authority_manifest,
        pre_conversion_report=pass_report,
        post_conversion_report=PostConversionQualityReport(
            policy_version="autre-politique",
            findings=(),
            status=QualityDecisionStatus.PASS,
        ),
    ),
)
assert_true(
    "Texte QA page" not in str(red_decision.to_audit_payload()),
    "Le payload d'audit ne doit pas contenir le texte documentaire complet.",
)

print("Tests unitaires T-005 qualité canonique M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_canonical_quality_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Tests unitaires T-005 qualité canonique M-004: OK"
