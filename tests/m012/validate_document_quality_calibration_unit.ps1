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
    SOURCE_BENCHMARK_RESULT,
    SOURCE_DEVELOPMENT_VALUE,
    THRESHOLD_MAXIMUM,
    THRESHOLD_MINIMUM,
    DocumentQualityCalibrationPolicy,
    DocumentQualityThreshold,
    DocumentQualityThresholdReport,
)
from app.evaluation.domain.document_route_benchmark import (
    DOCLING_STANDARD,
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
    REQUIRED_ROUTE_METRICS,
    RouteBenchmarkResult,
    RouteBenchmarkRun,
    RouteMetric,
    RouteStrataResult,
)


POLICY_VERSION = "DocumentQualityCalibrationPolicy-1.0"
RUN_ID = "RBRUN-M012-CALIBRATION-UNIT"
CORPUS_ID = "PCORP-M012-CALIBRATION-UNIT"
ANNOTATION_SET_ID = "ASET-M012-CALIBRATION-UNIT"
STRATA = ("FINANCIAL_TABLES", "EQUATIONS")


def metric(name, value):
    return RouteMetric(name=name, value=value, numerator=1, denominator=1)


def metrics(**overrides):
    values = {
        DOCUMENT_CER: "0.010000000000",
        DOCUMENT_WER: "0.020000000000",
        DOCUMENT_NUMERIC_TOKEN_ACCURACY: "1.000000000000",
        DOCUMENT_SIGN_ACCURACY: "1.000000000000",
        DOCUMENT_FORMULA_FIDELITY: "1.000000000000",
        DOCUMENT_CELL_ACCURACY: "0.980000000000",
        DOCUMENT_READING_ORDER_ACCURACY: "1.000000000000",
        DOCUMENT_PAGE_TIME_SECONDS: "1.000000000000",
        DOCUMENT_MEMORY_BYTES: "1024.000000000000",
        DOCUMENT_ROUTE_STABILITY_RATE: "1.000000000000",
        DOCUMENT_FAILURE_RATE: "0.000000000000",
    }
    values.update(overrides)
    return {name: metric(name, values[name]) for name in REQUIRED_ROUTE_METRICS}


def benchmark_result(*, route_metric_overrides=None, strata_metric_overrides=None):
    strata_metric_overrides = strata_metric_overrides or {}
    return RouteBenchmarkResult(
        result_id=f"{RUN_ID}:{DOCLING_STANDARD}",
        corpus_id=CORPUS_ID,
        annotation_set_id=ANNOTATION_SET_ID,
        route_name=DOCLING_STANDARD,
        policy_version="DocumentRouteBenchmarkPolicy-1.0",
        page_count=2,
        failed_page_count=0,
        metrics=metrics(**(route_metric_overrides or {})),
        strata_details={
            stratum: RouteStrataResult(
                stratum=stratum,
                page_count=1,
                failed_page_count=0,
                metrics=metrics(**strata_metric_overrides.get(stratum, {})),
            )
            for stratum in STRATA
        },
        page_measurements=(),
    )


def benchmark_run(result):
    return RouteBenchmarkRun(
        run_id=RUN_ID,
        corpus_id=CORPUS_ID,
        annotation_set_id=ANNOTATION_SET_ID,
        policy_version="DocumentRouteBenchmarkPolicy-1.0",
        results=(result,),
    )


def threshold(**overrides):
    payload = {
        "threshold_id": "THR-M012-UNIT-CELL",
        "policy_version": POLICY_VERSION,
        "source_kind": SOURCE_BENCHMARK_RESULT,
        "benchmark_result_id": f"{RUN_ID}:{DOCLING_STANDARD}",
        "corpus_id": CORPUS_ID,
        "route_name": DOCLING_STANDARD,
        "metric_name": DOCUMENT_CELL_ACCURACY,
        "operator": THRESHOLD_MINIMUM,
        "value": "0.950000000000",
        "justification_by_stratum": {
            "FINANCIAL_TABLES": "Controle des tableaux financiers critiques.",
            "EQUATIONS": "Controle des pages avec equations.",
        },
        "v1_criterion_id": "V1-DOCUMENT-CELL-ACCURACY",
    }
    payload.update(overrides)
    return DocumentQualityThreshold(**payload)


def report(thresholds):
    return DocumentQualityThresholdReport(
        report_id="SP-DOCUMENT-THRESHOLDS-M012-UNIT",
        policy_version=POLICY_VERSION,
        benchmark_run_id=RUN_ID,
        corpus_id=CORPUS_ID,
        thresholds=tuple(thresholds),
    )


def decision(thresholds, result=None):
    return DocumentQualityCalibrationPolicy(policy_version=POLICY_VERSION).calibrate(
        decision_id="CAL-M012-DOCUMENT-UNIT",
        benchmark_run=benchmark_run(result or benchmark_result()),
        threshold_report=report(thresholds),
    )


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


expect_raises("benchmark source absent", lambda: threshold(benchmark_result_id=""))
expect_raises("corpus seuil incoherent", lambda: decision((threshold(corpus_id="PCORP-AUTRE"),)))
expect_raises("version de politique incoherente", lambda: threshold(policy_version="DocumentQualityCalibrationPolicy-2.0"))
expect_raises("justification par strate absente", lambda: threshold(justification_by_stratum={"FINANCIAL_TABLES": "Tableaux."}))
expect_raises("valeur de developpement non promouvable", lambda: threshold(source_kind=SOURCE_DEVELOPMENT_VALUE))
expect_raises("operateur de seuil inconnu", lambda: threshold(operator="APPROXIMATE"))
expect_raises("valeur de seuil invalide", lambda: threshold(value="pas-un-nombre"))

ok_decision = decision((threshold(), threshold(metric_name=DOCUMENT_CER, operator=THRESHOLD_MAXIMUM, value="0.030000000000", threshold_id="THR-M012-UNIT-CER", v1_criterion_id="V1-DOCUMENT-CER")))
assert ok_decision.v1_gaps == ()
assert ok_decision.route_diagnostics[0].status == "ACCEPTED"

bad_result = benchmark_result(strata_metric_overrides={"FINANCIAL_TABLES": {DOCUMENT_CELL_ACCURACY: "0.900000000000"}})
bad_decision = decision((threshold(),), result=bad_result)
assert bad_decision.route_diagnostics[0].status == "REJECTED"
assert bad_decision.v1_gaps[0].metric_name == DOCUMENT_CELL_ACCURACY
assert bad_decision.v1_gaps[0].stratum == "FINANCIAL_TABLES"

missing_metric_result = benchmark_result()
missing_metric_result.strata_details["EQUATIONS"].metrics.pop(DOCUMENT_CELL_ACCURACY)
missing_metric_decision = decision((threshold(),), result=missing_metric_result)
assert missing_metric_decision.route_diagnostics[0].status == "REJECTED"
assert missing_metric_decision.v1_gaps[0].reason.startswith("metrique documentaire absente")

print("Tests unitaires T-006 calibration documentaire M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_document_quality_calibration_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires T-006 calibration documentaire M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
