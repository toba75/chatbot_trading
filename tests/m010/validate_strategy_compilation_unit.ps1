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
    CompilationDiagnosticCode,
    CompiledStrategyRepresentation,
    ParameterDomain,
    RuleExpression,
    RuleExpressionValidation,
    RuleOrigin,
    RuleOriginType,
    StrategyCandidate,
    StrategyCandidateStatus,
    StrategyCompilationStatus,
    StrategyCompiler,
    StrategyParameter,
    StrategyRule,
    ValidationPlan,
)


class TranslationDecision:
    decision_type = "SUPPORT_STATUS"
    source_research_case_id = "RSC-COMPILATION-UNIT"
    source_answer_id = "ANS-COMPILATION-UNIT"
    source_claim_refs = ("CLM-COMPILATION-UNIT@1",)
    description = "Reponse verifiee traduite en hypothese SD sans regle automatique."
    blocking = False
    details = {"support_status": "SUPPORTED"}


class SingleRuleExpressionValidator:
    def __init__(self, validation):
        self.validation = validation
        self.call_count = 0

    def validate(self, rule):
        self.call_count += 1
        return self.validation


class RecordingBackend:
    def __init__(self):
        self.compilation_call_count = 0
        self.backtest_call_count = 0

    def compile_representation(self, *, candidate, rule_validations, compiler_version):
        self.compilation_call_count += 1
        return CompiledStrategyRepresentation.from_candidate(
            candidate=candidate,
            rule_validations=rule_validations,
            compiler_version=compiler_version,
        )

    def execute_backtest(self):
        self.backtest_call_count += 1
        raise AssertionError("Le backend de compilation ne doit pas executer de backtest.")


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
            "research_case_id": "RSC-COMPILATION-UNIT",
            "question": "La compilation SD reste-t-elle deterministe sans backtest ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": "ANS-COMPILATION-UNIT",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-COMPILATION-UNIT@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T11:30:00Z",
        }
    )


def build_specified_candidate(strategy_id, expression_text):
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
            expression=RuleExpression.from_text(expression_text),
        ),
        expected_version=candidate.version,
    )
    return candidate.assign_rule_origin(
        rule_id=f"{strategy_id}-RULE-ENTRY",
        origin=RuleOrigin.source(
            verified_claim_refs=("CLM-COMPILATION-UNIT@1",),
            evidence_refs=(),
        ),
        expected_version=candidate.version,
    )


def add_resolved_parameter(candidate, suffix):
    candidate = candidate.add_parameter(
        parameter=StrategyParameter.unresolved(
            parameter_id=f"PARAM-LOOKBACK-{suffix}",
            name="lookback_days",
            origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
            blocking=True,
            unresolved_reason="Domaine et protocole requis avant compilation.",
        ),
        expected_version=candidate.version,
    )
    return candidate.define_calibration_plan(
        parameter_id=f"PARAM-LOOKBACK-{suffix}",
        domain=ParameterDomain.from_bounds(
            lower_bound=20,
            upper_bound=120,
            unit="day",
        ),
        validation_plan=ValidationPlan(
            calibration_protocol="walk_forward_v1",
            expected_sensitivity="stabilite du signal sur trois fenetres",
        ),
        expected_version=candidate.version,
    )


def build_compilable_candidate(strategy_id, expression_text):
    candidate = add_resolved_parameter(
        build_specified_candidate(strategy_id, expression_text),
        suffix=strategy_id.rsplit("-", 1)[-1],
    )
    validated = candidate.validate_candidate(expected_version=candidate.version)
    assert validated.status == StrategyCandidateStatus.COMPILABLE
    return validated


valid_candidate = build_compilable_candidate("STRAT-COMPILATION-UNIT", "trend_60d > 0")
valid_rule_id = valid_candidate.rules[0].rule_id
accepted_validation = RuleExpressionValidation.deterministic(
    rule_id=valid_rule_id,
    normalized_expression="trend_60d > 0",
)

expect_raises(
    "StrategyCompilerBackend requis",
    lambda: StrategyCompiler(
        backend=None,
        expression_validator=SingleRuleExpressionValidator(accepted_validation),
        compiler_version="unit-compiler-v1",
    ),
)
expect_raises(
    "RuleExpressionValidator requis",
    lambda: StrategyCompiler(
        backend=RecordingBackend(),
        expression_validator=None,
        compiler_version="unit-compiler-v1",
    ),
)

backend = RecordingBackend()
compiler = StrategyCompiler(
    backend=backend,
    expression_validator=SingleRuleExpressionValidator(accepted_validation),
    compiler_version="unit-compiler-v1",
)
compiled = compiler.compile(valid_candidate, expected_version=valid_candidate.version)
compiled_again = compiler.compile(valid_candidate, expected_version=valid_candidate.version)
assert compiled.compilation_status == StrategyCompilationStatus.COMPILED
assert compiled.diagnostics == ()
assert compiled.representation is not None
assert compiled.representation.representation_hash == compiled_again.representation.representation_hash
assert compiled.representation.to_payload() == compiled_again.representation.to_payload()
assert isinstance(hash(compiled.representation), int)
assert compiled.event.event_type == "StrategyCompiled"
assert compiled.event.representation_hash == compiled.representation.representation_hash
assert backend.compilation_call_count == 2
assert backend.backtest_call_count == 0

changed_candidate = build_compilable_candidate("STRAT-COMPILATION-ALT", "trend_90d > 0")
changed_compiler = StrategyCompiler(
    backend=RecordingBackend(),
    expression_validator=SingleRuleExpressionValidator(
        RuleExpressionValidation.deterministic(
            rule_id=changed_candidate.rules[0].rule_id,
            normalized_expression="trend_90d > 0",
        )
    ),
    compiler_version="unit-compiler-v1",
)
changed = changed_compiler.compile(changed_candidate, expected_version=changed_candidate.version)
assert changed.representation.representation_hash != compiled.representation.representation_hash

draft_candidate = StrategyCandidate.create_from_verified_research(
    strategy_id="STRAT-COMPILATION-DRAFT-UNIT",
    verified_research=build_outcome(),
    translation_decisions=(TranslationDecision(),),
    expected_version=0,
)
draft_backend = RecordingBackend()
draft_result = StrategyCompiler(
    backend=draft_backend,
    expression_validator=SingleRuleExpressionValidator(accepted_validation),
    compiler_version="unit-compiler-v1",
).compile(draft_candidate, expected_version=draft_candidate.version)
assert draft_result.compilation_status == StrategyCompilationStatus.REJECTED
assert draft_result.representation is None
assert any(
    diagnostic.code is CompilationDiagnosticCode.STRATEGY_NOT_COMPILABLE
    for diagnostic in draft_result.diagnostics
)
assert draft_backend.compilation_call_count == 0

invalid_expression_backend = RecordingBackend()
invalid_expression = StrategyCompiler(
    backend=invalid_expression_backend,
    expression_validator=SingleRuleExpressionValidator(
        RuleExpressionValidation.invalid(
            rule_id=valid_rule_id,
            reason="Expression de regle invalide.",
        )
    ),
    compiler_version="unit-compiler-v1",
).compile(valid_candidate, expected_version=valid_candidate.version)
assert invalid_expression.compilation_status == StrategyCompilationStatus.REJECTED
assert any(
    diagnostic.code is CompilationDiagnosticCode.RULE_EXPRESSION_INVALID
    for diagnostic in invalid_expression.diagnostics
)
assert invalid_expression_backend.compilation_call_count == 0

nondeterministic_backend = RecordingBackend()
nondeterministic = StrategyCompiler(
    backend=nondeterministic_backend,
    expression_validator=SingleRuleExpressionValidator(
        RuleExpressionValidation.non_deterministic(
            rule_id=valid_rule_id,
            random_mechanism=None,
            seed=None,
            reason="Alea sans graine explicite.",
        )
    ),
    compiler_version="unit-compiler-v1",
).compile(valid_candidate, expected_version=valid_candidate.version)
assert nondeterministic.compilation_status == StrategyCompilationStatus.REJECTED
assert any(
    diagnostic.code is CompilationDiagnosticCode.RULE_NON_DETERMINISTIC
    for diagnostic in nondeterministic.diagnostics
)
assert nondeterministic_backend.compilation_call_count == 0

unresolved_candidate = build_specified_candidate(
    "STRAT-COMPILATION-UNRESOLVED",
    "trend_60d > 0",
).add_parameter(
    parameter=StrategyParameter.unresolved(
        parameter_id="PARAM-UNRESOLVED",
        name="lookback_days",
        origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
        blocking=True,
        unresolved_reason="Parametre bloquant sans plan.",
    ),
    expected_version=3,
)
unresolved_result = StrategyCompiler(
    backend=RecordingBackend(),
    expression_validator=SingleRuleExpressionValidator(
        RuleExpressionValidation.deterministic(
            rule_id=unresolved_candidate.rules[0].rule_id,
            normalized_expression="trend_60d > 0",
        )
    ),
    compiler_version="unit-compiler-v1",
).compile(unresolved_candidate, expected_version=unresolved_candidate.version)
assert unresolved_result.compilation_status == StrategyCompilationStatus.REJECTED
assert any(
    diagnostic.code is CompilationDiagnosticCode.PARAMETER_CALIBRATION_REQUIRED
    for diagnostic in unresolved_result.diagnostics
)

missing_plan_candidate = build_specified_candidate(
    "STRAT-COMPILATION-NOPLAN",
    "trend_60d > 0",
).add_parameter(
    parameter=StrategyParameter(
        parameter_id="PARAM-NOPLAN",
        name="lookback_days",
        origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
        value=None,
        domain=ParameterDomain.from_bounds(lower_bound=20, upper_bound=120, unit="day"),
        validation_plan=None,
        blocking=True,
        resolution_status="RESOLVED",
        unresolved_reason=None,
    ),
    expected_version=3,
)
missing_plan = StrategyCompiler(
    backend=RecordingBackend(),
    expression_validator=SingleRuleExpressionValidator(
        RuleExpressionValidation.deterministic(
            rule_id=missing_plan_candidate.rules[0].rule_id,
            normalized_expression="trend_60d > 0",
        )
    ),
    compiler_version="unit-compiler-v1",
).compile(missing_plan_candidate, expected_version=missing_plan_candidate.version)
assert missing_plan.compilation_status == StrategyCompilationStatus.REJECTED
assert any(
    diagnostic.code is CompilationDiagnosticCode.VALIDATION_PLAN_REQUIRED
    for diagnostic in missing_plan.diagnostics
)

expect_raises(
    "version obsol",
    lambda: compiler.compile(valid_candidate, expected_version=valid_candidate.version - 1),
)

print("Tests unitaires de compilation deterministe de strategie M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_compilation_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires de compilation deterministe de strategie M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
