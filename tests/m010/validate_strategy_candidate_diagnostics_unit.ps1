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
from app.strategy_design.domain.strategy_candidate import (
    CompilationDiagnostic,
    CompilationDiagnosticCode,
    RuleExpression,
    RuleOrigin,
    RuleOriginType,
    StrategyCandidate,
    StrategyCandidateStatus,
    StrategyCompletenessPolicy,
    StrategyConflict,
    StrategyParameter,
    StrategyRule,
)


class TranslationDecision:
    decision_type = "SUPPORT_STATUS"
    source_research_case_id = "RSC-DIAGNOSTICS-UNIT"
    source_answer_id = "ANS-DIAGNOSTICS-UNIT"
    source_claim_refs = ("CLM-DIAGNOSTICS-UNIT@1",)
    description = "Réponse vérifiée traduite en hypothèse SD sans règle automatique."
    blocking = False
    details = {"support_status": "SUPPORTED"}


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
            "research_case_id": "RSC-DIAGNOSTICS-UNIT",
            "question": "La validation SD conserve-t-elle les diagnostics bloquants ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": "ANS-DIAGNOSTICS-UNIT",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-DIAGNOSTICS-UNIT@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T08:30:00Z",
        }
    )


def build_candidate():
    candidate = StrategyCandidate.create_from_verified_research(
        strategy_id="STRAT-DIAGNOSTICS-UNIT",
        verified_research=build_outcome(),
        translation_decisions=(TranslationDecision(),),
        expected_version=0,
    )
    candidate = candidate.add_rule(
        rule=StrategyRule.without_origin(
            rule_id="STRAT-DIAGNOSTICS-UNIT-RULE-ENTRY",
            rule_kind="ENTRY",
            expression=RuleExpression.from_text("trend_60d > 0"),
        ),
        expected_version=candidate.version,
    )
    return candidate.assign_rule_origin(
        rule_id="STRAT-DIAGNOSTICS-UNIT-RULE-ENTRY",
        origin=RuleOrigin.source(
            verified_claim_refs=("CLM-DIAGNOSTICS-UNIT@1",),
            evidence_refs=(),
        ),
        expected_version=candidate.version,
    )


complete_candidate = build_candidate()
validated_complete_candidate = complete_candidate.validate_candidate(
    expected_version=complete_candidate.version
)
assert validated_complete_candidate.status == StrategyCandidateStatus.COMPILABLE
assert validated_complete_candidate.compilation_diagnostics == ()

draft_candidate = StrategyCandidate.create_from_verified_research(
    strategy_id="STRAT-DIAGNOSTICS-DRAFT",
    verified_research=build_outcome(),
    translation_decisions=(TranslationDecision(),),
    expected_version=0,
)
validated_draft_candidate = draft_candidate.validate_candidate(
    expected_version=draft_candidate.version
)
assert validated_draft_candidate.status == StrategyCandidateStatus.INCOMPLETE
assert any(
    diagnostic.code is CompilationDiagnosticCode.STRATEGY_RULE_REQUIRED
    and diagnostic.blocking
    for diagnostic in validated_draft_candidate.compilation_diagnostics
)
assert validated_draft_candidate.status != StrategyCandidateStatus.COMPILABLE

candidate_with_parameter = complete_candidate.add_parameter(
    parameter=StrategyParameter.unresolved(
        parameter_id="PARAM-LOOKBACK-DIAGNOSTICS-UNIT",
        name="lookback_days",
        origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
        blocking=True,
        unresolved_reason="Domaine de calibration absent.",
    ),
    expected_version=complete_candidate.version,
)
candidate_with_conflict = candidate_with_parameter.record_conflict(
    conflict=StrategyConflict.blocking_documentary_conflict(
        conflict_id="CONFLICT-DOCUMENTARY-UNIT",
        description="Conflit documentaire bloquant entre claim et mandat.",
    ),
    expected_version=candidate_with_parameter.version,
)

diagnostics = StrategyCompletenessPolicy().evaluate(candidate_with_conflict)
assert {
    CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED,
    CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING,
}.issubset({diagnostic.code for diagnostic in diagnostics if diagnostic.blocking})
assert all(isinstance(diagnostic.code, CompilationDiagnosticCode) for diagnostic in diagnostics)

validated_incomplete_candidate = candidate_with_conflict.validate_candidate(
    expected_version=candidate_with_conflict.version
)
assert validated_incomplete_candidate.status == StrategyCandidateStatus.INCOMPLETE
assert any(
    event.event_type == "StrategyCandidateValidated"
    and event.status == StrategyCandidateStatus.INCOMPLETE
    and event.diagnostic_count == len(validated_incomplete_candidate.compilation_diagnostics)
    for event in validated_incomplete_candidate.domain_events
)

resolved_candidate = validated_incomplete_candidate.resolve_conflict(
    conflict_id="CONFLICT-DOCUMENTARY-UNIT",
    resolution_summary="Le mandat est reformulé dans une nouvelle version avant compilation.",
    expected_version=validated_incomplete_candidate.version,
)
assert validated_incomplete_candidate.status == StrategyCandidateStatus.INCOMPLETE
assert any(
    diagnostic.code is CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING
    for diagnostic in validated_incomplete_candidate.compilation_diagnostics
)
assert resolved_candidate.version == validated_incomplete_candidate.version + 1
assert resolved_candidate.conflicts[0].resolution_status == "RESOLVED"

revalidated_candidate = resolved_candidate.validate_candidate(
    expected_version=resolved_candidate.version
)
blocking_codes_after_resolution = {
    diagnostic.code
    for diagnostic in revalidated_candidate.compilation_diagnostics
    if diagnostic.blocking
}
assert CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED in blocking_codes_after_resolution
assert CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING not in blocking_codes_after_resolution

expect_raises(
    "code diagnostic libre interdit",
    lambda: CompilationDiagnostic(
        code="RULE_ORIGIN_REQUIRED",
        description="Diagnostic non typé interdit.",
        blocking=True,
        rule_id="STRAT-DIAGNOSTICS-UNIT-RULE-ENTRY",
        parameter_id=None,
    ),
)
expect_raises(
    "CONFLICT-DOCUMENTARY-UNIT",
    lambda: candidate_with_conflict.record_conflict(
        conflict=StrategyConflict.blocking_documentary_conflict(
            conflict_id="CONFLICT-DOCUMENTARY-UNIT",
            description="Conflit documentaire dupliqué.",
        ),
        expected_version=candidate_with_conflict.version,
    ),
)
expect_raises(
    "CONFLICT-ABSENT",
    lambda: complete_candidate.resolve_conflict(
        conflict_id="CONFLICT-ABSENT",
        resolution_summary="Impossible à résoudre sans conflit enregistré.",
        expected_version=complete_candidate.version,
    ),
)
expect_raises(
    "version obsol",
    lambda: complete_candidate.validate_candidate(
        expected_version=complete_candidate.version - 1
    ),
)

print("Tests unitaires des diagnostics de stratégie candidate M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_candidate_diagnostics_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires des diagnostics de stratégie candidate M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
