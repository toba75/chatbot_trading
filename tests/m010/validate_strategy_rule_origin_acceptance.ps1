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
    RuleOrigin,
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
            "research_case_id": "RSC-RULE-ORIGIN",
            "question": "Le filtre de tendance peut-il etre attribue a une source verifiee ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": "ANS-RULE-ORIGIN",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-RULE-ORIGIN@4"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-03T10:00:00Z",
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
        strategy_id="STRAT-RULE-ORIGIN",
        research_case_id="RSC-RULE-ORIGIN",
        answer_id="ANS-RULE-ORIGIN",
        expected_version=0,
    )
)

add_rule_handler = AddStrategyRuleHandler(repository=repository)
assign_origin_handler = AssignRuleOriginHandler(repository=repository)

# Given une strategie candidate comporte une regle d'entree sans RuleOrigin.
candidate_with_rule = add_rule_handler.handle(
    AddStrategyRuleCommand(
        strategy_id="STRAT-RULE-ORIGIN",
        expected_version=candidate.version,
        rule_id="STRAT-RULE-ORIGIN-RULE-ENTRY",
        rule_kind="ENTRY",
        expression="trend_60d > 0",
    )
)

# When la validation de compilation est demandee.
incomplete_candidate = candidate_with_rule.validate_for_compilation(
    expected_version=candidate_with_rule.version
)

# Then la strategie passe a INCOMPLETE et la regle devient un diagnostic bloquant.
assert incomplete_candidate.status == StrategyCandidateStatus.INCOMPLETE
assert any(
    diagnostic.code == "RULE_ORIGIN_REQUIRED"
    and diagnostic.blocking
    and diagnostic.rule_id == "STRAT-RULE-ORIGIN-RULE-ENTRY"
    for diagnostic in incomplete_candidate.compilation_diagnostics
)

# Given une origine SOURCE est attribuee sans claim versionne ni EvidenceRef.
candidate_with_unversioned_source = assign_origin_handler.handle(
    AssignRuleOriginCommand(
        strategy_id="STRAT-RULE-ORIGIN",
        expected_version=candidate_with_rule.version,
        rule_id="STRAT-RULE-ORIGIN-RULE-ENTRY",
        origin=RuleOrigin.source(
            verified_claim_refs=("CLM-RULE-ORIGIN",),
            evidence_refs=(),
        ),
    )
)

# When la validation de compilation est demandee pour cette origine documentaire invalide.
source_incomplete_candidate = candidate_with_unversioned_source.validate_for_compilation(
    expected_version=candidate_with_unversioned_source.version
)

# Then la strategie reste non compilable et expose l'absence de preuve versionnee.
assert source_incomplete_candidate.status == StrategyCandidateStatus.INCOMPLETE
assert any(
    diagnostic.code == "SOURCE_EVIDENCE_REQUIRED"
    and diagnostic.blocking
    and diagnostic.rule_id == "STRAT-RULE-ORIGIN-RULE-ENTRY"
    for diagnostic in source_incomplete_candidate.compilation_diagnostics
)
assert source_incomplete_candidate.status != "COMPILABLE"

print("Test d'acceptation des origines de regles de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_rule_origin_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation des origines de regles de strategie M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
