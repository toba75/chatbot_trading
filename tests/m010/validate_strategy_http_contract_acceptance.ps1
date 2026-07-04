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
from app.strategy_design.adapters.strategy_http import (
    HttpRequest,
    StrategyHttpAdapter,
)
from app.strategy_design.application.compile_strategy_candidate import (
    CompileStrategyCandidateHandler,
)
from app.strategy_design.application.create_strategy_candidate import (
    CreateStrategyCandidateCommand,
    CreateStrategyCandidateHandler,
)
from app.strategy_design.application.create_strategy_snapshot import (
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
        self._validations = dict(validations)

    def validate(self, rule):
        if rule.rule_id not in self._validations:
            raise AssertionError(f"Validation d'expression absente: {rule.rule_id}")
        return self._validations[rule.rule_id]


def build_outcome(suffix):
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": f"RSC-HTTP-{suffix}",
            "question": "Une strategie candidate exposee par HTTP reste-t-elle attribuee ?",
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
            "answer_id": f"ANS-HTTP-{suffix}",
            "support_status": "SUPPORTED",
            "claim_refs": [f"CLM-HTTP-{suffix}@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T13:00:00Z",
        }
    )


def open_candidate(repository, strategy_id, suffix):
    outcome = build_outcome(suffix)
    return CreateStrategyCandidateHandler(
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


def add_rule_without_origin(repository, strategy_id, suffix):
    candidate = open_candidate(repository, strategy_id, suffix)
    rule_id = f"{strategy_id}-RULE-ENTRY"
    candidate = AddStrategyRuleHandler(repository=repository).handle(
        AddStrategyRuleCommand(
            strategy_id=strategy_id,
            expected_version=candidate.version,
            rule_id=rule_id,
            rule_kind="ENTRY",
            expression="trend_60d > 0",
        )
    )
    return candidate, rule_id


def build_compilable_candidate(repository, strategy_id, suffix):
    candidate, rule_id = add_rule_without_origin(repository, strategy_id, suffix)
    candidate = AssignRuleOriginHandler(repository=repository).handle(
        AssignRuleOriginCommand(
            strategy_id=strategy_id,
            expected_version=candidate.version,
            rule_id=rule_id,
            origin=RuleOrigin.source(
                verified_claim_refs=(f"CLM-HTTP-{suffix}@1",),
                evidence_refs=(f"EVS-HTTP-{suffix}",),
            ),
        )
    )
    candidate = DeclareStrategyParameterHandler(repository=repository).handle(
        DeclareStrategyParameterCommand(
            strategy_id=strategy_id,
            expected_version=candidate.version,
            parameter_id=f"PARAM-LOOKBACK-{suffix}",
            name="lookback_days",
            origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
            blocking=True,
            unresolved_reason="Domaine et protocole requis avant exposition HTTP.",
        )
    )
    candidate = DefineCalibrationPlanHandler(repository=repository).handle(
        DefineCalibrationPlanCommand(
            strategy_id=strategy_id,
            expected_version=candidate.version,
            parameter_id=f"PARAM-LOOKBACK-{suffix}",
            lower_bound=20,
            upper_bound=120,
            unit="day",
            calibration_protocol="walk_forward_v1",
            expected_sensitivity="stabilite du signal sur trois fenetres",
        )
    )
    candidate = ValidateStrategyCandidateHandler(repository=repository).handle(
        ValidateStrategyCandidateCommand(
            strategy_id=strategy_id,
            expected_version=candidate.version,
        )
    )
    assert candidate.status == StrategyCandidateStatus.COMPILABLE
    return candidate, rule_id


def build_adapter(repository, snapshot_store, validations, backend):
    compiler = StrategyCompiler(
        backend=backend,
        expression_validator=MapRuleExpressionValidator(validations),
        compiler_version="m010-http-compiler-v1",
    )
    return StrategyHttpAdapter(
        compile_strategy_handler=CompileStrategyCandidateHandler(
            repository=repository,
            compiler=compiler,
        ),
        strategy_repository=repository,
        snapshot_handler=CreateStrategySnapshotHandler(
            repository=repository,
            snapshot_store=snapshot_store,
        ),
        snapshot_store=snapshot_store,
    )


def assert_public_payload(value):
    serialized = repr(value).lower()
    forbidden_tokens = (
        "raw_research_payload",
        "ra_repository_table",
        "eg_registry_table",
        "internal_strategy_table",
        "mutable_strategy_state",
        "profitability",
        "backtest_result",
    )
    for token in forbidden_tokens:
        assert token not in serialized, f"Payload public interdit: {token}"


# Given une strategie candidate contient une regle sans origine.
reject_repository = InMemoryStrategyCandidateRepository.empty()
candidate_without_origin, missing_rule_id = add_rule_without_origin(
    reject_repository,
    "STRAT-HTTP-MISSING-ORIGIN",
    "MISSING",
)
reject_backend = DeterministicStrategyCompilerBackend()
reject_snapshot_store = InMemoryStrategySnapshotStore.empty()
reject_adapter = build_adapter(
    reject_repository,
    reject_snapshot_store,
    {
        missing_rule_id: RuleExpressionValidation.deterministic(
            rule_id=missing_rule_id,
            normalized_expression="trend_60d > 0",
        )
    },
    reject_backend,
)

# When POST /v1/strategies/compile est appele.
rejected = reject_adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/strategies/compile",
        body={
            "strategy_id": "STRAT-HTTP-MISSING-ORIGIN",
            "expected_version": candidate_without_origin.version,
            "create_snapshot": False,
            "idempotency_key": "CMD-HTTP-MISSING-ORIGIN",
            "occurred_at": "2026-07-04T13:10:00Z",
        },
    )
)

# Then l'API retourne un refus de compilation avec un code public stable et aucun snapshot.
assert rejected.status_code == 422
assert rejected.body["error_code"] == "STRATEGY_RULE_ORIGIN_MISSING"
assert rejected.body["compilation_status"] == "REJECTED"
assert any(
    diagnostic["error_code"] == "STRATEGY_RULE_ORIGIN_MISSING"
    and diagnostic["rule_id"] == missing_rule_id
    for diagnostic in rejected.body["diagnostics"]
)
assert reject_snapshot_store.snapshots() == ()
assert reject_backend.backtest_call_count == 0
assert_public_payload(rejected.body)


# Given une strategie candidate complete et compilable est exposee par HTTP.
compile_repository = InMemoryStrategyCandidateRepository.empty()
compilable_candidate, compilable_rule_id = build_compilable_candidate(
    compile_repository,
    "STRAT-HTTP-COMPILED",
    "COMPILED",
)
compile_backend = DeterministicStrategyCompilerBackend()
compile_snapshot_store = InMemoryStrategySnapshotStore.empty()
compile_adapter = build_adapter(
    compile_repository,
    compile_snapshot_store,
    {
        compilable_rule_id: RuleExpressionValidation.deterministic(
            rule_id=compilable_rule_id,
            normalized_expression="trend_60d > 0",
        )
    },
    compile_backend,
)

# When la compilation demande explicitement un snapshot.
compiled = compile_adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/strategies/compile",
        body={
            "strategy_id": "STRAT-HTTP-COMPILED",
            "expected_version": compilable_candidate.version,
            "create_snapshot": True,
            "idempotency_key": "CMD-HTTP-COMPILED",
            "occurred_at": "2026-07-04T13:15:00Z",
            "snapshot_created_at": "2026-07-04T13:15:00Z",
            "correlation_id": "CORR-HTTP-COMPILED",
            "causation_id": "CMD-HTTP-COMPILED",
            "supersedes_snapshot_id": None,
        },
    )
)

# Then la reponse publique reference la compilation et le snapshot sans lancer EX.
assert compiled.status_code == 202
assert compiled.body["compilation_status"] == "COMPILED"
assert compiled.body["strategy_id"] == "STRAT-HTTP-COMPILED"
assert compiled.body["strategy_version"] == compilable_candidate.version
assert compiled.body["representation_ref"]["representation_hash"]
assert compiled.body["snapshot_ref"]["snapshot_id"].startswith("SVER-")
assert compiled.body["snapshot_ref"]["snapshot_hash"]
assert compile_backend.compilation_call_count == 1
assert compile_backend.backtest_call_count == 0
assert len(compile_snapshot_store.snapshots()) == 1
assert_public_payload(compiled.body)

# When GET /v1/strategies/{id} relit la strategie exposee.
read_response = compile_adapter.handle(
    HttpRequest(
        method="GET",
        path="/v1/strategies/STRAT-HTTP-COMPILED",
        body={},
    )
)

# Then le contrat public contient diagnostics, origines et snapshot sans creation implicite.
assert read_response.status_code == 200
assert read_response.body["strategy_id"] == "STRAT-HTTP-COMPILED"
assert read_response.body["latest_version"] == compilable_candidate.version
assert read_response.body["strategy_status"] == StrategyCandidateStatus.COMPILABLE
assert read_response.body["diagnostics"] == ()
assert read_response.body["rule_origin_summary"][0]["rule_id"] == compilable_rule_id
assert read_response.body["rule_origin_summary"][0]["origin_type"] == "SOURCE"
assert read_response.body["rule_origin_summary"][0]["verified_claim_refs"] == (
    "CLM-HTTP-COMPILED@1",
)
assert read_response.body["snapshot_refs"][0]["snapshot_id"] == compiled.body["snapshot_ref"]["snapshot_id"]
assert len(compile_snapshot_store.snapshots()) == 1
assert_public_payload(read_response.body)

print("Test d'acceptation du contrat HTTP strategies M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_http_contract_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation du contrat HTTP strategies M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
