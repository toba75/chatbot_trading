$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from pathlib import Path

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.document_route_benchmark import (
    DocumentRouteBenchmark,
    DocumentRouteOutput,
    REQUIRED_DOCUMENT_ROUTES,
    REQUIRED_ROUTE_METRICS,
    RouteBenchmarkLedger,
    RouteMetric,
    calculate_character_error_rate,
    calculate_word_error_rate,
)
from app.evaluation.domain.page_annotation import (
    AnnotationSet,
    CriticalNumericValue,
    PageAnnotation,
    PageReference,
    ReadingOrderItem,
    TableCellAnnotation,
)
from app.evaluation.domain.pilot_corpus import PilotCorpus, PilotDocument


HASH = "b" * 64


def page_ref():
    return PageReference(
        pilot_document_id="PDOC-M012-UNIT-BENCH",
        source_document_id="DOC-M012-UNIT-BENCH",
        canonical_version_id="CVER-M012-UNIT-BENCH",
        page_pdf=1,
    )


def corpus(strata=frozenset({"EQUATIONS", "FINANCIAL_TABLES"})):
    return PilotCorpus(
        corpus_id="PCORP-M012-UNIT-BENCH",
        policy_version="PilotCorpusCoveragePolicy-1.0",
        frozen_at="2026-07-06T00:00:00Z",
        documents=(
            PilotDocument(
                pilot_document_id="PDOC-M012-UNIT-BENCH",
                source_document_id="DOC-M012-UNIT-BENCH",
                original_path=Path(__file__),
                original_sha256=HASH,
                source_processing_status="DIAGNOSED_ROUTED_CANONICAL_PUBLISHED",
                source_processing_ref={
                    "document_id": "DOC-M012-UNIT-BENCH",
                    "diagnostic_run_id": "SPRUN-M012-UNIT-BENCH",
                    "route_plan_id": "RPLAN-M012-UNIT-BENCH",
                    "canonical_version_id": "CVER-M012-UNIT-BENCH",
                    "canonical_artifact_sha256": HASH,
                },
                strata=strata,
                edition_family_id="EDITION-M012-UNIT-BENCH",
                edition_label="2026",
                inclusion_justification="Document unitaire pour benchmark documentaire.",
            ),
        ),
        exclusions=(),
        frozen_manifest_sha256=HASH,
    )


def annotation_set():
    return AnnotationSet(
        annotation_set_id="ASET-M012-UNIT-BENCH",
        corpus_id="PCORP-M012-UNIT-BENCH",
        policy_version="AnnotationCompletenessPolicy-1.0",
        annotation_version="ANN-M012-UNIT-BENCH",
        frozen_at="2026-07-06T00:00:00Z",
        replaces_annotation_set_id=None,
        historical_annotation_versions=(),
        benchmark_pages=(page_ref(),),
        annotations=(
            PageAnnotation(
                annotation_id="PANN-M012-UNIT-BENCH",
                page_ref=page_ref(),
                annotation_version="ANN-M012-UNIT-BENCH",
                annotation_author_type="HUMAN_REVIEWER",
                generated_by_evaluated_system=False,
                expected_state="EVALUABLE",
                expected_route="OCR_WITH_TABLES",
                reference_transcription="Résultat -12,50 % avec formule A=B+C.",
                empty_or_rejection_reason=None,
                critical_numeric_values=(
                    CriticalNumericValue(
                        value_id="NUM-M012-UNIT-BENCH",
                        signed_value="-12.50",
                        unit="%",
                        context="Résultat.",
                        provenance_zone_id="ZONE-M012-UNIT-BENCH",
                    ),
                ),
                table_cells=(
                    TableCellAnnotation(
                        table_id="TABLE-M012-UNIT-BENCH",
                        row_index=1,
                        column_index=1,
                        text="-12,50 %",
                        provenance_zone_id="ZONE-M012-UNIT-BENCH",
                    ),
                ),
                reading_order=(
                    ReadingOrderItem(
                        order_index=1,
                        role="paragraph",
                        provenance_zone_id="ZONE-M012-UNIT-BENCH",
                    ),
                    ReadingOrderItem(
                        order_index=2,
                        role="formula",
                        provenance_zone_id="ZONE-M012-UNIT-BENCH",
                    ),
                ),
                provenance_zones=(),
            ),
        ),
        frozen_annotation_sha256=HASH,
    )


def output(
    route_name,
    *,
    measured_text="Résultat -12,50 % avec formule A=B+C.",
    numeric_values=("-12.50",),
    formulas=("A=B+C",),
    table_cells=("-12,50 %",),
    reading_order_roles=("paragraph", "formula"),
    processing_time_seconds="1.000",
    memory_bytes=1024,
    status="SUCCESS",
    failure_reason=None,
):
    return DocumentRouteOutput(
        output_id=f"ROUT-M012-UNIT-{route_name.upper().replace(' ', '-')}",
        route_name=route_name,
        page_ref=page_ref(),
        route_policy_version="DocumentRouteBenchmarkPolicy-1.0",
        measured_text=measured_text,
        numeric_values=numeric_values,
        formulas=formulas,
        table_cells=table_cells,
        reading_order_roles=reading_order_roles,
        processing_time_seconds=processing_time_seconds,
        memory_bytes=memory_bytes,
        status=status,
        failure_reason=failure_reason,
    )


def outputs_for_all_routes(**first_route_overrides):
    payload = {}
    for route_name in REQUIRED_DOCUMENT_ROUTES:
        overrides = first_route_overrides if route_name == "Docling standard" else {}
        payload[route_name] = (output(route_name, **overrides),)
    return payload


def benchmark(**kwargs):
    return DocumentRouteBenchmark(policy_version="DocumentRouteBenchmarkPolicy-1.0").measure(
        run_id="RBRUN-M012-UNIT-BENCH",
        corpus=corpus(),
        annotation_set=annotation_set(),
        route_outputs_by_route=outputs_for_all_routes(**kwargs),
    )


def docling_result(**kwargs):
    return benchmark(**kwargs).result_for_route("Docling standard")


def expect_raises(expected_fragment, action):
    try:
        action()
    except Exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"Erreur inattendue. Fragment attendu: {expected_fragment}. Erreur: {exc}"
            ) from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


assert calculate_character_error_rate("abc", "axc") == RouteMetric("document_cer", "0.333333333333", 1, 1)
assert calculate_word_error_rate("alpha beta", "alpha gamma") == RouteMetric("document_wer", "0.500000000000", 1, 1)

result = docling_result()
assert result.metrics["document_numeric_token_accuracy"].value == "1.000000000000"
assert result.metrics["document_sign_accuracy"].value == "1.000000000000"
assert result.metrics["document_formula_fidelity"].value == "1.000000000000"
assert result.metrics["document_cell_accuracy"].value == "1.000000000000"
assert result.metrics["document_reading_order_accuracy"].value == "1.000000000000"
assert result.metrics["document_page_time_seconds"].value == "1.000000000000"
assert result.metrics["document_memory_bytes"].value == "1024.000000000000"
assert result.metrics["document_route_stability_rate"].value == "1.000000000000"
assert set(REQUIRED_ROUTE_METRICS).issubset(result.metrics.keys())
assert set(result.strata_details.keys()) == {"EQUATIONS", "FINANCIAL_TABLES"}

assert docling_result(numeric_values=("+12.50",)).metrics["document_sign_accuracy"].value == "0.000000000000"
assert docling_result(numeric_values=("-99.00",)).metrics["document_numeric_token_accuracy"].value == "0.000000000000"
assert docling_result(formulas=("A=B-C",)).metrics["document_formula_fidelity"].value == "0.000000000000"
assert docling_result(table_cells=("-12,00 %",)).metrics["document_cell_accuracy"].value == "0.000000000000"
assert docling_result(reading_order_roles=("formula", "paragraph")).metrics["document_reading_order_accuracy"].value == "0.000000000000"
assert docling_result(status="FAILED", measured_text=None, numeric_values=(), formulas=(), table_cells=(), reading_order_roles=(), failure_reason="Échec contrôlé.").metrics["document_failure_rate"].value == "1.000000000000"

expect_raises("temps par page absent", lambda: output("Docling standard", processing_time_seconds=None))
expect_raises("memoire absente", lambda: output("Docling standard", memory_bytes=None))
expect_raises("route obligatoire absente", lambda: DocumentRouteBenchmark(policy_version="DocumentRouteBenchmarkPolicy-1.0").measure(run_id="RBRUN-M012-UNIT-MISSING", corpus=corpus(), annotation_set=annotation_set(), route_outputs_by_route={}))
expect_raises("strate vide", lambda: DocumentRouteBenchmark(policy_version="DocumentRouteBenchmarkPolicy-1.0").measure(run_id="RBRUN-M012-UNIT-STRATA", corpus=corpus(frozenset()), annotation_set=annotation_set(), route_outputs_by_route=outputs_for_all_routes()))
expect_raises("sortie manquante", lambda: DocumentRouteBenchmark(policy_version="DocumentRouteBenchmarkPolicy-1.0").measure(run_id="RBRUN-M012-UNIT-INCOMPLETE", corpus=corpus(), annotation_set=annotation_set(), route_outputs_by_route={"Docling standard": ()}))

duplicated_output = output("Docling standard")
expect_raises(
    "sortie dupliquee",
    lambda: DocumentRouteBenchmark(policy_version="DocumentRouteBenchmarkPolicy-1.0").measure(
        run_id="RBRUN-M012-UNIT-DUP",
        corpus=corpus(),
        annotation_set=annotation_set(),
        route_outputs_by_route={"Docling standard": (duplicated_output, duplicated_output)},
    ),
)

ledger = RouteBenchmarkLedger()
run = benchmark()
ledger.append(run)
expect_raises("resultat de benchmark duplique", lambda: ledger.append(run))

print("Tests unitaires T-005 benchmarks de routes documentaires M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_document_route_benchmark_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires T-005 benchmarks de routes documentaires M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
