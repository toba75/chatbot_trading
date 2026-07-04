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
from app.strategy_design.application.manage_strategy_parameters import (
    DeclareStrategyParameterCommand,
    DeclareStrategyParameterHandler,
    DefineCalibrationPlanCommand,
    DefineCalibrationPlanHandler,
)
from app.strategy_design.domain.strategy_candidate import (
    RuleOriginType,
    StrategyCandidateStatus,
)


class StubVerifiedResearchReader:
    def __init__(self, outcome):
        self._outcome = outcome

    def read_verified_research(self, research_case_id, answer_id):
        assert research_case_id == self._outcome.research_case_id
        assert answer_id == self._outcome.answer_id
        return self._outcome


def build_outcome():
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-PARAM-CALIBRATION",
            "question": "Le lookback de tendance doit-il etre calibre avant compilation ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": "ANS-PARAM-CALIBRATION",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-PARAM-CALIBRATION@2"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-03T11:00:00Z",
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
        strategy_id="STRAT-PARAM-CALIBRATION",
        research_case_id="RSC-PARAM-CALIBRATION",
        answer_id="ANS-PARAM-CALIBRATION",
        expected_version=0,
    )
)

declare_parameter_handler = DeclareStrategyParameterHandler(repository=repository)
define_plan_handler = DefineCalibrationPlanHandler(repository=repository)

# Given un lookback est declare PARAMETER_TO_CALIBRATE sans domaine ni protocole.
candidate_with_unresolved_parameter = declare_parameter_handler.handle(
    DeclareStrategyParameterCommand(
        strategy_id="STRAT-PARAM-CALIBRATION",
        expected_version=candidate.version,
        parameter_id="PARAM-LOOKBACK",
        name="lookback_days",
        origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
        blocking=True,
        unresolved_reason="Domaine et protocole de calibration a definir avant compilation.",
    )
)

# When la compilation est demandee.
incomplete_candidate = candidate_with_unresolved_parameter.validate_for_compilation(
    expected_version=candidate_with_unresolved_parameter.version
)

# Then la compilation est refusee avec un diagnostic bloquant sur le parametre.
assert incomplete_candidate.status == StrategyCandidateStatus.INCOMPLETE
assert any(
    diagnostic.code == "PARAMETER_CALIBRATION_REQUIRED"
    and diagnostic.blocking
    and diagnostic.parameter_id == "PARAM-LOOKBACK"
    for diagnostic in incomplete_candidate.compilation_diagnostics
)
assert incomplete_candidate.status != "COMPILABLE"

# Given le plan de calibration explicite le domaine et le protocole anti-surajustement.
candidate_with_plan = define_plan_handler.handle(
    DefineCalibrationPlanCommand(
        strategy_id="STRAT-PARAM-CALIBRATION",
        expected_version=candidate_with_unresolved_parameter.version,
        parameter_id="PARAM-LOOKBACK",
        lower_bound=20,
        upper_bound=120,
        unit="TRADING_DAY",
        calibration_protocol="walk_forward_sans_selection_sur_test_final",
        expected_sensitivity="Verifier la stabilite du lookback par regime de volatilite.",
    )
)

# When la validation de compilation est rejouee.
specified_candidate = candidate_with_plan.validate_for_compilation(
    expected_version=candidate_with_plan.version
)

# Then le parametre n'emet plus de diagnostic bloquant.
assert specified_candidate.status == StrategyCandidateStatus.SPECIFIED
assert all(
    diagnostic.code != "PARAMETER_CALIBRATION_REQUIRED"
    for diagnostic in specified_candidate.compilation_diagnostics
)
assert any(
    event.event_type == "CalibrationPlanDefined"
    and event.parameter_id == "PARAM-LOOKBACK"
    and event.domain_hash
    and event.protocol_version == "walk_forward_sans_selection_sur_test_final"
    for event in candidate_with_plan.domain_events
)

print("Test d'acceptation des parametres de calibration de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_parameter_calibration_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation des parametres de calibration de strategie M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
