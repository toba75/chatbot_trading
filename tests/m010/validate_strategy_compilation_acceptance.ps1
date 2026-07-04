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
    CompilationDiagnosticCode,
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
        self.calls = []

    def validate(self, rule):
        self.calls.append(rule.rule_id)
        if rule.rule_id not in self.validations:
            raise AssertionError(f"Validation d'expression absente: {rule.rule_id}")
        return self.validations[rule.rule_id]


def build_outcome(suffix):
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": f"RSC-COMPILATION-{suffix}",
            "question": "Une strategie candidate complete peut-elle etre compilee sans backtest ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": f"ANS-COMPILATION-{suffix}",
            "support_status": "SUPPORTED",
            "claim_refs": [f"CLM-COMPILATION-{suffix}@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T11:00:00Z",
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


def build_compilable_candidate(strategy_id, suffix, expression):
    repository = InMemoryStrategyCandidateRepository.empty()
    candidate = open_candidate(repository, strategy_id, suffix)
    rule_id = f"{strategy_id}-RULE-ENTRY"
    with_rule = AddStrategyRuleHandler(repository=repository).handle(
        AddStrategyRuleCommand(
            strategy_id=strategy_id,
            expected_version=candidate.version,
            rule_id=rule_id,
            rule_kind="ENTRY",
            expression=expression,
        )
    )
    with_origin = AssignRuleOriginHandler(repository=repository).handle(
        AssignRuleOriginCommand(
            strategy_id=strategy_id,
            expected_version=with_rule.version,
            rule_id=rule_id,
            origin=RuleOrigin.source(
                verified_claim_refs=(f"CLM-COMPILATION-{suffix}@1",),
                evidence_refs=(),
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
            unresolved_reason="Domaine et protocole requis avant compilation.",
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
    return repository, validated, rule_id


# Given une strategie candidate COMPILABLE avec regle deterministe, parametres resolus et plan de validation.
repository, candidate, rule_id = build_compilable_candidate(
    strategy_id="STRAT-COMPILATION-OK",
    suffix="OK",
    expression="trend_60d > 0",
)
backend = DeterministicStrategyCompilerBackend()
compiler = StrategyCompiler(
    backend=backend,
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
handler = CompileStrategyCandidateHandler(repository=repository, compiler=compiler)

# When la compilation est demandee deux fois sans mutation de la strategie.
first_result = handler.handle(
    CompileStrategyCandidateCommand(
        strategy_id="STRAT-COMPILATION-OK",
        expected_version=candidate.version,
    )
)
second_result = handler.handle(
    CompileStrategyCandidateCommand(
        strategy_id="STRAT-COMPILATION-OK",
        expected_version=candidate.version,
    )
)

# Then SD produit une representation intermediaire hashable et stable, sans backtest.
assert first_result.compilation_status == StrategyCompilationStatus.COMPILED
assert first_result.representation is not None
assert first_result.diagnostics == ()
assert first_result.event.event_type == "StrategyCompiled"
assert first_result.event.representation_hash == first_result.representation.representation_hash
assert first_result.representation.representation_hash == second_result.representation.representation_hash
assert first_result.representation.to_payload() == second_result.representation.to_payload()
assert isinstance(hash(first_result.representation), int)
assert backend.compilation_call_count == 2
assert backend.backtest_call_count == 0


# Given une strategie non compilable.
non_compilable_repository = InMemoryStrategyCandidateRepository.empty()
non_compilable_candidate = open_candidate(
    non_compilable_repository,
    strategy_id="STRAT-COMPILATION-DRAFT",
    suffix="DRAFT",
)
rejecting_backend = DeterministicStrategyCompilerBackend()
rejecting_handler = CompileStrategyCandidateHandler(
    repository=non_compilable_repository,
    compiler=StrategyCompiler(
        backend=rejecting_backend,
        expression_validator=MapRuleExpressionValidator({}),
        compiler_version="m010-deterministic-compiler-v1",
    ),
)

# When la compilation est demandee.
rejected_draft = rejecting_handler.handle(
    CompileStrategyCandidateCommand(
        strategy_id="STRAT-COMPILATION-DRAFT",
        expected_version=non_compilable_candidate.version,
    )
)

# Then aucune representation n'est produite et le backend n'est pas appele.
assert rejected_draft.compilation_status == StrategyCompilationStatus.REJECTED
assert rejected_draft.representation is None
assert rejected_draft.event.event_type == "StrategyCompilationRejected"
assert any(
    diagnostic.code is CompilationDiagnosticCode.STRATEGY_NOT_COMPILABLE
    for diagnostic in rejected_draft.diagnostics
)
assert rejecting_backend.compilation_call_count == 0
assert rejecting_backend.backtest_call_count == 0


# Given une strategie complete dont la regle declare une alea sans graine explicite.
random_repository, random_candidate, random_rule_id = build_compilable_candidate(
    strategy_id="STRAT-COMPILATION-RANDOM",
    suffix="RANDOM",
    expression="random_weight(signal)",
)
random_backend = DeterministicStrategyCompilerBackend()
random_handler = CompileStrategyCandidateHandler(
    repository=random_repository,
    compiler=StrategyCompiler(
        backend=random_backend,
        expression_validator=MapRuleExpressionValidator(
            {
                random_rule_id: RuleExpressionValidation.non_deterministic(
                    rule_id=random_rule_id,
                    random_mechanism=None,
                    seed=None,
                    reason="Mecanisme aleatoire sans graine explicite.",
                )
            }
        ),
        compiler_version="m010-deterministic-compiler-v1",
    ),
)

# When la compilation est demandee.
rejected_random = random_handler.handle(
    CompileStrategyCandidateCommand(
        strategy_id="STRAT-COMPILATION-RANDOM",
        expected_version=random_candidate.version,
    )
)

# Then la compilation est refusee sans representation intermediaire.
assert rejected_random.compilation_status == StrategyCompilationStatus.REJECTED
assert rejected_random.representation is None
assert any(
    diagnostic.code is CompilationDiagnosticCode.RULE_NON_DETERMINISTIC
    for diagnostic in rejected_random.diagnostics
)
assert random_backend.compilation_call_count == 0
assert random_backend.backtest_call_count == 0

print("Test d'acceptation de compilation deterministe de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_compilation_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation de compilation deterministe de strategie M-010 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
