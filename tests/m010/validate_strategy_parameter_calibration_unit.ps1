$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.strategy_design.domain.strategy_candidate import (
    ParameterCalibrationPolicy,
    ParameterDomain,
    RuleOriginType,
    StrategyParameter,
    ValidationPlan,
)


def expect_raises(expected_fragment, action):
    try:
        action()
    except Exception as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"Erreur inattendue. Fragment attendu: {expected_fragment}. Erreur: {exc}"
            ) from exc
        return exc
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


policy = ParameterCalibrationPolicy()

fixed_parameter = StrategyParameter.fixed_value(
    parameter_id="PARAM-FIXED-RISK",
    name="risk_budget",
    value=0.25,
    origin_type=RuleOriginType.DESIGN_CHOICE,
    blocking=True,
)
assert policy.validate_parameter(fixed_parameter) == ()
assert fixed_parameter.resolution_status == "RESOLVED"

domain = ParameterDomain.from_bounds(
    lower_bound=20,
    upper_bound=120,
    unit="TRADING_DAY",
)
assert domain.unit == "trading_day"
assert domain.to_payload() == {
    "lower_bound": 20,
    "upper_bound": 120,
    "unit": "trading_day",
}

plan = ValidationPlan(
    calibration_protocol="walk_forward_sans_selection_sur_test_final",
    expected_sensitivity="Verifier la stabilite du lookback par regime de volatilite.",
)
calibrated_parameter = StrategyParameter.to_calibrate(
    parameter_id="PARAM-LOOKBACK-RESOLVED",
    name="lookback_days",
    domain=domain,
    validation_plan=plan,
    blocking=True,
)
assert policy.validate_parameter(calibrated_parameter) == ()
assert calibrated_parameter.resolution_status == "RESOLVED"

unresolved_blocking_parameter = StrategyParameter.unresolved(
    parameter_id="PARAM-LOOKBACK-UNRESOLVED",
    name="lookback_days",
    origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
    blocking=True,
    unresolved_reason="Domaine de recherche absent dans la source.",
)
blocking_diagnostics = policy.validate_parameter(unresolved_blocking_parameter)
assert any(
    diagnostic.code == "PARAMETER_CALIBRATION_REQUIRED"
    and diagnostic.blocking
    and diagnostic.parameter_id == "PARAM-LOOKBACK-UNRESOLVED"
    for diagnostic in blocking_diagnostics
)

non_blocking_parameter = StrategyParameter.unresolved(
    parameter_id="PARAM-NON-BLOCKING",
    name="commentary_window",
    origin_type=RuleOriginType.DESIGN_CHOICE,
    blocking=False,
    unresolved_reason="Parametre informatif non utilise par la compilation M-010.",
)
assert policy.validate_parameter(non_blocking_parameter) == ()

expect_raises(
    "domaine de calibration vide",
    lambda: ParameterDomain.from_payload({}),
)
expect_raises(
    "borne basse superieure ou egale a la borne haute",
    lambda: ParameterDomain.from_bounds(
        lower_bound=120,
        upper_bound=20,
        unit="trading_day",
    ),
)
expect_raises(
    "protocole de calibration vide",
    lambda: ValidationPlan(
        calibration_protocol="",
        expected_sensitivity="Verifier la stabilite du lookback.",
    ),
)
expect_raises(
    "sensibilite attendue vide",
    lambda: ValidationPlan(
        calibration_protocol="walk_forward_sans_selection_sur_test_final",
        expected_sensitivity="",
    ),
)
expect_raises(
    "parametre sans valeur, domaine ni raison de non-resolution",
    lambda: StrategyParameter(
        parameter_id="PARAM-INVALID",
        name="lookback_days",
        origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
        value=None,
        domain=None,
        validation_plan=None,
        blocking=True,
        resolution_status="UNRESOLVED",
        unresolved_reason=None,
    ),
)
expect_raises(
    "origin_type de parametre invalide",
    lambda: StrategyParameter.fixed_value(
        parameter_id="PARAM-INVALID-ORIGIN",
        name="risk_budget",
        value=0.25,
        origin_type="DESIGN_CHOICE",
        blocking=True,
    ),
)

print("Tests unitaires des parametres de calibration de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_parameter_calibration_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires des parametres de calibration de strategie M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
