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
from app.strategy_design.domain.strategy_candidate import (
    StrategyCandidateStatus,
    StrategyConcurrencyError,
)


class StubVerifiedResearchReader:
    def __init__(self, outcomes):
        self._outcomes = dict(outcomes)
        self.reads = []

    def read_verified_research(self, research_case_id, answer_id):
        self.reads.append((research_case_id, answer_id))
        return self._outcomes[(research_case_id, answer_id)]

    def replace(self, outcome):
        self._outcomes[(outcome.research_case_id, outcome.answer_id)] = outcome


def build_outcome(*, answer_id, mandate, completed_at):
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-CARRY-PREMIUM",
            "question": "Le carry obligataire reste-t-il exploitable avec volatilité bornée ?",
            "mandate": mandate,
            "answer_id": answer_id,
            "support_status": "INSUFFICIENT_EVIDENCE",
            "claim_refs": ["CLM-CARRY-PREMIUM@3"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [
                {
                    "topic": "Frais récents non couverts",
                    "impact": "Bloque la formalisation directe d'une règle exécutable.",
                }
            ],
            "completed_at": completed_at,
        }
    )


initial_outcome = build_outcome(
    answer_id="ANS-CARRY-PREMIUM",
    mandate={
        "universe": "ETF_US_TREASURY",
        "horizon": "swing",
        "risk_limit": "drawdown_10pct",
    },
    completed_at="2026-07-03T08:00:00Z",
)
reader = StubVerifiedResearchReader(
    {(initial_outcome.research_case_id, initial_outcome.answer_id): initial_outcome}
)
repository = InMemoryStrategyCandidateRepository.empty()
handler = CreateStrategyCandidateHandler(
    verified_research_reader=reader,
    translator=StrategyDesignResearchOutcomeTranslator(),
    repository=repository,
)

# Given un résultat de recherche vérifié contient des claims, un mandat et une lacune documentaire bloquante.
command = CreateStrategyCandidateCommand(
    strategy_id="STRAT-CARRY-PREMIUM",
    research_case_id="RSC-CARRY-PREMIUM",
    answer_id="ANS-CARRY-PREMIUM",
    expected_version=0,
)

# When SD ouvre une stratégie candidate depuis ce résultat.
candidate = handler.handle(command)

# Then la stratégie conserve le mandat, les références de recherche, les décisions de traduction et le diagnostic bloquant sans créer de règle exécutable.
assert reader.reads == [("RSC-CARRY-PREMIUM", "ANS-CARRY-PREMIUM")]
assert candidate.strategy_id == "STRAT-CARRY-PREMIUM"
assert candidate.version == 1
assert candidate.status == StrategyCandidateStatus.DRAFT
assert candidate.rules == ()
assert candidate.mandate.to_payload() == initial_outcome.mandate
assert candidate.verified_research_ref.research_case_id == "RSC-CARRY-PREMIUM"
assert candidate.verified_research_ref.answer_id == "ANS-CARRY-PREMIUM"
assert candidate.verified_research_ref.claim_refs == ("CLM-CARRY-PREMIUM@3",)
assert {decision.decision_type for decision in candidate.translation_decisions} == {
    "SUPPORT_STATUS",
    "MANDATE_CONSTRAINT",
    "SOURCE_ORIGIN",
    "KNOWLEDGE_GAP",
}
assert any(
    decision.decision_type == "KNOWLEDGE_GAP" and decision.blocking
    for decision in candidate.translation_decisions
)
assert any(
    diagnostic.code == "INSUFFICIENT_EVIDENCE" and diagnostic.blocking
    for diagnostic in candidate.translation_diagnostics
)
assert any(
    diagnostic.code == "KNOWLEDGE_GAP" and diagnostic.blocking
    for diagnostic in candidate.translation_diagnostics
)
assert len(candidate.domain_events) == 1
created_event = candidate.domain_events[0]
assert created_event.event_type == "StrategyCandidateCreated"
assert created_event.strategy_id == "STRAT-CARRY-PREMIUM"
assert created_event.strategy_version == 1
assert created_event.verified_research_ref.research_case_id == "RSC-CARRY-PREMIUM"
assert created_event.mandate_hash != ""

stored_candidate = repository.get("STRAT-CARRY-PREMIUM")
assert stored_candidate == candidate

updated_outcome = build_outcome(
    answer_id="ANS-CARRY-PREMIUM-UPDATED",
    mandate={
        "universe": "ETF_GLOBAL_RATES",
        "horizon": "monthly",
        "risk_limit": "drawdown_5pct",
    },
    completed_at="2026-07-03T09:00:00Z",
)
reader.replace(updated_outcome)
stale_command = CreateStrategyCandidateCommand(
    strategy_id="STRAT-CARRY-PREMIUM",
    research_case_id="RSC-CARRY-PREMIUM",
    answer_id="ANS-CARRY-PREMIUM-UPDATED",
    expected_version=0,
)

try:
    handler.handle(stale_command)
except StrategyConcurrencyError as exc:
    assert exc.strategy_id == "STRAT-CARRY-PREMIUM"
    assert exc.expected_version == 0
    assert exc.actual_version == 1
else:
    raise AssertionError("Une commande obsolète ne doit pas écraser la stratégie existante.")

reloaded_candidate = repository.get("STRAT-CARRY-PREMIUM")
assert reloaded_candidate.mandate.to_payload() == initial_outcome.mandate
assert reloaded_candidate.verified_research_ref.answer_id == "ANS-CARRY-PREMIUM"

print("Test d'acceptation de création de stratégie candidate M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_candidate_creation_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation de création de stratégie candidate M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
