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
from app.strategy_design.adapters.in_memory_strategy_snapshot_store import (
    InMemoryStrategySnapshotStore,
)
from app.strategy_design.domain.strategy_candidate import (
    CompiledStrategyRepresentation,
    ParameterDomain,
    RuleExpression,
    RuleExpressionValidation,
    RuleOrigin,
    RuleOriginType,
    StrategyCandidate,
    StrategyCandidateStatus,
    StrategyParameter,
    StrategyRule,
    StrategySnapshotPolicy,
    ValidationPlan,
)


class TranslationDecision:
    decision_type = "SUPPORT_STATUS"
    source_research_case_id = "RSC-SNAPSHOT-UNIT"
    source_answer_id = "ANS-SNAPSHOT-UNIT"
    source_claim_refs = ("CLM-SNAPSHOT-UNIT@3",)
    description = "Reponse verifiee traduite en hypothese SD sans regle automatique."
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
            "research_case_id": "RSC-SNAPSHOT-UNIT",
            "question": "Le snapshot SD conserve-t-il les preuves et versions ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
                "constraints": {"max_leverage": 1.0},
                "data_requirements": [
                    {
                        "name": "daily_adjusted_close",
                        "frequency": "daily",
                        "point_in_time": True,
                    }
                ],
            },
            "answer_id": "ANS-SNAPSHOT-UNIT",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-SNAPSHOT-UNIT@3"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T12:30:00Z",
        }
    )


def build_compilable_candidate(strategy_id="STRAT-SNAPSHOT-UNIT"):
    candidate = StrategyCandidate.create_from_verified_research(
        strategy_id=strategy_id,
        verified_research=build_outcome(),
        translation_decisions=(TranslationDecision(),),
        expected_version=0,
    )
    candidate = candidate.add_rule(
        rule=StrategyRule.without_origin(
            rule_id=f"{strategy_id}-RULE-ENTRY",
            rule_kind="ENTRY",
            expression=RuleExpression.from_text("trend_60d > 0"),
        ),
        expected_version=candidate.version,
    )
    candidate = candidate.assign_rule_origin(
        rule_id=f"{strategy_id}-RULE-ENTRY",
        origin=RuleOrigin.source(
            verified_claim_refs=("CLM-SNAPSHOT-UNIT@3",),
            evidence_refs=("EVS-SNAPSHOT-UNIT",),
        ),
        expected_version=candidate.version,
    )
    candidate = candidate.add_parameter(
        parameter=StrategyParameter.unresolved(
            parameter_id="PARAM-SNAPSHOT-LOOKBACK",
            name="lookback_days",
            origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
            blocking=True,
            unresolved_reason="Domaine requis.",
        ),
        expected_version=candidate.version,
    )
    candidate = candidate.define_calibration_plan(
        parameter_id="PARAM-SNAPSHOT-LOOKBACK",
        domain=ParameterDomain.from_bounds(
            lower_bound=20,
            upper_bound=120,
            unit="day",
        ),
        validation_plan=ValidationPlan(
            calibration_protocol="walk_forward_v1",
            expected_sensitivity="stabilite du signal",
        ),
        expected_version=candidate.version,
    )
    candidate = candidate.validate_candidate(expected_version=candidate.version)
    assert candidate.status == StrategyCandidateStatus.COMPILABLE
    return candidate


def compiled_representation(candidate):
    return CompiledStrategyRepresentation.from_candidate(
        candidate=candidate,
        rule_validations=(
            RuleExpressionValidation.deterministic(
                rule_id=candidate.rules[0].rule_id,
                normalized_expression="trend_60d > 0",
            ),
        ),
        compiler_version="unit-compiler-v1",
    )


policy = StrategySnapshotPolicy()
candidate = build_compilable_candidate()
representation = compiled_representation(candidate)

first = policy.create_snapshot(
    candidate=candidate,
    compiled_representation=representation,
    created_at="2026-07-04T12:40:00Z",
    correlation_id="CORR-M010-SNAPSHOT-UNIT",
    causation_id="CMD-M010-SNAPSHOT-UNIT",
    supersedes_snapshot_id=None,
)
second = policy.create_snapshot(
    candidate=candidate,
    compiled_representation=representation,
    created_at="2026-07-04T12:40:00Z",
    correlation_id="CORR-M010-SNAPSHOT-UNIT",
    causation_id="CMD-M010-SNAPSHOT-UNIT",
    supersedes_snapshot_id=None,
)

assert first.snapshot_hash == second.snapshot_hash
assert first.created_event.event_id == second.created_event.event_id
assert first.snapshot.to_payload() == second.snapshot.to_payload()
assert first.snapshot.to_payload()["rules"][0]["claim_id"] == "CLM-SNAPSHOT-UNIT"
assert first.snapshot.to_payload()["rules"][0]["claim_version"] == 3
assert first.snapshot.to_payload()["rules"][0]["source_evidence_refs"] == [
    "EVS-SNAPSHOT-UNIT"
]
assert first.created_event.aggregate_version == candidate.version
assert first.created_event.payload["aggregate_version"] == candidate.version

try:
    first.snapshot.rules[0]["kind"] = "MUTATED"
except TypeError:
    pass
else:
    raise AssertionError("Le snapshot doit etre immuable apres creation.")

draft = StrategyCandidate.create_from_verified_research(
    strategy_id="STRAT-SNAPSHOT-DRAFT",
    verified_research=build_outcome(),
    translation_decisions=(TranslationDecision(),),
    expected_version=0,
)
expect_raises(
    "strategie non compilable",
    lambda: policy.create_snapshot(
        candidate=draft,
        compiled_representation=representation,
        created_at="2026-07-04T12:41:00Z",
        correlation_id="CORR-M010-SNAPSHOT-DRAFT",
        causation_id="CMD-M010-SNAPSHOT-DRAFT",
        supersedes_snapshot_id=None,
    ),
)

other_candidate = build_compilable_candidate("STRAT-SNAPSHOT-OTHER")
other_representation = compiled_representation(other_candidate)
expect_raises(
    "compilation hors strategie",
    lambda: policy.create_snapshot(
        candidate=candidate,
        compiled_representation=other_representation,
        created_at="2026-07-04T12:42:00Z",
        correlation_id="CORR-M010-SNAPSHOT-OTHER",
        causation_id="CMD-M010-SNAPSHOT-OTHER",
        supersedes_snapshot_id=None,
    ),
)

candidate_without_claim = candidate.assign_rule_origin(
    rule_id=candidate.rules[0].rule_id,
    origin=RuleOrigin.source(verified_claim_refs=(), evidence_refs=("EVS-SNAPSHOT-UNIT",)),
    expected_version=candidate.version,
)
expect_raises(
    "claim versionne requis",
    lambda: policy.create_snapshot(
        candidate=candidate_without_claim,
        compiled_representation=compiled_representation(candidate_without_claim),
        created_at="2026-07-04T12:43:00Z",
        correlation_id="CORR-M010-SNAPSHOT-CLAIM",
        causation_id="CMD-M010-SNAPSHOT-CLAIM",
        supersedes_snapshot_id=None,
    ),
)

store = InMemoryStrategySnapshotStore.empty()
stored = store.append_publication(first)
duplicate = store.append_publication(first)
assert stored.snapshot_id == duplicate.snapshot_id
assert len(store.snapshots()) == 1
assert len(store.outbox_events()) == 1
assert store.outbox_events()[0].event_id == first.created_event.event_id

superseding_candidate = build_compilable_candidate("STRAT-SNAPSHOT-SUPERSEDING")
superseding = policy.create_snapshot(
    candidate=superseding_candidate,
    compiled_representation=compiled_representation(superseding_candidate),
    created_at="2026-07-04T12:50:00Z",
    correlation_id="CORR-M010-SNAPSHOT-SUPERSEDING",
    causation_id="CMD-M010-SNAPSHOT-SUPERSEDING",
    supersedes_snapshot_id=first.snapshot_id,
)
store.append_publication(superseding)
assert store.supersedes(superseding.snapshot_id) == first.snapshot_id
assert store.superseded_by(first.snapshot_id) == superseding.snapshot_id
assert len(store.outbox_events()) == 3
assert store.outbox_events()[-1].event_type == "StrategyVersionSuperseded"

orphan_candidate = build_compilable_candidate("STRAT-SNAPSHOT-ORPHAN")
orphan = policy.create_snapshot(
    candidate=orphan_candidate,
    compiled_representation=compiled_representation(orphan_candidate),
    created_at="2026-07-04T12:55:00Z",
    correlation_id="CORR-M010-SNAPSHOT-ORPHAN",
    causation_id="CMD-M010-SNAPSHOT-ORPHAN",
    supersedes_snapshot_id="SVER-SNAPSHOT-UNKNOWN-V000001",
)
expect_raises("snapshot supersede absent", lambda: InMemoryStrategySnapshotStore.empty().append_publication(orphan))

print("Tests unitaires de snapshot immuable de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_snapshot_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires de snapshot immuable de strategie M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
