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
)
from app.strategy_design.application.manage_strategy_rules import (
    AddStrategyRuleCommand,
    AddStrategyRuleHandler,
    AssignRuleOriginCommand,
    AssignRuleOriginHandler,
)
from app.strategy_design.application.validate_strategy_candidate import (
    RecordStrategyConflictCommand,
    RecordStrategyConflictHandler,
    ValidateStrategyCandidateCommand,
    ValidateStrategyCandidateHandler,
)
from app.strategy_design.domain.strategy_candidate import (
    CompilationDiagnosticCode,
    RuleOrigin,
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
            "research_case_id": "RSC-DIAGNOSTICS",
            "question": "Une stratégie avec paramètre bloquant et conflit documentaire peut-elle être validée ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": "ANS-DIAGNOSTICS",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-DIAGNOSTICS@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T08:00:00Z",
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
        strategy_id="STRAT-DIAGNOSTICS",
        research_case_id="RSC-DIAGNOSTICS",
        answer_id="ANS-DIAGNOSTICS",
        expected_version=0,
    )
)

candidate_with_rule = AddStrategyRuleHandler(repository=repository).handle(
    AddStrategyRuleCommand(
        strategy_id="STRAT-DIAGNOSTICS",
        expected_version=candidate.version,
        rule_id="STRAT-DIAGNOSTICS-RULE-ENTRY",
        rule_kind="ENTRY",
        expression="trend_60d > 0",
    )
)
candidate_with_origin = AssignRuleOriginHandler(repository=repository).handle(
    AssignRuleOriginCommand(
        strategy_id="STRAT-DIAGNOSTICS",
        expected_version=candidate_with_rule.version,
        rule_id="STRAT-DIAGNOSTICS-RULE-ENTRY",
        origin=RuleOrigin.source(
            verified_claim_refs=("CLM-DIAGNOSTICS@1",),
            evidence_refs=(),
        ),
    )
)
candidate_with_parameter = DeclareStrategyParameterHandler(repository=repository).handle(
    DeclareStrategyParameterCommand(
        strategy_id="STRAT-DIAGNOSTICS",
        expected_version=candidate_with_origin.version,
        parameter_id="PARAM-LOOKBACK-DIAGNOSTICS",
        name="lookback_days",
        origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
        blocking=True,
        unresolved_reason="Domaine et protocole de calibration absents.",
    )
)

# Given une stratégie candidate contient une règle attribuée, un paramètre bloquant non résolu et un conflit documentaire bloquant.
candidate_with_conflict = RecordStrategyConflictHandler(repository=repository).handle(
    RecordStrategyConflictCommand(
        strategy_id="STRAT-DIAGNOSTICS",
        expected_version=candidate_with_parameter.version,
        conflict_id="CONFLICT-DOCUMENTARY-001",
        description="La preuve CLM-DIAGNOSTICS@1 contredit le mandat de risque avant calibration.",
        blocking=True,
    )
)

# When la validation de stratégie est demandée.
validated_candidate = ValidateStrategyCandidateHandler(repository=repository).handle(
    ValidateStrategyCandidateCommand(
        strategy_id="STRAT-DIAGNOSTICS",
        expected_version=candidate_with_conflict.version,
    )
)

# Then la stratégie passe à INCOMPLETE avec deux diagnostics bloquants conservés.
assert validated_candidate.status == StrategyCandidateStatus.INCOMPLETE
blocking_codes = {
    diagnostic.code
    for diagnostic in validated_candidate.compilation_diagnostics
    if diagnostic.blocking
}
assert CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED in blocking_codes
assert CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING in blocking_codes
assert all(
    isinstance(diagnostic.code, CompilationDiagnosticCode)
    for diagnostic in validated_candidate.compilation_diagnostics
)
assert validated_candidate.status != StrategyCandidateStatus.COMPILABLE

persisted_candidate = repository.get("STRAT-DIAGNOSTICS")
assert persisted_candidate.version == validated_candidate.version
assert persisted_candidate.status == StrategyCandidateStatus.INCOMPLETE
assert persisted_candidate.compilation_diagnostics == validated_candidate.compilation_diagnostics
assert any(
    event.event_type == "StrategyCandidateValidated"
    and event.status == StrategyCandidateStatus.INCOMPLETE
    and event.diagnostic_count == len(validated_candidate.compilation_diagnostics)
    for event in persisted_candidate.domain_events
)

print("Test d'acceptation des diagnostics de stratégie candidate M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_candidate_diagnostics_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation des diagnostics de stratégie candidate M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
