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
from app.strategy_design.adapters.deterministic_strategy_compiler_backend import (
    DeterministicStrategyCompilerBackend,
)
from app.strategy_design.adapters.in_memory_strategy_candidate_repository import (
    InMemoryStrategyCandidateRepository,
)
from app.strategy_design.adapters.in_memory_strategy_snapshot_store import (
    InMemoryStrategySnapshotStore,
)
from app.strategy_design.adapters.strategy_http import (
    HttpRequest,
    StrategyHttpAdapter,
)
from app.strategy_design.application.compile_strategy_candidate import (
    CompileStrategyCandidateHandler,
)
from app.strategy_design.application.create_strategy_snapshot import (
    CreateStrategySnapshotHandler,
)
from app.strategy_design.domain.strategy_candidate import (
    CompatibilityFinding,
    CompatibilityFindingCode,
    CompilationDiagnosticCode,
    ParameterDomain,
    RuleExpression,
    RuleExpressionValidation,
    RuleOrigin,
    RuleOriginType,
    StrategyCandidate,
    StrategyCandidateNotFoundError,
    StrategyCandidateStatus,
    StrategyCompiler,
    StrategyConflict,
    StrategyParameter,
    StrategyRule,
    ValidationPlan,
)


class TranslationDecision:
    decision_type = "SUPPORT_STATUS"
    source_research_case_id = "RSC-HTTP-UNIT"
    source_answer_id = "ANS-HTTP-UNIT"
    source_claim_refs = ("CLM-HTTP-UNIT@1",)
    description = "Reponse verifiee traduite en hypothese SD sans regle automatique."
    blocking = False
    details = {"support_status": "SUPPORTED"}


class MapRuleExpressionValidator:
    def __init__(self, validations):
        self._validations = dict(validations)

    def validate(self, rule):
        if rule.rule_id not in self._validations:
            raise AssertionError(f"Validation d'expression absente: {rule.rule_id}")
        return self._validations[rule.rule_id]


class MissingStrategyRepository:
    def __init__(self):
        self.get_calls = []

    def get(self, strategy_id):
        self.get_calls.append(strategy_id)
        raise StrategyCandidateNotFoundError(strategy_id)


def build_outcome():
    return VerifiedResearchOutcome.from_payload(
        {
            "schema_version": "1.0",
            "research_case_id": "RSC-HTTP-UNIT",
            "question": "Le contrat HTTP SD mappe-t-il les diagnostics publics ?",
            "mandate": {
                "universe": "ETF_US_TREASURY",
                "horizon": "swing",
                "risk_limit": "drawdown_10pct",
            },
            "answer_id": "ANS-HTTP-UNIT",
            "support_status": "SUPPORTED",
            "claim_refs": ["CLM-HTTP-UNIT@1"],
            "unresolved_conflicts": [],
            "knowledge_gaps": [],
            "completed_at": "2026-07-04T13:30:00Z",
        }
    )


def build_complete_candidate(strategy_id):
    candidate = StrategyCandidate.create_from_verified_research(
        strategy_id=strategy_id,
        verified_research=build_outcome(),
        translation_decisions=(TranslationDecision(),),
        expected_version=0,
    )
    rule_id = f"{strategy_id}-RULE-ENTRY"
    candidate = candidate.add_rule(
        rule=StrategyRule.without_origin(
            rule_id=rule_id,
            rule_kind="ENTRY",
            expression=RuleExpression.from_text("trend_60d > 0"),
        ),
        expected_version=candidate.version,
    )
    candidate = candidate.assign_rule_origin(
        rule_id=rule_id,
        origin=RuleOrigin.source(
            verified_claim_refs=("CLM-HTTP-UNIT@1",),
            evidence_refs=("EVS-HTTP-UNIT",),
        ),
        expected_version=candidate.version,
    )
    candidate = candidate.add_parameter(
        parameter=StrategyParameter.unresolved(
            parameter_id=f"PARAM-{strategy_id.rsplit('-', 1)[-1]}",
            name="lookback_days",
            origin_type=RuleOriginType.PARAMETER_TO_CALIBRATE,
            blocking=True,
            unresolved_reason="Domaine requis.",
        ),
        expected_version=candidate.version,
    )
    candidate = candidate.define_calibration_plan(
        parameter_id=f"PARAM-{strategy_id.rsplit('-', 1)[-1]}",
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
    return candidate, rule_id


def build_adapter(repository, validations, backend=None, snapshot_store=None):
    if backend is None:
        backend = DeterministicStrategyCompilerBackend()
    if snapshot_store is None:
        snapshot_store = InMemoryStrategySnapshotStore.empty()
    compiler = StrategyCompiler(
        backend=backend,
        expression_validator=MapRuleExpressionValidator(validations),
        compiler_version="m010-http-unit-compiler-v1",
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


def compile_request(strategy_id, version):
    return HttpRequest(
        method="POST",
        path="/v1/strategies/compile",
        body={
            "strategy_id": strategy_id,
            "expected_version": version,
            "create_snapshot": False,
            "idempotency_key": f"CMD-{strategy_id}",
            "occurred_at": "2026-07-04T13:40:00Z",
        },
    )


# DTO strict: champs inconnus et champs de stockage public interdits.
candidate, rule_id = build_complete_candidate("STRAT-HTTP-UNIT-OK")
repository = InMemoryStrategyCandidateRepository({"STRAT-HTTP-UNIT-OK": candidate})
adapter = build_adapter(
    repository,
    {
        rule_id: RuleExpressionValidation.deterministic(
            rule_id=rule_id,
            normalized_expression="trend_60d > 0",
        )
    },
)

unknown = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/strategies/compile",
        body={
            "strategy_id": "STRAT-HTTP-UNIT-OK",
            "expected_version": candidate.version,
            "create_snapshot": False,
            "idempotency_key": "CMD-UNKNOWN-FIELD",
            "occurred_at": "2026-07-04T13:41:00Z",
            "unexpected_field": "forbidden",
        },
    )
)
assert unknown.status_code == 400
assert unknown.body == {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}

forbidden = adapter.handle(
    HttpRequest(
        method="POST",
        path="/v1/strategies/compile",
        body={
            "strategy_id": "STRAT-HTTP-UNIT-OK",
            "expected_version": candidate.version,
            "create_snapshot": False,
            "idempotency_key": "CMD-FORBIDDEN-FIELD",
            "occurred_at": "2026-07-04T13:42:00Z",
            "profitability_claim": "12pct",
        },
    )
)
assert forbidden.status_code == 400
assert forbidden.body == {"error_code": "PUBLIC_STORAGE_FIELD_FORBIDDEN", "field": "body"}

bad_get = adapter.handle(
    HttpRequest(
        method="GET",
        path="/v1/strategies/STRAT-HTTP-UNIT-OK",
        body={"raw_research_payload": True},
    )
)
assert bad_get.status_code == 400
assert bad_get.body == {"error_code": "PUBLIC_STORAGE_FIELD_FORBIDDEN", "field": "body"}


# GET absent: pas de creation implicite ni fallback vers strategie vide.
missing_repository = MissingStrategyRepository()
missing_adapter = build_adapter(missing_repository, {})
missing = missing_adapter.handle(
    HttpRequest(
        method="GET",
        path="/v1/strategies/STRAT-HTTP-UNKNOWN",
        body={},
    )
)
assert missing.status_code == 404
assert missing.body == {"error_code": "STRATEGY_NOT_FOUND"}
assert missing_repository.get_calls == ["STRAT-HTTP-UNKNOWN"]


# Mapping explicite d'un conflit documentaire bloquant.
conflict_candidate, conflict_rule_id = build_complete_candidate("STRAT-HTTP-CONFLICT")
conflict_candidate = conflict_candidate.record_conflict(
    conflict=StrategyConflict.blocking_documentary_conflict(
        conflict_id="CONFLICT-HTTP-001",
        description="Conflit documentaire non resolu pour la regle exposee.",
    ),
    expected_version=conflict_candidate.version,
)
conflict_candidate = conflict_candidate.validate_candidate(
    expected_version=conflict_candidate.version,
)
assert any(
    diagnostic.code is CompilationDiagnosticCode.STRATEGY_CONFLICT_BLOCKING
    for diagnostic in conflict_candidate.compilation_diagnostics
)
conflict_repository = InMemoryStrategyCandidateRepository(
    {"STRAT-HTTP-CONFLICT": conflict_candidate}
)
conflict_adapter = build_adapter(
    conflict_repository,
    {
        conflict_rule_id: RuleExpressionValidation.deterministic(
            rule_id=conflict_rule_id,
            normalized_expression="trend_60d > 0",
        )
    },
)
conflict_response = conflict_adapter.handle(
    compile_request("STRAT-HTTP-CONFLICT", conflict_candidate.version)
)
assert conflict_response.status_code == 409
assert conflict_response.body["error_code"] == "STRATEGY_CONFLICT_UNRESOLVED"
assert any(
    diagnostic["error_code"] == "STRATEGY_CONFLICT_UNRESOLVED"
    for diagnostic in conflict_response.body["diagnostics"]
)


# Mapping explicite d'une donnee actuelle requise.
current_data_candidate, current_data_rule_id = build_complete_candidate("STRAT-HTTP-CURRENT-DATA")
current_data_finding = CompatibilityFinding(
    code=CompatibilityFindingCode.POINT_IN_TIME_VIOLATION,
    description="La donnee est publiee apres le moment de decision.",
    blocking=True,
    rule_id=current_data_rule_id,
    parameter_id=None,
)
current_data_candidate = replace(
    current_data_candidate,
    status=StrategyCandidateStatus.INCONSISTENT,
    compatibility_findings=(current_data_finding,),
    compilation_diagnostics=(current_data_finding.to_diagnostic(),),
)
current_data_repository = InMemoryStrategyCandidateRepository(
    {"STRAT-HTTP-CURRENT-DATA": current_data_candidate}
)
current_data_adapter = build_adapter(
    current_data_repository,
    {
        current_data_rule_id: RuleExpressionValidation.deterministic(
            rule_id=current_data_rule_id,
            normalized_expression="trend_60d > 0",
        )
    },
)
current_data_response = current_data_adapter.handle(
    compile_request("STRAT-HTTP-CURRENT-DATA", current_data_candidate.version)
)
assert current_data_response.status_code == 422
assert current_data_response.body["error_code"] == "CURRENT_DATA_REQUIRED"
assert any(
    diagnostic["error_code"] == "CURRENT_DATA_REQUIRED"
    and diagnostic["rule_id"] == current_data_rule_id
    for diagnostic in current_data_response.body["diagnostics"]
)

print("Tests unitaires du contrat HTTP strategies M-010: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m010_strategy_http_contract_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires du contrat HTTP strategies M-010 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
