$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.document_quality_calibration import (
    CALIBRATION_ACCEPTED,
    CALIBRATION_REJECTED,
    SOURCE_BENCHMARK_RESULT,
    THRESHOLD_MAXIMUM,
    THRESHOLD_MINIMUM,
    V1_GAP_BLOCKING,
    DocumentQualityCalibrationPolicy,
    DocumentQualityThreshold,
    DocumentQualityThresholdReport,
)
from app.evaluation.domain.document_route_benchmark import (
    DOCLING_STANDARD,
    DOUBLE_CONVERSION_ADJUDICATION,
    DOCUMENT_CELL_ACCURACY,
    DOCUMENT_CER,
    DOCUMENT_FAILURE_RATE,
    DOCUMENT_FORMULA_FIDELITY,
    DOCUMENT_MEMORY_BYTES,
    DOCUMENT_NUMERIC_TOKEN_ACCURACY,
    DOCUMENT_PAGE_TIME_SECONDS,
    DOCUMENT_READING_ORDER_ACCURACY,
    DOCUMENT_ROUTE_STABILITY_RATE,
    DOCUMENT_SIGN_ACCURACY,
    DOCUMENT_WER,
    GRANITE_DOCLING_DIRECT,
    PREPROCESSING_GRANITE_DOCLING,
    REQUIRED_DOCUMENT_ROUTES,
    REQUIRED_ROUTE_METRICS,
    RouteBenchmarkResult,
    RouteBenchmarkRun,
    RouteMetric,
    RouteStrataResult,
)


POLICY_VERSION = "DocumentQualityCalibrationPolicy-1.0"
RUN_ID = "RBRUN-M012-CALIBRATION-0001"
CORPUS_ID = "PCORP-M012-CALIBRATION"
ANNOTATION_SET_ID = "ASET-M012-CALIBRATION"
STRATA = ("FINANCIAL_TABLES", "EQUATIONS")


def metric(name, value):
    return RouteMetric(name=name, value=value, numerator=1, denominator=1)


def metrics(**overrides):
    values = {
        DOCUMENT_CER: "0.010000000000",
        DOCUMENT_WER: "0.020000000000",
        DOCUMENT_NUMERIC_TOKEN_ACCURACY: "0.990000000000",
        DOCUMENT_SIGN_ACCURACY: "1.000000000000",
        DOCUMENT_FORMULA_FIDELITY: "0.980000000000",
        DOCUMENT_CELL_ACCURACY: "0.970000000000",
        DOCUMENT_READING_ORDER_ACCURACY: "0.990000000000",
        DOCUMENT_PAGE_TIME_SECONDS: "2.000000000000",
        DOCUMENT_MEMORY_BYTES: "2048.000000000000",
        DOCUMENT_ROUTE_STABILITY_RATE: "1.000000000000",
        DOCUMENT_FAILURE_RATE: "0.000000000000",
    }
    values.update(overrides)
    return {name: metric(name, values[name]) for name in REQUIRED_ROUTE_METRICS}


def strata_details(route_name, **overrides_by_stratum):
    details = {}
    for stratum in STRATA:
        details[stratum] = RouteStrataResult(
            stratum=stratum,
            page_count=2,
            failed_page_count=0,
            metrics=metrics(**overrides_by_stratum.get(stratum, {})),
        )
    return details


def result(route_name, **overrides_by_stratum):
    route_metrics = metrics()
    if route_name == GRANITE_DOCLING_DIRECT:
        route_metrics = metrics(**{DOCUMENT_CELL_ACCURACY: "0.910000000000"})
    return RouteBenchmarkResult(
        result_id=f"{RUN_ID}:{route_name}",
        corpus_id=CORPUS_ID,
        annotation_set_id=ANNOTATION_SET_ID,
        route_name=route_name,
        policy_version="DocumentRouteBenchmarkPolicy-1.0",
        page_count=4,
        failed_page_count=0,
        metrics=route_metrics,
        strata_details=strata_details(route_name, **overrides_by_stratum),
        page_measurements=(),
    )


def benchmark_run():
    return RouteBenchmarkRun(
        run_id=RUN_ID,
        corpus_id=CORPUS_ID,
        annotation_set_id=ANNOTATION_SET_ID,
        policy_version="DocumentRouteBenchmarkPolicy-1.0",
        results=(
            result(DOCLING_STANDARD),
            result(
                GRANITE_DOCLING_DIRECT,
                FINANCIAL_TABLES={DOCUMENT_CELL_ACCURACY: "0.900000000000"},
            ),
            result(PREPROCESSING_GRANITE_DOCLING),
            result(DOUBLE_CONVERSION_ADJUDICATION),
        ),
    )


def threshold(route_name, metric_name, operator, value):
    return DocumentQualityThreshold(
        threshold_id=f"THR-M012-{route_name}-{metric_name}",
        policy_version=POLICY_VERSION,
        source_kind=SOURCE_BENCHMARK_RESULT,
        benchmark_result_id=f"{RUN_ID}:{route_name}",
        corpus_id=CORPUS_ID,
        route_name=route_name,
        metric_name=metric_name,
        operator=operator,
        value=value,
        justification_by_stratum={
            "FINANCIAL_TABLES": "Strate critique pour les cellules et signes financiers.",
            "EQUATIONS": "Strate critique pour les formules et l'ordre de lecture.",
        },
        v1_criterion_id=f"V1-DOCUMENT-{metric_name}",
    )


def threshold_report():
    thresholds = []
    for route_name in sorted(REQUIRED_DOCUMENT_ROUTES):
        thresholds.extend(
            (
                threshold(route_name, DOCUMENT_CER, THRESHOLD_MAXIMUM, "0.030000000000"),
                threshold(route_name, DOCUMENT_CELL_ACCURACY, THRESHOLD_MINIMUM, "0.950000000000"),
                threshold(route_name, DOCUMENT_FORMULA_FIDELITY, THRESHOLD_MINIMUM, "0.950000000000"),
            )
        )
    return DocumentQualityThresholdReport(
        report_id="SP-DOCUMENT-THRESHOLDS-M012-0001",
        policy_version=POLICY_VERSION,
        benchmark_run_id=RUN_ID,
        corpus_id=CORPUS_ID,
        thresholds=tuple(thresholds),
    )


# Given les routes documentaires ont ete mesurees sur le corpus pilote.
run = benchmark_run()
report = threshold_report()

# When les seuils de conversion canonique sont calibres.
decision = DocumentQualityCalibrationPolicy(policy_version=POLICY_VERSION).calibrate(
    decision_id="CAL-M012-DOCUMENT-0001",
    benchmark_run=run,
    threshold_report=report,
)

# Then chaque seuil publie conserve benchmark, corpus, version de politique et justification par strate.
assert decision.policy_version == POLICY_VERSION
assert decision.threshold_report.policy_version == POLICY_VERSION
for calibrated_threshold in decision.threshold_report.thresholds:
    assert calibrated_threshold.source_kind == SOURCE_BENCHMARK_RESULT
    assert calibrated_threshold.benchmark_result_id
    assert calibrated_threshold.corpus_id == CORPUS_ID
    assert calibrated_threshold.policy_version == POLICY_VERSION
    assert set(calibrated_threshold.justification_by_stratum) == set(STRATA)

# Then une route sous seuil n'est pas acceptee et l'ecart V1 documentaire reste visible.
diagnostics = {diagnostic.route_name: diagnostic for diagnostic in decision.route_diagnostics}
assert diagnostics[DOCLING_STANDARD].status == CALIBRATION_ACCEPTED
assert diagnostics[GRANITE_DOCLING_DIRECT].status == CALIBRATION_REJECTED
assert DOCUMENT_CELL_ACCURACY in diagnostics[GRANITE_DOCLING_DIRECT].blocking_metrics
assert all(diagnostic.status != CALIBRATION_ACCEPTED for diagnostic in decision.route_diagnostics if diagnostic.route_name == GRANITE_DOCLING_DIRECT)

cell_gaps = [
    gap for gap in decision.v1_gaps
    if gap.route_name == GRANITE_DOCLING_DIRECT and gap.metric_name == DOCUMENT_CELL_ACCURACY
]
assert len(cell_gaps) == 1
assert cell_gaps[0].status == V1_GAP_BLOCKING
assert cell_gaps[0].benchmark_result_id == f"{RUN_ID}:{GRANITE_DOCLING_DIRECT}"
assert cell_gaps[0].policy_version == POLICY_VERSION

print("Test d'acceptation T-006 calibration documentaire M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_document_quality_calibration_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-006 calibration documentaire M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
