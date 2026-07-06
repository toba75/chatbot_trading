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


HASH = "a" * 64


def corpus():
    return PilotCorpus(
        corpus_id="PCORP-M012-BENCH",
        policy_version="PilotCorpusCoveragePolicy-1.0",
        frozen_at="2026-07-06T00:00:00Z",
        documents=(
            PilotDocument(
                pilot_document_id="PDOC-M012-BENCH-0001",
                source_document_id="DOC-M012-BENCH-0001",
                original_path=Path(__file__),
                original_sha256=HASH,
                source_processing_status="DIAGNOSED_ROUTED_CANONICAL_PUBLISHED",
                source_processing_ref={
                    "document_id": "DOC-M012-BENCH-0001",
                    "diagnostic_run_id": "SPRUN-M012-BENCH-0001",
                    "route_plan_id": "RPLAN-M012-BENCH-0001",
                    "canonical_version_id": "CVER-M012-BENCH-0001",
                    "canonical_artifact_sha256": HASH,
                },
                strata=frozenset({"FINANCIAL_TABLES", "FRENCH_TEXT"}),
                edition_family_id="EDITION-M012-BENCH",
                edition_label="2026",
                inclusion_justification="Document pilote pour benchmark de routes documentaires.",
            ),
        ),
        exclusions=(),
        frozen_manifest_sha256=HASH,
    )


def page_ref(page_pdf):
    return PageReference(
        pilot_document_id="PDOC-M012-BENCH-0001",
        source_document_id="DOC-M012-BENCH-0001",
        canonical_version_id="CVER-M012-BENCH-0001",
        page_pdf=page_pdf,
    )


def annotation_set():
    return AnnotationSet(
        annotation_set_id="ASET-M012-BENCH-0001",
        corpus_id="PCORP-M012-BENCH",
        policy_version="AnnotationCompletenessPolicy-1.0",
        annotation_version="ANN-M012-BENCH-0001",
        frozen_at="2026-07-06T00:00:00Z",
        replaces_annotation_set_id=None,
        historical_annotation_versions=(),
        benchmark_pages=(page_ref(1), page_ref(2)),
        annotations=(
            PageAnnotation(
                annotation_id="PANN-M012-BENCH-0001",
                page_ref=page_ref(1),
                annotation_version="ANN-M012-BENCH-0001",
                annotation_author_type="HUMAN_REVIEWER",
                generated_by_evaluated_system=False,
                expected_state="EVALUABLE",
                expected_route="OCR_WITH_TABLES",
                reference_transcription="Résultat net -12,50 % et formule A=B+C.",
                empty_or_rejection_reason=None,
                critical_numeric_values=(
                    CriticalNumericValue(
                        value_id="NUM-M012-BENCH-0001",
                        signed_value="-12.50",
                        unit="%",
                        context="Résultat net.",
                        provenance_zone_id="ZONE-M012-BENCH-0001",
                    ),
                ),
                table_cells=(
                    TableCellAnnotation(
                        table_id="TABLE-M012-BENCH-0001",
                        row_index=1,
                        column_index=1,
                        text="-12,50 %",
                        provenance_zone_id="ZONE-M012-BENCH-0001",
                    ),
                ),
                reading_order=(
                    ReadingOrderItem(
                        order_index=1,
                        role="paragraph",
                        provenance_zone_id="ZONE-M012-BENCH-0001",
                    ),
                    ReadingOrderItem(
                        order_index=2,
                        role="formula",
                        provenance_zone_id="ZONE-M012-BENCH-0001",
                    ),
                ),
                provenance_zones=(),
            ),
            PageAnnotation(
                annotation_id="PANN-M012-BENCH-0002",
                page_ref=page_ref(2),
                annotation_version="ANN-M012-BENCH-0001",
                annotation_author_type="HUMAN_REVIEWER",
                generated_by_evaluated_system=False,
                expected_state="EVALUABLE",
                expected_route="NATIVE_TEXT",
                reference_transcription="Chiffre d'affaires +42 EUR.",
                empty_or_rejection_reason=None,
                critical_numeric_values=(
                    CriticalNumericValue(
                        value_id="NUM-M012-BENCH-0002",
                        signed_value="+42",
                        unit="EUR",
                        context="Chiffre d'affaires.",
                        provenance_zone_id="ZONE-M012-BENCH-0002",
                    ),
                ),
                table_cells=(),
                reading_order=(
                    ReadingOrderItem(
                        order_index=1,
                        role="paragraph",
                        provenance_zone_id="ZONE-M012-BENCH-0002",
                    ),
                ),
                provenance_zones=(),
            ),
        ),
        frozen_annotation_sha256=HASH,
    )


def route_outputs(route_name, *, second_page_failed=False):
    outputs = [
        DocumentRouteOutput(
            output_id=f"ROUT-M012-{route_name.upper().replace(' ', '-').replace('+', 'PLUS')}-P1",
            route_name=route_name,
            page_ref=page_ref(1),
            route_policy_version="DocumentRouteBenchmarkPolicy-1.0",
            measured_text="Résultat net -12,50 % et formule A=B+C.",
            numeric_values=("-12.50",),
            formulas=("A=B+C",),
            table_cells=("-12,50 %",),
            reading_order_roles=("paragraph", "formula"),
            processing_time_seconds="1.250",
            memory_bytes=1048576,
            status="SUCCESS",
            failure_reason=None,
        )
    ]
    outputs.append(
        DocumentRouteOutput(
            output_id=f"ROUT-M012-{route_name.upper().replace(' ', '-').replace('+', 'PLUS')}-P2",
            route_name=route_name,
            page_ref=page_ref(2),
            route_policy_version="DocumentRouteBenchmarkPolicy-1.0",
            measured_text=None if second_page_failed else "Chiffre d'affaires +42 EUR.",
            numeric_values=() if second_page_failed else ("+42",),
            formulas=(),
            table_cells=(),
            reading_order_roles=() if second_page_failed else ("paragraph",),
            processing_time_seconds="2.000",
            memory_bytes=2097152,
            status="FAILED" if second_page_failed else "SUCCESS",
            failure_reason="Conversion impossible sur page pilote." if second_page_failed else None,
        )
    )
    return tuple(outputs)


def all_outputs():
    return {
        route_name: route_outputs(
            route_name,
            second_page_failed=route_name == "Granite-Docling direct",
        )
        for route_name in REQUIRED_DOCUMENT_ROUTES
    }


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


# Given un corpus pilote figé et un jeu annoté page par page.
benchmark = DocumentRouteBenchmark(policy_version="DocumentRouteBenchmarkPolicy-1.0")

# When les routes documentaires obligatoires sont mesurées.
run = benchmark.measure(
    run_id="RBRUN-M012-BENCH-0001",
    corpus=corpus(),
    annotation_set=annotation_set(),
    route_outputs_by_route=all_outputs(),
)

# Then chaque route publie les métriques normatives par strate et garde les échecs au dénominateur.
assert run.corpus_id == "PCORP-M012-BENCH"
assert run.annotation_set_id == "ASET-M012-BENCH-0001"
assert run.policy_version == "DocumentRouteBenchmarkPolicy-1.0"
assert {result.route_name for result in run.results} == set(REQUIRED_DOCUMENT_ROUTES)

direct = run.result_for_route("Granite-Docling direct")
assert direct.page_count == 2
assert direct.failed_page_count == 1
assert direct.metrics["document_failure_rate"].denominator == 2
assert direct.metrics["document_cer"].denominator == 2
assert direct.metrics["document_wer"].denominator == 2
assert direct.metrics["document_route_stability_rate"].denominator == 2
assert set(REQUIRED_ROUTE_METRICS).issubset(direct.metrics.keys())
assert set(direct.strata_details.keys()) == {"FINANCIAL_TABLES", "FRENCH_TEXT"}
assert direct.page_measurements[1].output_id.endswith("-P2")
assert direct.page_measurements[1].status == "FAILED"

for result in run.results:
    for metric_name in REQUIRED_ROUTE_METRICS:
        metric = result.metrics[metric_name]
        assert metric.denominator == result.page_count, metric_name
    assert result.strata_details, result.route_name
    for strata_result in result.strata_details.values():
        assert set(REQUIRED_ROUTE_METRICS).issubset(strata_result.metrics.keys())

missing_route_outputs = all_outputs()
del missing_route_outputs["Docling standard"]
expect_raises(
    "route obligatoire absente",
    lambda: benchmark.measure(
        run_id="RBRUN-M012-BENCH-0002",
        corpus=corpus(),
        annotation_set=annotation_set(),
        route_outputs_by_route=missing_route_outputs,
    ),
)

without_time = all_outputs()
bad_page = without_time["Docling standard"][0]
without_time["Docling standard"] = (
    DocumentRouteOutput(
        output_id=bad_page.output_id,
        route_name=bad_page.route_name,
        page_ref=bad_page.page_ref,
        route_policy_version=bad_page.route_policy_version,
        measured_text=bad_page.measured_text,
        numeric_values=bad_page.numeric_values,
        formulas=bad_page.formulas,
        table_cells=bad_page.table_cells,
        reading_order_roles=bad_page.reading_order_roles,
        processing_time_seconds=None,
        memory_bytes=bad_page.memory_bytes,
        status=bad_page.status,
        failure_reason=bad_page.failure_reason,
    ),
    without_time["Docling standard"][1],
)
expect_raises(
    "temps par page absent",
    lambda: benchmark.measure(
        run_id="RBRUN-M012-BENCH-0003",
        corpus=corpus(),
        annotation_set=annotation_set(),
        route_outputs_by_route=without_time,
    ),
)

ledger = RouteBenchmarkLedger()
ledger.append(run)
expect_raises("resultat de benchmark duplique", lambda: ledger.append(run))

print("Test d'acceptation T-005 benchmarks de routes documentaires M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_document_route_benchmark_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-005 benchmarks de routes documentaires M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
