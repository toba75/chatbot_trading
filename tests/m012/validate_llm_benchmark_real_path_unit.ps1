$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.llm_real_path_benchmark import (
    COMMUNITY_CHECKPOINT_ORIGIN,
    OFFICIAL_CHECKPOINT_ORIGIN,
    CheckpointCandidate,
    CheckpointMeasurement,
    LlmBenchmarkSuite,
    LlmRealPathAttestation,
    LlmTechnicalMetric,
    StructuredOutputEvaluation,
)


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(expected_fragment, action):
    try:
        action()
    except (TypeError, ValueError) as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(f"Erreur inattendue: {exc}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {expected_fragment}")


def candidate(checkpoint_id="nvidia/Gemma-4-31B-IT-NVFP4", origin=OFFICIAL_CHECKPOINT_ORIGIN):
    return CheckpointCandidate(
        checkpoint_id=checkpoint_id,
        origin=origin,
        serving_profile_id="SERVE-M012-UNIT",
    )


def path():
    return LlmRealPathAttestation(
        path_id="LLM-PATH-M012-UNIT",
        segments=("docker-local", "llm-gateway", "reseau-prive", "vllm-spark"),
        gateway_trace_id="GWTRACE-M012-UNIT",
        network_policy_id="NETPOL-M002-SPARK-PRIVATE",
        vllm_route_id="VLLM-SPARK-GEMMA4",
    )


def metric(name, value="1.000000000000", numerator=1, denominator=1, public_labels=("m012",)):
    return LlmTechnicalMetric(
        name=name,
        value=value,
        numerator=numerator,
        denominator=denominator,
        public_labels=public_labels,
    )


def all_metrics():
    return (
        metric("llm_gateway_latency_ms", "40.000000000000"),
        metric("llm_network_latency_ms", "7.000000000000"),
        metric("llm_vllm_queue_time_ms", "11.000000000000"),
        metric("llm_time_to_first_token_ms", "300.000000000000"),
        metric("llm_tokens_per_second", "50.000000000000"),
        metric("llm_error_rate", "0.000000000000"),
        metric("llm_retry_before_first_token_total", "1.000000000000"),
        metric("llm_structured_output_stability_rate", "1.000000000000"),
        metric("llm_spark_restart_recovery_rate", "1.000000000000"),
    )


def evaluation(task_name, **overrides):
    payload = {
        "evaluation_id": f"EVAL-M012-UNIT-{task_name}",
        "task_name": task_name,
        "response_json": '{"answer":"ok","citations":["SRC-1"],"tool_call":{"name":"lookup"}}',
        "atomic_extraction_complete": True,
        "negations_preserved": True,
        "numeric_values_exact": True,
        "conditions_preserved": True,
        "limits_preserved": True,
        "entailment_correct": True,
        "contradiction_detected": True,
        "fr_en_synthesis_valid": True,
        "tool_call_valid": True,
        "citations_resolved": True,
        "retry_before_first_token_total": 1,
        "retry_after_first_token_total": 0,
        "retry_limit": 2,
        "retry_idempotency_key": f"IDEMP-M012-UNIT-{task_name}",
    }
    payload.update(overrides)
    return StructuredOutputEvaluation(**payload)


def all_evaluations(**overrides_by_task):
    tasks = (
        "json_valide",
        "extraction_atomique",
        "conservation_negations",
        "exactitude_nombres",
        "conditions_application",
        "limites",
        "entailment",
        "contradiction",
        "synthese_fr_en",
        "tool_calling",
        "citations",
    )
    return tuple(evaluation(task, **overrides_by_task.get(task, {})) for task in tasks)


def measurement(checkpoint=None, evaluations=None, metrics=None):
    return CheckpointMeasurement(
        candidate=checkpoint or candidate(),
        path_attestation=path(),
        structured_outputs=evaluations or all_evaluations(),
        technical_metrics=metrics or all_metrics(),
    )


valid_json_evaluation = evaluation("json_valide")
assert_equal(valid_json_evaluation.passed, True, "Un JSON valide doit réussir la tâche JSON.")
assert_equal(hasattr(valid_json_evaluation, "response_json"), False, "Le JSON brut ne doit pas rester exposé.")
assert_equal(len(valid_json_evaluation.response_json_sha256), 64, "Le hash du JSON doit rester traçable.")
assert_equal(evaluation("json_valide", response_json="not-json").passed, False, "Un JSON invalide doit échouer.")
assert_equal(evaluation("extraction_atomique", atomic_extraction_complete=False).passed, False, "Une extraction atomique incomplète doit échouer.")
assert_equal(evaluation("conservation_negations", negations_preserved=False).passed, False, "Une négation perdue doit échouer.")
assert_equal(evaluation("exactitude_nombres", numeric_values_exact=False).passed, False, "Un nombre modifié doit échouer.")
assert_equal(evaluation("conditions_application", conditions_preserved=False).passed, False, "Une condition d'application perdue doit échouer.")
assert_equal(evaluation("limites", limits_preserved=False).passed, False, "Une limite omise doit échouer.")
assert_equal(evaluation("entailment", entailment_correct=False).passed, False, "Un entailment faux doit échouer.")
assert_equal(evaluation("contradiction", contradiction_detected=False).passed, False, "Une contradiction non détectée doit échouer.")
assert_equal(evaluation("synthese_fr_en", fr_en_synthesis_valid=False).passed, False, "Une synthèse FR/EN dégradée doit échouer.")
assert_equal(evaluation("tool_calling", tool_call_valid=False).passed, False, "Un tool call invalide doit échouer.")
assert_equal(evaluation("citations", citations_resolved=False).passed, False, "Une citation absente doit échouer.")

assert_raises("retry après premier token interdit", lambda: evaluation("json_valide", retry_after_first_token_total=1))
assert_raises("retry illimité interdit", lambda: evaluation("json_valide", retry_limit=0))
assert_raises("clé idempotence retry requise", lambda: evaluation("json_valide", retry_before_first_token_total=1, retry_idempotency_key=""))
assert_raises("checkpoint inconnu", lambda: candidate("autre/checkpoint", OFFICIAL_CHECKPOINT_ORIGIN))
assert_raises("origine checkpoint invalide", lambda: candidate(origin="MIRROR"))
assert_raises("métrique technique LLM inconnue", lambda: metric("llm_prompt_payload"))
assert_raises("payload sensible interdit", lambda: metric("llm_gateway_latency_ms", public_labels=("réponse complète: secret",)))
for forbidden_label in ("Authorization: Bearer secret", "api_key=secret", "password=secret", "mot de passe: secret", "sk-secret"):
    assert_raises(
        "payload sensible interdit",
        lambda forbidden_label=forbidden_label: metric("llm_gateway_latency_ms", public_labels=(forbidden_label,)),
    )
assert_raises("valeur métrique invalide", lambda: metric("llm_gateway_latency_ms", "NaN"))
assert_raises("dénominateur métrique invalide", lambda: metric("llm_gateway_latency_ms", denominator=0))
assert_raises(
    "chemin LLM réel invalide",
    lambda: LlmRealPathAttestation(
        path_id="LLM-PATH-M012-BAD",
        segments=("docker-local", "llm-gateway", "vllm-spark"),
        gateway_trace_id="GWTRACE-M012-BAD",
        network_policy_id="NETPOL-M002-SPARK-PRIVATE",
        vllm_route_id="VLLM-SPARK-GEMMA4",
    ),
)

suite = LlmBenchmarkSuite(policy_version="LlmRealPathBenchmarkPolicy-1.0")
run = suite.measure(
    run_id="LLMRUN-M012-UNIT",
    measurements=(
        measurement(candidate("nvidia/Gemma-4-31B-IT-NVFP4", OFFICIAL_CHECKPOINT_ORIGIN)),
        measurement(candidate("google/gemma-4-31B-it-qat-w4a16-ct", OFFICIAL_CHECKPOINT_ORIGIN)),
        measurement(
            candidate("YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ", COMMUNITY_CHECKPOINT_ORIGIN),
            evaluations=all_evaluations(exactitude_nombres={"numeric_values_exact": False}),
        ),
    ),
)
community = run.measurements_by_checkpoint["YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ"]
assert_equal(community.task_success_rates["exactitude_nombres"].value, "0.000000000000", "La métrique de tâche doit exposer l'échec.")
assert_equal(community.eligible_for_promotion, False, "Une tâche normative en échec interdit la promotion.")
assert_equal(suite.evaluate_promotion(run=run, checkpoint_id="YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ").status, "REJECTED", "La promotion doit être refusée.")

assert_raises(
    "promotion réservée aux checkpoints communautaires",
    lambda: suite.evaluate_promotion(run=run, checkpoint_id="nvidia/Gemma-4-31B-IT-NVFP4"),
)
assert_raises(
    "checkpoint benchmark absent",
    lambda: suite.evaluate_promotion(run=run, checkpoint_id="absent/checkpoint"),
)

print("Tests unitaires T-009 benchmark LLM chemin réel M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_llm_real_path_benchmark_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
Set-Content -Encoding UTF8 -LiteralPath $pythonScriptPath -Value $pythonCode
try {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $env:PYTHONIOENCODING = "utf-8"
        $output = & $pythonExecutable -B $pythonScriptPath $repoRoot 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw "Tests unitaires T-009 benchmark LLM chemin réel M-012 invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
