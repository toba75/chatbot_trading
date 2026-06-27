$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import hashlib
import sys

sys.path.insert(0, sys.argv[1])

from app.source_processing.domain.document_processing_run import (
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
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def registered_source():
    original_content = b"%PDF-1.7\ncanonical quality acceptance\n%%EOF\n"
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
                "title": "Qualité canonique M-004",
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


def content_hash_for(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def signals_for(page_state, *, has_table=False, has_formula=False):
    native_text_state = "RELIABLE"
    image_state = "NONE"
    layout_complexity = "SIMPLE"
    if page_state is PageDecisionState.NATIVE_SUSPECT:
        native_text_state = "SUSPECT"
    if page_state is PageDecisionState.SCAN_CLEAN:
        native_text_state = "ABSENT"
        image_state = "SCAN_CLEAN"
    if page_state is PageDecisionState.COMPLEX_VISUAL:
        native_text_state = "SUSPECT"
        image_state = "SCAN_CLEAN"
        layout_complexity = "COMPLEX"
    return PageDiagnosticSignals(
        native_text_state=native_text_state,
        image_state=image_state,
        existing_ocr_state="NONE",
        layout_complexity=layout_complexity,
        corruption_state="NONE",
        mixed_content_detected=page_state is PageDecisionState.COMPLEX_VISUAL,
        has_table=has_table,
        has_formula=has_formula,
    )


def diagnostic(page_number, page_state, *, has_table=False, has_formula=False):
    return PageDecision(
        page_number=PageNumber.from_value(page_number),
        page_state=page_state,
        signals=signals_for(page_state, has_table=has_table, has_formula=has_formula),
        diagnostic_version=__import__(
            "app.source_processing.domain.document_processing_run",
            fromlist=["DiagnosticVersion"],
        ).DiagnosticVersion.from_value("diag-quality-v1"),
        justification=f"Diagnostic explicite page {page_number}.",
    )


def route(
    page_number,
    route_name,
    *,
    decision_mode=RouteDecisionMode.AUTO,
    confidence_score=0.97,
):
    return PageRoute(
        page_number=PageNumber.from_value(page_number),
        route_name=route_name,
        decision_mode=decision_mode,
        confidence_score=confidence_score,
        preprocessing_action=PagePreprocessingAction.NONE,
        routing_policy_version=RoutingPolicyVersion.from_value("routing-quality-v1"),
        justification=f"Route explicite page {page_number}.",
    )


def conversion_item(page_number, label=PageConversionItemLabel.TEXT, text=None, content_hash=None):
    item_text = text or f"Contenu contrôlé page {page_number}."
    return PageConversionItem(
        label=label,
        text=item_text,
        geometry=PageItemGeometry(
            left=100,
            top=100,
            right=900,
            bottom=300,
            page_width=1000,
            page_height=1000,
        ),
        content_hash=content_hash_for(item_text) if content_hash is None else content_hash,
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
        tool_version="quality-tool-v1",
        artifact_hash=hex(page_number)[2:] * 64,
        audit_artifact_ref=(
            "artifact:source_processing.page_conversion/"
            f"RUN-M004-T005/page-{page_number:03d}.json"
        ),
        items=(conversion_item(page_number, label=label, text=text),),
    )


def authority_manifest_for(page_manifest, page_routes):
    policy = TextAuthoritySelectionPolicy(policy_version="text-authority-v1")
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
                justification=f"Autorité explicite page {page_route.page_number.value}.",
            )
        )
    return TextAuthorityManifest.from_page_decisions(
        page_manifest=page_manifest,
        page_decisions=tuple(decisions),
    )


source_document = registered_source()
page_manifest = manifest_for(6)
page_diagnostics = (
    diagnostic(1, PageDecisionState.NATIVE_OK),
    diagnostic(2, PageDecisionState.NATIVE_OK),
    diagnostic(3, PageDecisionState.NATIVE_OK),
    diagnostic(4, PageDecisionState.SCAN_CLEAN, has_table=True),
    diagnostic(5, PageDecisionState.NATIVE_SUSPECT, has_table=True),
    diagnostic(6, PageDecisionState.COMPLEX_VISUAL, has_formula=True),
)
page_routes = (
    route(1, PageRouteName.NATIVE_STANDARD),
    route(2, PageRouteName.NATIVE_STANDARD),
    route(3, PageRouteName.NATIVE_STANDARD),
    route(4, PageRouteName.SCAN_GRANITE),
    route(
        5,
        PageRouteName.NATIVE_STANDARD,
        decision_mode=RouteDecisionMode.BENCHMARK,
        confidence_score=0.86,
    ),
    route(6, PageRouteName.TARGETED_ENRICHMENT, decision_mode=RouteDecisionMode.BENCHMARK),
)
route_plan = RoutePlan(
    routing_policy_version=RoutingPolicyVersion.from_value("routing-quality-v1"),
    page_routes=page_routes,
    dominant_route_name=PageRouteName.NATIVE_STANDARD,
    page_exceptions=(page_routes[3], page_routes[5]),
    confidence_score=0.94,
)

# Given une source routée contient une page faible, une route minoritaire et une table financière critique.
# When la QA pré-conversion sélectionne les pages critiques et compare les routes ambiguës.
sampling_policy = CriticalPageSamplingPolicy(
    policy_version="critical-pages-v1",
    low_confidence_threshold=0.90,
)
critical_selection = sampling_policy.select(
    page_manifest=page_manifest,
    page_diagnostics=page_diagnostics,
    route_plan=route_plan,
)
route_retry = PreConversionRouteComparison(
    page_number=PageNumber.from_value(5),
    current_route_name=PageRouteName.NATIVE_STANDARD,
    alternative_route_name=PageRouteName.TARGETED_ENRICHMENT,
    status=QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE,
    justification="Signe négatif divergent entre route native et enrichissement ciblé.",
)
pre_report = PreConversionQualityReport(
    policy_version="canonical-quality-v1",
    critical_page_selection=critical_selection,
    route_comparisons=(route_retry,),
    status=QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE,
)

# Then les pages critiques sont sélectionnées explicitement et le retry est une décision métier tracée.
assert_equal(
    tuple(page.value for page in critical_selection.page_numbers),
    (1, 2, 3, 4, 5, 6),
    "Toutes les pages critiques attendues doivent être explicites.",
)
assert_true("LOW_CONFIDENCE" in critical_selection.reasons_for(PageNumber.from_value(5)), "La page faible doit porter une raison explicite.")
assert_true("MINORITY_ROUTE" in critical_selection.reasons_for(PageNumber.from_value(6)), "La route minoritaire doit être tracée.")
assert_equal(route_retry.status, QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE, "Le retry doit porter un statut métier explicite.")
assert_equal(pre_report.status, QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE, "Le rapport pré-conversion doit conserver le statut de retry.")

authority_manifest = authority_manifest_for(page_manifest, page_routes)
incomplete_docling_document = PagewiseDoclingFusionService().merge(
    document_id=source_document.document_id,
    canonical_version_id="CVER-M004-T005",
    source_sha256=source_document.fingerprint,
    original_storage_ref=source_document.original_storage_ref,
    page_manifest=manifest_for(5),
    page_outputs=(
        artifact(1, PageRouteName.NATIVE_STANDARD),
        artifact(2, PageRouteName.NATIVE_STANDARD),
        artifact(3, PageRouteName.NATIVE_STANDARD),
        artifact(4, PageRouteName.SCAN_GRANITE, label=PageConversionItemLabel.TABLE, text="PERFORMANCE_TABLE_FULL_TEXT: 2020 -12.5"),
        artifact(5, PageRouteName.NATIVE_STANDARD, label=PageConversionItemLabel.TABLE, text="Performance 2021 8.0"),
    ),
)
acceptance_policy = CanonicalAcceptancePolicy(policy_version="canonical-quality-v1")
post_report = acceptance_policy.evaluate_post_conversion(
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    docling_document=incomplete_docling_document,
    findings=(
        PostConversionQualityFinding(
            code=QualityFindingCode.NUMERIC_INCONSISTENCY,
            page_number=PageNumber.from_value(5),
            item_id=incomplete_docling_document.pages[4].items[0].item_id,
            expected="8.0",
            actual="80",
            detail="Valeur numérique incohérente.",
        ),
        PostConversionQualityFinding(
            code=QualityFindingCode.NEGATIVE_SIGN_ALTERED,
            page_number=PageNumber.from_value(4),
            item_id=incomplete_docling_document.pages[3].items[0].item_id,
            expected="-12.5",
            actual="12.5",
            detail="Signe négatif altéré.",
        ),
        PostConversionQualityFinding(
            code=QualityFindingCode.INCOMPLETE_TABLE,
            page_number=PageNumber.from_value(5),
            item_id=incomplete_docling_document.pages[4].items[0].item_id,
            expected="colonnes année et rendement",
            actual="colonne rendement seule",
            detail="Structure tabulaire incomplète.",
        ),
        PostConversionQualityFinding(
            code=QualityFindingCode.PERCENTAGE_ALTERED,
            page_number=PageNumber.from_value(5),
            item_id=incomplete_docling_document.pages[4].items[0].item_id,
            expected="8.0%",
            actual="80%",
            detail="Pourcentage altéré.",
        ),
        PostConversionQualityFinding(
            code=QualityFindingCode.DECIMAL_SEPARATOR_ALTERED,
            page_number=PageNumber.from_value(4),
            item_id=incomplete_docling_document.pages[3].items[0].item_id,
            expected="-12,5",
            actual="-125",
            detail="Séparateur décimal altéré.",
        ),
        PostConversionQualityFinding(
            code=QualityFindingCode.FIGURE_PROVENANCE_MISSING,
            page_number=PageNumber.from_value(6),
            item_id="PAGE-006-FIGURE",
            expected="SourceLocator figure",
            actual="ABSENT",
            detail="Figure critique sans provenance.",
        ),
    ),
)

# Then la version canonique candidate est refusée avec anomalies explicites et sans événement de publication.
decision = acceptance_policy.decide(
    source_document=source_document,
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    pre_conversion_report=pre_report,
    post_conversion_report=post_report,
)
finding_codes = tuple(finding.code for finding in decision.findings)
assert_equal(decision.publication_allowed, False, "Une QA RED doit bloquer la publication.")
assert_equal(decision.status, QualityDecisionStatus.RETRY_WITH_ALTERNATIVE_ROUTE, "La relance de route doit rester visible dans la décision finale.")
assert_equal(decision.publication_events, (), "Aucun événement de publication ne doit être produit.")
assert_true(QualityFindingCode.PAGE_OMITTED in finding_codes, "La page omise doit être refusée.")
assert_true(QualityFindingCode.NUMERIC_INCONSISTENCY in finding_codes, "L'incohérence numérique doit être conservée.")
assert_true(QualityFindingCode.NEGATIVE_SIGN_ALTERED in finding_codes, "Le signe altéré doit être conservé.")
assert_true(QualityFindingCode.INCOMPLETE_TABLE in finding_codes, "Le tableau incomplet doit être conservé.")
assert_true(QualityFindingCode.PERCENTAGE_ALTERED in finding_codes, "Le pourcentage altéré doit être conservé.")
assert_true(QualityFindingCode.DECIMAL_SEPARATOR_ALTERED in finding_codes, "Le séparateur décimal altéré doit être conservé.")
assert_true(QualityFindingCode.FIGURE_PROVENANCE_MISSING in finding_codes, "La figure sans provenance doit être conservée.")
assert_true(
    "PERFORMANCE_TABLE_FULL_TEXT" not in str(decision.to_audit_payload()),
    "Le payload d'audit ne doit pas journaliser le contenu documentaire complet.",
)

assert_raises(
    "obligatoire",
    lambda: acceptance_policy.decide(
        source_document=source_document,
        page_manifest=page_manifest,
        text_authority_manifest=authority_manifest,
        pre_conversion_report=None,
        post_conversion_report=post_report,
    ),
)
assert_raises(
    "post-conversion",
    lambda: acceptance_policy.decide(
        source_document=source_document,
        page_manifest=page_manifest,
        text_authority_manifest=authority_manifest,
        pre_conversion_report=pre_report,
        post_conversion_report=None,
    ),
)

quarantine_decision = acceptance_policy.decide(
    source_document=source_document.quarantine("Quarantaine explicite avant publication canonique."),
    page_manifest=page_manifest,
    text_authority_manifest=authority_manifest,
    pre_conversion_report=pre_report,
    post_conversion_report=post_report,
)
assert_equal(quarantine_decision.status, QualityDecisionStatus.QUARANTINE, "Une source quarantinée doit rester non publiable.")
assert_true(QualityFindingCode.SOURCE_QUARANTINED in tuple(finding.code for finding in quarantine_decision.findings), "La quarantaine doit être conservée en anomalie.")
assert_equal(quarantine_decision.publication_allowed, False, "Une source quarantinée ne doit jamais être publiée.")

print("Test d'acceptation T-005 qualité canonique M-004: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m004_canonical_quality_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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

Write-Host "Test d'acceptation T-005 qualité canonique M-004: OK"
