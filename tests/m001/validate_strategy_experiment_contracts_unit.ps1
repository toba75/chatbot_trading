$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable

$pythonCode = @'
import sys

sys.path.insert(0, sys.argv[1])

from app.contracts.strategy_experiments import (
    ALLOWED_EXPERIMENT_RESULT_STATUSES,
    COMPILABLE_STRATEGY_STATUS,
    COMPLETED_EXPERIMENT_STATUS,
    FAILED_EXPERIMENT_STATUS,
    ExperimentResult,
    StrategySnapshot,
)


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def strategy_payload():
    return {
        "schema_version": "1.0",
        "strategy_id": "STRAT-000017",
        "strategy_version_id": "SVER-000006",
        "spec_hash": "a" * 64,
        "status": COMPILABLE_STRATEGY_STATUS,
        "rules": [
            {
                "rule_id": "STRAT-000017-RULE-001",
                "kind": "SIGNAL",
                "expression": "close_200d > close_50d",
                "origin": "SOURCE",
                "evidence_refs": ["CLM-004812@3"],
                "deterministic": True,
            }
        ],
        "parameters": [
            {
                "name": "lookback_fast",
                "unit": "trading_day",
                "value": 50,
                "origin": "DESIGN_CHOICE",
                "blocking": True,
                "resolution_status": "RESOLVED",
            }
        ],
        "constraints": [
            {
                "name": "max_leverage",
                "value": 1.0,
                "origin": "USER_CONSTRAINT",
            }
        ],
        "data_requirements": [
            {
                "name": "daily_adjusted_close",
                "frequency": "daily",
                "point_in_time": True,
            }
        ],
        "validation_plan": {
            "walk_forward": "anchored",
            "costs": "commissions_spread_slippage",
        },
        "evidence_refs": ["CLM-004812@3"],
        "created_at": "2026-06-21T10:00:00Z",
    }


def result_payload():
    return {
        "schema_version": "1.0",
        "experiment_id": "EXP-000123",
        "strategy_version_id": "SVER-000006",
        "data_snapshot_id": "DATA-000044",
        "result_hash": "b" * 64,
        "code_version": "git:0335a23",
        "status": COMPLETED_EXPERIMENT_STATUS,
        "frozen_inputs": {
            "strategy_snapshot_hash": "a" * 64,
            "data_snapshot_id": "DATA-000044",
            "data_snapshot_hash": "c" * 64,
            "cost_model_hash": "d" * 64,
            "execution_environment_hash": "e" * 64,
            "frozen_at": "2026-06-21T10:05:00Z",
        },
        "metrics": {
            "annualized_return": {
                "value": 0.071,
                "unit": "ratio",
                "period": "2014-2024",
                "benchmark": "cash",
                "universe": "liquid_futures",
                "costs": "included",
                "assumptions": ["no survivorship bias", "point-in-time data"],
            }
        },
        "diagnostics": {
            "bias_checks": ["look_ahead_bias_checked", "survivorship_bias_checked"],
            "warnings": ["sample size limited"],
        },
        "artifacts": [
            {
                "artifact_id": "EXP-000123-REPORT",
                "artifact_type": "summary_report",
                "artifact_hash": "f" * 64,
            }
        ],
        "started_at": "2026-06-21T10:10:00Z",
        "completed_at": "2026-06-21T10:12:00Z",
    }


snapshot = StrategySnapshot.from_payload(strategy_payload())
if StrategySnapshot.from_json(snapshot.to_json()) != snapshot:
    raise AssertionError("Le round-trip StrategySnapshot doit rester stable.")
if StrategySnapshot.from_json(snapshot.to_json()).to_json() != snapshot.to_json():
    raise AssertionError("La sérialisation StrategySnapshot doit être déterministe.")

snapshot_json = snapshot.to_json()
try:
    snapshot.rules[0]["kind"] = "MUTATED"
except TypeError:
    pass
else:
    raise AssertionError("StrategySnapshot.rules doit etre immuable apres validation.")
if snapshot.to_json() != snapshot_json:
    raise AssertionError("Une mutation externe ne doit pas modifier StrategySnapshot.")

result = ExperimentResult.from_payload(result_payload())
if ExperimentResult.from_json(result.to_json()) != result:
    raise AssertionError("Le round-trip ExperimentResult doit rester stable.")
if ExperimentResult.from_json(result.to_json()).to_json() != result.to_json():
    raise AssertionError("La sérialisation ExperimentResult doit être déterministe.")

result_json = result.to_json()
try:
    result.frozen_inputs["data_snapshot_id"] = "DATA-999999"
except TypeError:
    pass
else:
    raise AssertionError("ExperimentResult.frozen_inputs doit etre immuable apres validation.")
if result.to_json() != result_json:
    raise AssertionError("Une mutation externe ne doit pas modifier ExperimentResult.")

if FAILED_EXPERIMENT_STATUS not in ALLOWED_EXPERIMENT_RESULT_STATUSES:
    raise AssertionError("Les résultats échoués doivent rester représentables.")

missing_strategy_version_id = strategy_payload()
del missing_strategy_version_id["strategy_version_id"]
assert_raises(
    "strategy_version_id absent",
    lambda: StrategySnapshot.from_payload(missing_strategy_version_id),
)

invalid_strategy_version_id = strategy_payload()
invalid_strategy_version_id["strategy_version_id"] = "STRAT-000006"
assert_raises(
    "strategy_version_id invalide",
    lambda: StrategySnapshot.from_payload(invalid_strategy_version_id),
)

missing_hash = strategy_payload()
del missing_hash["spec_hash"]
assert_raises("spec_hash absent", lambda: StrategySnapshot.from_payload(missing_hash))

invalid_hash = strategy_payload()
invalid_hash["spec_hash"] = "not-a-hash"
assert_raises("spec_hash invalide", lambda: StrategySnapshot.from_payload(invalid_hash))

not_compilable = strategy_payload()
not_compilable["status"] = "DRAFT"
assert_raises("status non autorise", lambda: StrategySnapshot.from_payload(not_compilable))

missing_rules = strategy_payload()
del missing_rules["rules"]
assert_raises("rules absent", lambda: StrategySnapshot.from_payload(missing_rules))

empty_rules = strategy_payload()
empty_rules["rules"] = []
assert_raises("rules vide", lambda: StrategySnapshot.from_payload(empty_rules))

rule_without_evidence = strategy_payload()
rule_without_evidence["rules"] = [dict(rule_without_evidence["rules"][0])]
rule_without_evidence["rules"][0]["evidence_refs"] = []
assert_raises("evidence_refs vide", lambda: StrategySnapshot.from_payload(rule_without_evidence))

unresolved_blocking_parameter = strategy_payload()
unresolved_blocking_parameter["parameters"] = [
    dict(parameter) for parameter in unresolved_blocking_parameter["parameters"]
]
unresolved_blocking_parameter["parameters"][0]["resolution_status"] = "UNRESOLVED"
assert_raises(
    "parametre bloquant non resolu",
    lambda: StrategySnapshot.from_payload(unresolved_blocking_parameter),
)

mutable_reference = strategy_payload()
mutable_reference["constraints"] = [dict(mutable_reference["constraints"][0])]
mutable_reference["constraints"][0]["mutable_reference"] = "strategy_candidate:STRAT-000017/current"
assert_raises("reference mutable interdite", lambda: StrategySnapshot.from_payload(mutable_reference))

case_variant_mutable_reference = strategy_payload()
case_variant_mutable_reference["constraints"] = [
    dict(case_variant_mutable_reference["constraints"][0])
]
case_variant_mutable_reference["constraints"][0]["Mutable_Reference"] = "strategy_candidate:STRAT-000017/current"
assert_raises(
    "reference mutable interdite",
    lambda: StrategySnapshot.from_payload(case_variant_mutable_reference),
)

profitability_statement = strategy_payload()
profitability_statement["profitability_statement"] = "validated"
assert_raises(
    "declaration de rentabilite interdite",
    lambda: StrategySnapshot.from_payload(profitability_statement),
)

case_variant_profitability_statement = strategy_payload()
case_variant_profitability_statement["constraints"] = [
    dict(case_variant_profitability_statement["constraints"][0])
]
case_variant_profitability_statement["constraints"][0]["Profitability_Statement"] = "validated"
assert_raises(
    "declaration de rentabilite interdite",
    lambda: StrategySnapshot.from_payload(case_variant_profitability_statement),
)

missing_data_snapshot_id = result_payload()
del missing_data_snapshot_id["data_snapshot_id"]
assert_raises(
    "data_snapshot_id absent",
    lambda: ExperimentResult.from_payload(missing_data_snapshot_id),
)

wrong_data_snapshot_prefix = result_payload()
wrong_data_snapshot_prefix["data_snapshot_id"] = "EXP-000044"
assert_raises(
    "data_snapshot_id invalide",
    lambda: ExperimentResult.from_payload(wrong_data_snapshot_prefix),
)

missing_result_hash = result_payload()
del missing_result_hash["result_hash"]
assert_raises("result_hash absent", lambda: ExperimentResult.from_payload(missing_result_hash))

implicit_status = result_payload()
implicit_status["status"] = ""
assert_raises("status vide", lambda: ExperimentResult.from_payload(implicit_status))

unknown_status = result_payload()
unknown_status["status"] = "ARCHIVED"
assert_raises("status non autorise", lambda: ExperimentResult.from_payload(unknown_status))

for status in ALLOWED_EXPERIMENT_RESULT_STATUSES:
    payload = result_payload()
    payload["status"] = status
    if status == FAILED_EXPERIMENT_STATUS:
        payload["diagnostics"] = dict(payload["diagnostics"])
        payload["diagnostics"]["failure_reason"] = "erreur reproductible documentee"
    ExperimentResult.from_payload(payload)

failed_without_failure_reason = result_payload()
failed_without_failure_reason["status"] = FAILED_EXPERIMENT_STATUS
failed_without_failure_reason["diagnostics"] = {"warnings": ["generic"]}
assert_raises(
    "diagnostic d'echec requis",
    lambda: ExperimentResult.from_payload(failed_without_failure_reason),
)

failed_with_failure_reason = result_payload()
failed_with_failure_reason["status"] = FAILED_EXPERIMENT_STATUS
failed_with_failure_reason["diagnostics"] = {
    "failure_reason": "donnees insuffisantes pour terminer l'experience",
    "warnings": ["sample size limited"],
}
ExperimentResult.from_payload(failed_with_failure_reason)

missing_frozen_inputs = result_payload()
del missing_frozen_inputs["frozen_inputs"]
assert_raises("frozen_inputs absent", lambda: ExperimentResult.from_payload(missing_frozen_inputs))

mutable_input = result_payload()
mutable_input["frozen_inputs"] = dict(mutable_input["frozen_inputs"])
mutable_input["frozen_inputs"]["mutable_input"] = "market-data:latest"
assert_raises("entree mutable interdite", lambda: ExperimentResult.from_payload(mutable_input))

inconsistent_frozen_input = result_payload()
inconsistent_frozen_input["frozen_inputs"] = dict(inconsistent_frozen_input["frozen_inputs"])
inconsistent_frozen_input["frozen_inputs"]["data_snapshot_id"] = "DATA-999999"
assert_raises(
    "data_snapshot_id incoherent avec frozen_inputs",
    lambda: ExperimentResult.from_payload(inconsistent_frozen_input),
)

missing_metrics = result_payload()
del missing_metrics["metrics"]
assert_raises("metrics absent", lambda: ExperimentResult.from_payload(missing_metrics))

missing_diagnostics = result_payload()
del missing_diagnostics["diagnostics"]
assert_raises("diagnostics absent", lambda: ExperimentResult.from_payload(missing_diagnostics))

missing_artifacts = result_payload()
del missing_artifacts["artifacts"]
assert_raises("artifacts absent", lambda: ExperimentResult.from_payload(missing_artifacts))

profitability_claim = result_payload()
profitability_claim["rentability_claim"] = "profitable"
assert_raises(
    "declaration de rentabilite interdite",
    lambda: ExperimentResult.from_payload(profitability_claim),
)

impossible_created_at = strategy_payload()
impossible_created_at["created_at"] = "2026-02-30T10:00:00Z"
assert_raises("created_at invalide", lambda: StrategySnapshot.from_payload(impossible_created_at))

non_finite_metric = result_payload()
non_finite_metric["metrics"] = dict(non_finite_metric["metrics"])
non_finite_metric["metrics"]["sharpe"] = float("nan")
assert_raises("valeur de contrat invalide", lambda: ExperimentResult.from_payload(non_finite_metric))

internal_experiment_key = result_payload()
internal_experiment_key["diagnostics"] = dict(internal_experiment_key["diagnostics"])
internal_experiment_key["diagnostics"]["retry_policy"] = "interne"
assert_raises("cle interdite", lambda: ExperimentResult.from_payload(internal_experiment_key))

top_level_extra_key = strategy_payload()
top_level_extra_key["strategy_candidate_id"] = "STRAT-CANDIDATE-001"
assert_raises("champ interdit", lambda: StrategySnapshot.from_payload(top_level_extra_key))

print("Invariants unitaires StrategySnapshot et ExperimentResult M-001: OK")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_strategy_experiment_contracts_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Tests unitaires StrategySnapshot et ExperimentResult M-001: OK"
