$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys
from dataclasses import replace

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.contracts.research_outcomes import VerifiedResearchOutcome
from app.strategy_design.adapters.in_memory_strategy_candidate_repository import (
    InMemoryStrategyCandidateRepository,
)
from app.strategy_design.adapters.research_outcome_translator import (
    ResearchOutcomeTranslationDecision,
    StrategyDesignResearchOutcomeTranslator,
)
from app.strategy_design.domain.strategy_candidate import (
    StrategyCandidate,
    StrategyCandidateStatus,
    StrategyConcurrencyError,
    StrategyMandate,
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


def build_outcome():
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-UNIT-CARRY",
            "question": "Le carry reste-t-il robuste après hausse de volatilité ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": "ANS-UNIT-CARRY",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-UNIT-CARRY@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-03T08:30:00Z",
        }
    )


outcome = build_outcome()
decisions = StrategyDesignResearchOutcomeTranslator().translate(outcome)

candidate = StrategyCandidate.create_from_verified_research(
    strategy_id="STRAT-UNIT-CARRY",
    verified_research=outcome,
    translation_decisions=decisions,
    expected_version=0,
)

assert candidate.strategy_id == "STRAT-UNIT-CARRY"
assert candidate.version == 1
assert candidate.status == StrategyCandidateStatus.DRAFT
assert candidate.rules == ()
assert candidate.verified_research_ref.claim_refs == ("CLM-UNIT-CARRY@1",)
assert candidate.mandate.to_payload() == outcome.mandate
assert len(candidate.domain_events) == 1
assert candidate.domain_events[0].event_type == "StrategyCandidateCreated"
assert candidate.domain_events[0].strategy_version == 1
assert candidate.domain_events[0].mandate_hash != ""

expect_raises(
    "mandat SD vide",
    lambda: StrategyMandate.from_payload({}),
)
expect_raises(
    "version attendue initiale invalide",
    lambda: StrategyCandidate.create_from_verified_research(
        strategy_id="STRAT-UNIT-CARRY-VERSION",
        verified_research=outcome,
        translation_decisions=decisions,
        expected_version=1,
    ),
)

outcome_without_claims = replace(outcome, claim_refs=())
expect_raises(
    "claim_refs SD requis",
    lambda: StrategyCandidate.create_from_verified_research(
        strategy_id="STRAT-UNIT-NO-CLAIM",
        verified_research=outcome_without_claims,
        translation_decisions=decisions,
        expected_version=0,
    ),
)

forbidden_decision = ResearchOutcomeTranslationDecision(
    decision_type="STRATEGY_RULE",
    source_research_case_id=outcome.research_case_id,
    source_answer_id=outcome.answer_id,
    source_claim_refs=("CLM-UNIT-CARRY@1",),
    description="Une décision de traduction ne doit pas devenir une règle SD.",
    blocking=False,
    details={"reason": "rule_creation_forbidden"},
)
expect_raises(
    "d\u00e9cision de traduction interdite",
    lambda: StrategyCandidate.create_from_verified_research(
        strategy_id="STRAT-UNIT-FORBIDDEN",
        verified_research=outcome,
        translation_decisions=decisions + (forbidden_decision,),
        expected_version=0,
    ),
)

repository = InMemoryStrategyCandidateRepository.empty()
repository.save_new(candidate, expected_version=0)
assert repository.get("STRAT-UNIT-CARRY") == candidate

expect_raises(
    "identit\u00e9 strat\u00e9gie d\u00e9j\u00e0 ouverte",
    lambda: repository.save_new(candidate, expected_version=1),
)

stale_candidate = StrategyCandidate.create_from_verified_research(
    strategy_id="STRAT-UNIT-STALE",
    verified_research=outcome,
    translation_decisions=decisions,
    expected_version=0,
)
stale_error = expect_raises(
    "version obsol\u00e8te",
    lambda: repository.save_new(stale_candidate, expected_version=2),
)
assert isinstance(stale_error, StrategyConcurrencyError)
assert stale_error.expected_version == 2
assert stale_error.actual_version == 0

existing_stale_error = expect_raises(
    "version obsol\u00e8te",
    lambda: repository.save(candidate, expected_version=0),
)
assert isinstance(existing_stale_error, StrategyConcurrencyError)
assert existing_stale_error.expected_version == 0
assert existing_stale_error.actual_version == 1
assert repository.get("STRAT-UNIT-CARRY") == candidate

print("Tests unitaires de création de stratégie candidate M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_candidate_creation_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires de création de stratégie candidate M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
