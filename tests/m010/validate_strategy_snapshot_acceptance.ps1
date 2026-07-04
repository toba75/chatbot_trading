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
from app.contracts.strategy_experiments import StrategySnapshot
from app.strategy_design.adapters.deterministic_strategy_compiler_backend import (
    DeterministicStrategyCompilerBackend,
)
from app.strategy_design.adapters.in_memory_strategy_candidate_repository import (
    InMemoryStrategyCandidateRepository,
)
from app.strategy_design.adapters.in_memory_strategy_snapshot_store import (
    InMemoryStrategySnapshotStore,
)
from app.strategy_design.adapters.research_outcome_translator import (
    StrategyDesignResearchOutcomeTranslator,
)
from app.strategy_design.application.compile_strategy_candidate import (
    CompileStrategyCandidateCommand,
    CompileStrategyCandidateHandler,
)
from app.strategy_design.application.create_strategy_candidate import (
    CreateStrategyCandidateCommand,
    CreateStrategyCandidateHandler,
)
from app.strategy_design.application.create_strategy_snapshot import (
    CreateStrategySnapshotCommand,
    CreateStrategySnapshotHandler,
)
from app.strategy_design.application.manage_strategy_parameters import (
    DeclareStrategyParameterCommand,
    DeclareStrategyParameterHandler,
    DefineCalibrationPlanCommand,
    DefineCalibrationPlanHandler,
)
from app.strategy_design.application.manage_strategy_rules import (
    AddStrategyRuleCommand,
    AddStrategyRuleHandler,
    AssignRuleOriginCommand,
    AssignRuleOriginHandler,
)
from app.strategy_design.application.validate_strategy_candidate import (
    ValidateStrategyCandidateCommand,
    ValidateStrategyCandidateHandler,
)
from app.strategy_design.domain.strategy_candidate import (
    RuleExpressionValidation,
    RuleOrigin,
    RuleOriginType,
    StrategyCandidateStatus,
    StrategyCompilationStatus,
    StrategyCompiler,
)


class StubVerifiedResearchReader:
    def __init__(self, outcome):
        self._outcome = outcome

    def read_verified_research(self, research_case_id, answer_id):
        assert research_case_id == self._outcome.research_case_id
        assert answer_id == self._outcome.answer_id
        return self._outcome


class MapRuleExpressionValidator:
    def __init__(self, validations):
        self.validations = dict(validations)

    def validate(self, rule):
        if rule.rule_id not in self.validations:
            raise AssertionError(f"Validation d'expression absente: {rule.rule_id}")
        return self.validations[rule.rule_id]


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


def build_outcome(suffix):
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": f"RSC-SNAPSHOT-{suffix}",
            "question": "Une strategie candidate peut-elle etre publiee comme snapshot immuable ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
                "constraints": {
                    "max_leverage": 1.0,
                    "max_turnover": 0.25,
                },
                "data_requirements": [
                    {
                        "name": "daily_adjusted_close",
                        "frequency": "daily",
                        "point_in_time": True,
                    }
                ],
            },
            "answer_id": f"ANS-SNAPSHOT-{suffix}",
            "support_status": "SUPPORTED",
            "claim_refs": [f"CLM-SNAPSHOT-{suffix}@2"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T12:00:00Z",
        }
    )


def build_compiled_strategy(strategy_id, suffix):
    repository = InMemoryStrategyCandidateRepository.empty()
    outcome = build_outcome(suffix)
    candidate = CreateStrategyCandidateHandler(
        verified_research_reader=StubVerifiedResearchReader(outcome),
        translator=StrategyDesignResearchOutcomeTranslator(),
        repository=repository,
    ).handle(
        CreateStrategyCandidateCommand(
            strategy_id=strategy_id,
            research_case_id=outcome.research_case_id,
            answer_id=outcome.answer_id,
            expected_version=0,
        )
    )
    rule_id = f"{strategy_id}-RULE-ENTRY"
    with_rule = AddStrategyRuleHandler(repository=repository).handle(
        AddStrategyRuleCommand(
            strategy_id=strategy_id,
            expected_version=candidate.version,
            rule_id=rule_id,
            rule_kind="ENTRY",
            expression="trend_60d > 0",
        )
    )
    with_origin = AssignRuleOriginHandler(repository=repository).handle(
        AssignRuleOriginCommand(
            strategy_id=strategy_id,
            expected_version=with_rule.version,
            rule_id=rule_id,
            origin=RuleOrigin.source(
                verified_claim_refs=(f"CLM-SNAPSHOT-{suffix}@2",),
                evidence_refs=(f"EVS-SNAPSHOT-{suffix}",),
            ),
        )
    )
    with_parameter = DeclareStrategyParameterHandler(repository=repository).handle(
        DeclareStrategyParameterCommand(
            strategy_id=strategy_id,
            expected_version=with_origin.version,
            parameter_id=f"PARAM-LOOKBACK-{suffix}",
            name="lookback_days",
            origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
            blocking=True,
            unresolved_reason="Domaine et protocole requis avant snapshot.",
        )
    )
    with_plan = DefineCalibrationPlanHandler(repository=repository).handle(
        DefineCalibrationPlanCommand(
            strategy_id=strategy_id,
            expected_version=with_parameter.version,
            parameter_id=f"PARAM-LOOKBACK-{suffix}",
            lower_bound=20,
            upper_bound=120,
            unit="day",
            calibration_protocol="walk_forward_v1",
            expected_sensitivity="stabilite du signal sur trois fenetres",
        )
    )
    validated = ValidateStrategyCandidateHandler(repository=repository).handle(
        ValidateStrategyCandidateCommand(
            strategy_id=strategy_id,
            expected_version=with_plan.version,
        )
    )
    assert validated.status == StrategyCandidateStatus.COMPILABLE
    compiler = StrategyCompiler(
        backend=DeterministicStrategyCompilerBackend(),
        expression_validator=MapRuleExpressionValidator(
            {
                rule_id: RuleExpressionValidation.deterministic(
                    rule_id=rule_id,
                    normalized_expression="trend_60d > 0",
                )
            }
        ),
        compiler_version="m010-deterministic-compiler-v1",
    )
    compilation = CompileStrategyCandidateHandler(
        repository=repository,
        compiler=compiler,
    ).handle(
        CompileStrategyCandidateCommand(
            strategy_id=strategy_id,
            expected_version=validated.version,
        )
    )
    assert compilation.compilation_status == StrategyCompilationStatus.COMPILED
    return repository, validated, compilation


# Given une strategie candidate COMPILABLE a ete compilee.
repository, candidate, compilation = build_compiled_strategy(
    strategy_id="STRAT-SNAPSHOT-OK",
    suffix="OK",
)
store = InMemoryStrategySnapshotStore.empty()
handler = CreateStrategySnapshotHandler(repository=repository, snapshot_store=store)

# When SD cree le snapshot.
publication = handler.handle(
    CreateStrategySnapshotCommand(
        strategy_id="STRAT-SNAPSHOT-OK",
        expected_version=candidate.version,
        compilation_result=compilation,
        created_at="2026-07-04T12:10:00Z",
        correlation_id="CORR-M010-SNAPSHOT-OK",
        causation_id="CMD-M010-SNAPSHOT-OK",
        supersedes_snapshot_id=None,
    )
)

# Then EX ne recevra qu'un StrategySnapshot immutable, hashe et sans reference mutable.
snapshot = publication.snapshot
payload = snapshot.to_payload()
assert isinstance(snapshot, StrategySnapshot)
assert publication.strategy.status == StrategyCandidateStatus.SNAPSHOTTED
assert publication.snapshot_hash == snapshot.spec_hash
assert StrategySnapshot.from_json(snapshot.to_json()).to_json() == snapshot.to_json()
assert "current" not in snapshot.to_json().lower()
assert "latest" not in snapshot.to_json().lower()

rule_payload = payload["rules"][0]
assert rule_payload["evidence_refs"] == ["CLM-SNAPSHOT-OK@2"]
assert rule_payload["claim_id"] == "CLM-SNAPSHOT-OK"
assert rule_payload["claim_version"] == 2
assert rule_payload["source_evidence_refs"] == ["EVS-SNAPSHOT-OK"]
assert rule_payload["deterministic"] is True

assert payload["parameters"][0]["resolution_status"] == "RESOLVED"
assert payload["constraints"][0]["origin"] == "USER_CONSTRAINT"
assert payload["data_requirements"][0]["point_in_time"] is True
assert payload["validation_plan"]["compiled_representation_hash"] == (
    compilation.representation.representation_hash
)

outbox_events = store.outbox_events()
assert len(outbox_events) == 1
created_event = outbox_events[0]
assert created_event.event_type == "StrategySnapshotCreated"
assert created_event.event_id == publication.created_event.event_id
assert created_event.aggregate_version == publication.strategy.version
assert created_event.payload["snapshot_hash"] == snapshot.spec_hash
assert created_event.payload["snapshot_id"] == publication.snapshot_id

stored = store.get(publication.snapshot_id)
assert stored.snapshot == snapshot
assert store.supersedes(publication.snapshot_id) is None
assert store.superseded_by(publication.snapshot_id) is None

# Given une compilation absente.
draft_repository, draft_candidate, _ = build_compiled_strategy(
    strategy_id="STRAT-SNAPSHOT-DRAFT-SOURCE",
    suffix="DRAFT",
)
current_candidate = draft_repository.get("STRAT-SNAPSHOT-DRAFT-SOURCE")
expect_raises(
    "compilation disponible requise",
    lambda: CreateStrategySnapshotHandler(
        repository=draft_repository,
        snapshot_store=InMemoryStrategySnapshotStore.empty(),
    ).handle(
        CreateStrategySnapshotCommand(
            strategy_id="STRAT-SNAPSHOT-DRAFT-SOURCE",
            expected_version=current_candidate.version,
            compilation_result=None,
            created_at="2026-07-04T12:11:00Z",
            correlation_id="CORR-M010-SNAPSHOT-DRAFT",
            causation_id="CMD-M010-SNAPSHOT-DRAFT",
            supersedes_snapshot_id=None,
        )
    ),
)

# Given une nouvelle version remplace un snapshot existant.
new_repository, new_candidate, new_compilation = build_compiled_strategy(
    strategy_id="STRAT-SNAPSHOT-NEXT",
    suffix="NEXT",
)
superseding = CreateStrategySnapshotHandler(
    repository=new_repository,
    snapshot_store=store,
).handle(
    CreateStrategySnapshotCommand(
        strategy_id="STRAT-SNAPSHOT-NEXT",
        expected_version=new_candidate.version,
        compilation_result=new_compilation,
        created_at="2026-07-04T12:20:00Z",
        correlation_id="CORR-M010-SNAPSHOT-NEXT",
        causation_id="CMD-M010-SNAPSHOT-NEXT",
        supersedes_snapshot_id=publication.snapshot_id,
    )
)

# Then la relation supersedes/superseded_by reste resoluble et l'evenement est en outbox.
assert store.supersedes(superseding.snapshot_id) == publication.snapshot_id
assert store.superseded_by(publication.snapshot_id) == superseding.snapshot_id
assert any(event.event_type == "StrategyVersionSuperseded" for event in store.outbox_events())

print("Test d'acceptation de snapshot immuable de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_snapshot_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation de snapshot immuable de strategie M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
