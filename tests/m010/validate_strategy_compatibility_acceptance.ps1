$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.strategy_design.adapters.in_memory_strategy_candidate_repository import (
    InMemoryStrategyCandidateRepository,
)
from app.strategy_design.adapters.research_outcome_translator import (
    StrategyDesignResearchOutcomeTranslator,
)
from app.strategy_design.application.create_strategy_candidate import (
    CreateStrategyCandidateCommand,
    CreateStrategyCandidateHandler,
)
from app.strategy_design.application.manage_strategy_rules import (
    AddStrategyRuleCommand,
    AddStrategyRuleHandler,
    AssignRuleOriginCommand,
    AssignRuleOriginHandler,
)
from app.strategy_design.domain.strategy_candidate import (
    CompatibilityFindingCode,
    DataAvailability,
    DataRequirement,
    ExecutionProfile,
    PointInTimeDataPolicy,
    ExecutionFeasibilityPolicy,
    RuleOrigin,
    StrategyCandidateStatus,
    StrategyCompatibilityAnalyzer,
    StrategyCompatibilityContext,
    StrategyCompatibilityPolicy,
)


class StubVerifiedResearchReader:
    def __init__(self, outcome):
        self._outcome = outcome

    def read_verified_research(self, research_case_id, answer_id):
        assert research_case_id == self._outcome.research_case_id
        assert answer_id == self._outcome.answer_id
        return self._outcome


class StubDataAvailabilityCatalog:
    def __init__(self, availability_by_requirement_id):
        self._availability_by_requirement_id = dict(availability_by_requirement_id)
        self.calls = []

    def availability_for(self, requirement):
        self.calls.append(requirement.requirement_id)
        return self._availability_by_requirement_id[requirement.requirement_id]


class StubMarketCalendarCatalog:
    def __init__(self, calendar_ids):
        self._calendar_ids = frozenset(calendar_ids)
        self.calls = []

    def has_calendar(self, calendar_id):
        self.calls.append(calendar_id)
        return calendar_id in self._calendar_ids


def build_outcome():
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-COMPATIBILITY",
            "question": "Le signal quotidien peut-il utiliser une donnée mensuelle publiée après décision ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
                "max_leverage": 1.0,
                "max_liquidity_usage": 0.25,
                "max_turnover": 0.35,
                "allowed_evidence_scope_refs": ["CLM-COMPATIBILITY@1"],
            },
            "answer_id": "ANS-COMPATIBILITY",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-COMPATIBILITY@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-03T12:00:00Z",
        }
    )


outcome = build_outcome()
repository = InMemoryStrategyCandidateRepository.empty()
create_handler = CreateStrategyCandidateHandler(
    verified_research_reader=StubVerifiedResearchReader(outcome),
    translator=StrategyDesignResearchOutcomeTranslator(),
    repository=repository,
)
candidate = create_handler.handle(
    CreateStrategyCandidateCommand(
        strategy_id="STRAT-COMPATIBILITY",
        research_case_id="RSC-COMPATIBILITY",
        answer_id="ANS-COMPATIBILITY",
        expected_version=0,
    )
)

candidate_with_rule = AddStrategyRuleHandler(repository=repository).handle(
    AddStrategyRuleCommand(
        strategy_id="STRAT-COMPATIBILITY",
        expected_version=candidate.version,
        rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
        rule_kind="SIGNAL",
        expression="cpi_yoy > moving_average(cpi_yoy, 12)",
    )
)

candidate_with_origin = AssignRuleOriginHandler(repository=repository).handle(
    AssignRuleOriginCommand(
        strategy_id="STRAT-COMPATIBILITY",
        expected_version=candidate_with_rule.version,
        rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
        origin=RuleOrigin.source(
            verified_claim_refs=("CLM-COMPATIBILITY@1",),
            evidence_refs=(),
        ),
    )
)

data_catalog = StubDataAvailabilityCatalog(
    {
        "DATA-CPI-MONTHLY": DataAvailability(
            requirement_id="DATA-CPI-MONTHLY",
            available_at="2026-03-16T14:00:00Z",
        )
    }
)
calendar_catalog = StubMarketCalendarCatalog(("XNYS",))

analyzer = StrategyCompatibilityAnalyzer(
    policy=StrategyCompatibilityPolicy(
        point_in_time_policy=PointInTimeDataPolicy(
            data_availability_catalog=data_catalog,
        ),
        execution_feasibility_policy=ExecutionFeasibilityPolicy(
            market_calendar_catalog=calendar_catalog,
        ),
    )
)

context = StrategyCompatibilityContext(
    rule_id="STRAT-COMPATIBILITY-RULE-SIGNAL",
    decision_at="2026-03-15T14:00:00Z",
    data_requirements=(
        DataRequirement(
            requirement_id="DATA-CPI-MONTHLY",
            data_name="cpi_yoy",
            frequency="MONTHLY",
            evidence_scope_refs=("CLM-COMPATIBILITY@1",),
        ),
    ),
    execution=ExecutionProfile(
        signal_horizon="DAILY",
        holding_horizon="SWING",
        decision_frequency="DAILY",
        calendar_id="XNYS",
        cost_model_id=None,
        expected_turnover=0.40,
        expected_liquidity_usage=0.20,
        expected_leverage=1.25,
    ),
)

# Given une règle de signal quotidien utilise une donnée mensuelle publiée après le moment de décision.
# When l'analyse de compatibilité est exécutée.
inconsistent_candidate = analyzer.analyze(
    candidate_with_origin,
    context=context,
    expected_version=candidate_with_origin.version,
)

# Then les findings bloquants rendent la stratégie non compilable sans backtest ni fallback de calendrier.
assert inconsistent_candidate.status == StrategyCandidateStatus.INCONSISTENT
assert inconsistent_candidate.status != "COMPILABLE"
assert any(
    finding.code is CompatibilityFindingCode.POINT_IN_TIME_VIOLATION
    and finding.blocking
    and finding.rule_id == "STRAT-COMPATIBILITY-RULE-SIGNAL"
    for finding in inconsistent_candidate.compatibility_findings
)
assert any(
    diagnostic.code == "POINT_IN_TIME_VIOLATION"
    and diagnostic.blocking
    and diagnostic.rule_id == "STRAT-COMPATIBILITY-RULE-SIGNAL"
    for diagnostic in inconsistent_candidate.compilation_diagnostics
)
assert any(
    finding.code is CompatibilityFindingCode.IMPLICIT_COST_MODEL
    for finding in inconsistent_candidate.compatibility_findings
)
assert any(
    finding.code is CompatibilityFindingCode.LEVERAGE_CONSTRAINT_VIOLATION
    for finding in inconsistent_candidate.compatibility_findings
)
assert data_catalog.calls == ["DATA-CPI-MONTHLY"]
assert calendar_catalog.calls == ["XNYS"]

print("Test d'acceptation de compatibilité de stratégie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_compatibility_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation de compatibilité de stratégie M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
