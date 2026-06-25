$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$strategySnapshotFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/sd_to_ex_strategy_snapshot_v1.json"
$exToRaResultFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/ex_to_ra_experiment_result_v1.json"
$exToCvResultFixturePath = Join-Path $repoRoot "tests/fixtures/m001/contracts/ex_to_cv_experiment_result_v1.json"

foreach ($fixturePath in @($strategySnapshotFixturePath, $exToRaResultFixturePath, $exToCvResultFixturePath)) {
    if (-not (Test-Path -LiteralPath $fixturePath -PathType Leaf)) {
        throw "Fixture de contrat stratégie expérience absente: $fixturePath"
    }
}

$pythonCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])

from app.contracts.strategy_experiments import ExperimentResult, StrategySnapshot


def load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_raises(expected_fragment, action):
    try:
        action()
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}")
    else:
        raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def assert_no_internal_sd_or_ex_keys(payload):
    forbidden_keys = {
        "backtest_engine_state",
        "experiment_repository_id",
        "mutable_strategy_candidate",
        "open_parameter_state",
        "pnl_expectation",
        "profitability_statement",
        "rentability_claim",
        "sd_internal_state",
        "strategy_candidate_id",
        "strategy_repository_id",
    }

    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in forbidden_keys:
                raise AssertionError(f"Modèle interne SD ou EX exposé dans le contrat: {key}")
            assert_no_internal_sd_or_ex_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_internal_sd_or_ex_keys(item)


strategy_payload = load_payload(sys.argv[2])
ex_to_ra_payload = load_payload(sys.argv[3])
ex_to_cv_payload = load_payload(sys.argv[4])

# Given SD a produit un snapshot complet et hashé.
strategy_snapshot = StrategySnapshot.from_payload(strategy_payload)

# When EX planifie une expérience puis publie un résultat vers RA et CV.
ra_result = ExperimentResult.from_payload(ex_to_ra_payload)
cv_result = ExperimentResult.from_payload(ex_to_cv_payload)

# Then EX consomme uniquement le snapshot immuable et retourne un résultat rattaché aux entrées figées.
if strategy_snapshot.status != "COMPILABLE":
    raise AssertionError("Le snapshot transmis à EX doit être compilable.")
if strategy_snapshot.strategy_version_id != ra_result.strategy_version_id:
    raise AssertionError("Le résultat EX doit rester lié à strategy_version_id.")
if ra_result != cv_result:
    raise AssertionError("RA et CV doivent consommer le même langage publié ExperimentResult.")
if ra_result.frozen_inputs["strategy_snapshot_hash"] != strategy_snapshot.spec_hash:
    raise AssertionError("Le résultat EX doit référencer le hash du snapshot exécuté.")
if ra_result.frozen_inputs["data_snapshot_id"] != ra_result.data_snapshot_id:
    raise AssertionError("Le résultat EX doit rattacher l'entrée figée au data_snapshot_id.")
if not strategy_snapshot.rules or not strategy_snapshot.parameters or not strategy_snapshot.constraints:
    raise AssertionError("Le snapshot doit publier règles, paramètres et contraintes.")
if not strategy_snapshot.evidence_refs:
    raise AssertionError("Le snapshot doit conserver ses preuves publiées.")
if not ra_result.metrics or not ra_result.diagnostics or not ra_result.artifacts:
    raise AssertionError("Le résultat doit publier métriques, diagnostics et artefacts.")

for payload in (strategy_payload, ex_to_ra_payload, ex_to_cv_payload):
    assert_no_internal_sd_or_ex_keys(payload)

strategy_without_hash = dict(strategy_payload)
del strategy_without_hash["spec_hash"]
assert_raises("spec_hash absent", lambda: StrategySnapshot.from_payload(strategy_without_hash))

unresolved_blocking_parameter = dict(strategy_payload)
unresolved_blocking_parameter["parameters"] = [
    dict(parameter) for parameter in strategy_payload["parameters"]
]
unresolved_blocking_parameter["parameters"][0]["resolution_status"] = "UNRESOLVED"
unresolved_blocking_parameter["parameters"][0]["blocking"] = True
assert_raises(
    "paramètre bloquant non résolu",
    lambda: StrategySnapshot.from_payload(unresolved_blocking_parameter),
)

mutable_strategy_reference = dict(strategy_payload)
mutable_strategy_reference["rules"] = [dict(rule) for rule in strategy_payload["rules"]]
mutable_strategy_reference["rules"][0]["mutable_reference"] = "strategy_candidate:STRAT-000017/current"
assert_raises(
    "référence mutable interdite",
    lambda: StrategySnapshot.from_payload(mutable_strategy_reference),
)

mutable_result_input = dict(ex_to_ra_payload)
mutable_result_input["frozen_inputs"] = dict(ex_to_ra_payload["frozen_inputs"])
mutable_result_input["frozen_inputs"]["mutable_input"] = "market-data:latest"
assert_raises(
    "entrée mutable interdite",
    lambda: ExperimentResult.from_payload(mutable_result_input),
)

implicit_status = dict(ex_to_ra_payload)
del implicit_status["status"]
assert_raises("status absent", lambda: ExperimentResult.from_payload(implicit_status))

result_without_diagnostics = dict(ex_to_ra_payload)
del result_without_diagnostics["diagnostics"]
assert_raises(
    "diagnostics absent",
    lambda: ExperimentResult.from_payload(result_without_diagnostics),
)

profitability_claim = dict(ex_to_ra_payload)
profitability_claim["profitability_statement"] = "validated"
assert_raises(
    "déclaration de rentabilité interdite",
    lambda: ExperimentResult.from_payload(profitability_claim),
)

print("Contrats StrategySnapshot et ExperimentResult M-001 acceptés.")
'@

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m001_strategy_experiment_contracts_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $output = & python -B $pythonScriptPath $repoRoot $strategySnapshotFixturePath $exToRaResultFixturePath $exToCvResultFixturePath 2>&1
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Remove-Item -LiteralPath $pythonScriptPath -Force
}

if ($LASTEXITCODE -ne 0) {
    throw ($output -join "`n")
}

Write-Host "Test d'acceptation des contrats StrategySnapshot et ExperimentResult M-001: OK"
