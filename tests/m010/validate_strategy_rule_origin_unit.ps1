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
    RuleExpression,
    RuleOrigin,
    RuleOriginPolicy,
    RuleOriginType,
    StrategyRule,
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


def assert_policy_code(origin, expected_code):
    rule = StrategyRule.with_origin(
        rule_id="STRAT-UNIT-RULE-ORIGIN-RULE-001",
        rule_kind="ENTRY",
        expression=RuleExpression.from_text("trend_60d > 0"),
        origin=origin,
    )
    diagnostics = RuleOriginPolicy().validate_rule(rule)
    assert any(
        diagnostic.code == expected_code
        and diagnostic.blocking
        and diagnostic.rule_id == "STRAT-UNIT-RULE-ORIGIN-RULE-001"
        for diagnostic in diagnostics
    )


valid_origins = (
    RuleOrigin.source(
        verified_claim_refs=("CLM-UNIT-RULE-ORIGIN@1",),
        evidence_refs=(),
    ),
    RuleOrigin.deduction(
        premises=("CLM-UNIT-RULE-ORIGIN@1", "mandate:risk_limit"),
        transformation="Transformer la tendance observee en filtre d'entree.",
    ),
    RuleOrigin.design_choice(
        justification="Limiter la frequence d'entree pour reduire le turnover operationnel.",
        mandate_impact="Compatible avec l'horizon swing du mandat.",
    ),
    RuleOrigin.parameter_to_calibrate(
        calibration_domain={
            "name": "lookback_days",
            "lower": 20,
            "upper": 120,
            "unit": "trading_day",
        },
        calibration_protocol="walk_forward_sans_selection_sur_test_final",
    ),
    RuleOrigin.user_constraint(
        mandate_refs=("mandate:risk_limit",),
    ),
)

for origin in valid_origins:
    rule = StrategyRule.with_origin(
        rule_id=f"STRAT-UNIT-RULE-ORIGIN-RULE-{origin.origin_type.value}",
        rule_kind="ENTRY",
        expression=RuleExpression.from_text("trend_60d > 0"),
        origin=origin,
    )
    assert RuleOriginPolicy().validate_rule(rule) == ()

expect_raises(
    "origine de regle inconnue",
    lambda: RuleOrigin.from_payload({"origin_type": "MODEL_GUESS"}),
)
expect_raises(
    "origin_type libre interdit",
    lambda: RuleOrigin(
        origin_type="SOURCE",
        verified_claim_refs=("CLM-UNIT-RULE-ORIGIN@1",),
        evidence_refs=(),
        premises=(),
        transformation=None,
        justification=None,
        mandate_impact=None,
        calibration_domain=None,
        calibration_protocol=None,
        mandate_refs=(),
    ),
)

rule_without_origin = StrategyRule.without_origin(
    rule_id="STRAT-UNIT-RULE-ORIGIN-RULE-NONE",
    rule_kind="ENTRY",
    expression=RuleExpression.from_text("trend_60d > 0"),
)
missing_origin_diagnostics = RuleOriginPolicy().validate_rule(rule_without_origin)
assert any(
    diagnostic.code == "RULE_ORIGIN_REQUIRED"
    and diagnostic.blocking
    and diagnostic.rule_id == "STRAT-UNIT-RULE-ORIGIN-RULE-NONE"
    for diagnostic in missing_origin_diagnostics
)

assert_policy_code(
    RuleOrigin.source(verified_claim_refs=(), evidence_refs=()),
    "SOURCE_EVIDENCE_REQUIRED",
)
assert_policy_code(
    RuleOrigin.source(verified_claim_refs=("CLM-UNIT-RULE-ORIGIN",), evidence_refs=()),
    "SOURCE_EVIDENCE_REQUIRED",
)
assert_policy_code(
    RuleOrigin.deduction(
        premises=(),
        transformation="Transformer la tendance observee en filtre d'entree.",
    ),
    "RULE_ORIGIN_REQUIRED",
)
assert_policy_code(
    RuleOrigin.design_choice(
        justification="",
        mandate_impact="Compatible avec l'horizon swing du mandat.",
    ),
    "DESIGN_CHOICE_JUSTIFICATION_REQUIRED",
)
assert_policy_code(
    RuleOrigin.parameter_to_calibrate(
        calibration_domain={},
        calibration_protocol="walk_forward_sans_selection_sur_test_final",
    ),
    "PARAMETER_CALIBRATION_REQUIRED",
)
assert_policy_code(
    RuleOrigin.user_constraint(mandate_refs=()),
    "STRATEGY_MANDATE_REQUIRED",
)

assert RuleOriginType.SOURCE.value == "SOURCE"

print("Tests unitaires des origines de regles de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_rule_origin_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires des origines de regles de strategie M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
