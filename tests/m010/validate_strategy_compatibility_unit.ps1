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
    CompatibilityFinding,
    CompatibilityFindingCode,
    DataAvailability,
    DataRequirement,
    ExecutionFeasibilityPolicy,
    ExecutionProfile,
    PointInTimeDataPolicy,
    StrategyCompatibilityContext,
    StrategyCompatibilityPolicy,
    StrategyMandate,
)


class StubDataAvailabilityCatalog:
    def __init__(self, availability_by_requirement_id):
        self._availability_by_requirement_id = dict(availability_by_requirement_id)

    def availability_for(self, requirement):
        return self._availability_by_requirement_id[requirement.requirement_id]


class StubMarketCalendarCatalog:
    def __init__(self, calendar_ids):
        self._calendar_ids = frozenset(calendar_ids)

    def has_calendar(self, calendar_id):
        return calendar_id in self._calendar_ids


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


mandate = StrategyMandate.from_payload(
    {
        "universe": "ETF_US_TREASURY",
        "horizon": "swing",
        "risk_limit": "drawdown_10pct",
        "max_leverage": 1.0,
        "max_liquidity_usage": 0.25,
        "max_turnover": 0.35,
        "allowed_evidence_scope_refs": ["CLM-COMPATIBILITY@1"],
    }
)

late_monthly_requirement = DataRequirement(
    requirement_id="DATA-CPI-MONTHLY",
    data_name="cpi_yoy",
    frequency="MONTHLY",
    evidence_scope_refs=("CLM-COMPATIBILITY@1",),
)
daily_requirement = DataRequirement(
    requirement_id="DATA-PRICE-DAILY",
    data_name="close_price",
    frequency="DAILY",
    evidence_scope_refs=("CLM-COMPATIBILITY@1",),
)
out_of_scope_requirement = DataRequirement(
    requirement_id="DATA-OTHER-SCOPE",
    data_name="other_claim_feature",
    frequency="DAILY",
    evidence_scope_refs=("CLM-OTHER-SCOPE@9",),
)

point_in_time_policy = PointInTimeDataPolicy(
    data_availability_catalog=StubDataAvailabilityCatalog(
        {
            "DATA-CPI-MONTHLY": DataAvailability(
                requirement_id="DATA-CPI-MONTHLY",
                available_at="2026-03-16T14:00:00Z",
            ),
            "DATA-PRICE-DAILY": DataAvailability(
                requirement_id="DATA-PRICE-DAILY",
                available_at="2026-03-15T13:59:00Z",
            ),
            "DATA-OTHER-SCOPE": DataAvailability(
                requirement_id="DATA-OTHER-SCOPE",
                available_at="2026-03-15T13:59:00Z",
            ),
        }
    )
)

pit_findings = point_in_time_policy.evaluate(
    rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
    decision_at="2026-03-15T14:00:00Z",
    data_requirements=(late_monthly_requirement, daily_requirement),
    signal_horizon="DAILY",
)
assert any(
    finding.code is CompatibilityFindingCode.POINT_IN_TIME_VIOLATION
    and finding.blocking
    and finding.rule_id == "STRAT-COMPATIBILITY-RULE-SIGNAL"
    for finding in pit_findings
)
assert any(
    finding.code is CompatibilityFindingCode.DATA_FREQUENCY_INCOMPATIBLE
    and finding.blocking
    for finding in pit_findings
)
assert all(finding.parameter_id is None for finding in pit_findings)

execution_policy = ExecutionFeasibilityPolicy(
    market_calendar_catalog=StubMarketCalendarCatalog(("XNYS",))
)
execution_findings = execution_policy.evaluate(
    rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
    mandate=mandate,
    execution=ExecutionProfile(
        signal_horizon="DAILY",
        holding_horizon="SWING",
        decision_frequency="DAILY",
        calendar_id="XPAR",
        cost_model_id=None,
        expected_turnover=0.40,
        expected_liquidity_usage=0.30,
        expected_leverage=1.25,
    ),
)
expected_execution_codes = {
    CompatibilityFindingCode.CALENDAR_UNAVAILABLE,
    CompatibilityFindingCode.IMPLICIT_COST_MODEL,
    CompatibilityFindingCode.TURNOVER_CONSTRAINT_VIOLATION,
    CompatibilityFindingCode.LIQUIDITY_CONSTRAINT_VIOLATION,
    CompatibilityFindingCode.LEVERAGE_CONSTRAINT_VIOLATION,
}
assert expected_execution_codes.issubset({finding.code for finding in execution_findings})

compatibility_policy = StrategyCompatibilityPolicy(
    point_in_time_policy=point_in_time_policy,
    execution_feasibility_policy=execution_policy,
)
context = StrategyCompatibilityContext(
    rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
    decision_at="2026-03-15T14:00:00Z",
    data_requirements=(daily_requirement, out_of_scope_requirement),
    execution=ExecutionProfile(
        signal_horizon="DAILY",
        holding_horizon="INTRADAY",
        decision_frequency="DAILY",
        calendar_id="XNYS",
        cost_model_id="explicit_spread_commission_model_v1",
        expected_turnover=0.20,
        expected_liquidity_usage=0.20,
        expected_leverage=0.75,
    ),
)
policy_findings = compatibility_policy.evaluate(mandate=mandate, context=context)
assert any(
    finding.code is CompatibilityFindingCode.HORIZON_MISMATCH
    and finding.blocking
    for finding in policy_findings
)
assert any(
    finding.code is CompatibilityFindingCode.EVIDENCE_SCOPE_MISMATCH
    and finding.blocking
    for finding in policy_findings
)

typed_finding = CompatibilityFinding(
    code=CompatibilityFindingCode.POINT_IN_TIME_VIOLATION,
    description="La donnée est publiée après le moment de décision.",
    blocking=True,
    rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
    parameter_id=None,
)
diagnostic = typed_finding.to_diagnostic()
assert diagnostic.code == "POINT_IN_TIME_VIOLATION"
assert diagnostic.blocking
assert diagnostic.rule_id == "STRAT-COMPATIBILITY-RULE-SIGNAL"

expect_raises(
    "code finding compatibilité libre interdit",
    lambda: CompatibilityFinding(
        code="POINT_IN_TIME_VIOLATION",
        description="La donnée est publiée après le moment de décision.",
        blocking=True,
        rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
        parameter_id=None,
    ),
)
expect_raises(
    "finding de compatibilité à cible multiple",
    lambda: CompatibilityFinding(
        code=CompatibilityFindingCode.POINT_IN_TIME_VIOLATION,
        description="La donnée est publiée après le moment de décision.",
        blocking=True,
        rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
        parameter_id="PARAM-LOOKBACK",
    ),
)
expect_raises(
    "coût attendu invalide",
    lambda: ExecutionProfile(
        signal_horizon="DAILY",
        holding_horizon="SWING",
        decision_frequency="DAILY",
        calendar_id="XNYS",
        cost_model_id="explicit_spread_commission_model_v1",
        expected_turnover=-0.10,
        expected_liquidity_usage=0.20,
        expected_leverage=0.75,
    ),
)

print("Tests unitaires de compatibilité de stratégie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_compatibility_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires de compatibilité de stratégie M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
