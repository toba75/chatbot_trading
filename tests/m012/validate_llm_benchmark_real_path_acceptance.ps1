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
    PROMOTION_ACCEPTED,
    PROMOTION_REJECTED,
    REQUIRED_LLM_CHECKPOINTS,
    REQUIRED_LLM_TASKS,
    REQUIRED_LLM_TECHNICAL_METRICS,
    CheckpointCandidate,
    CheckpointMeasurement,
    LlmBenchmarkSuite,
    LlmRealPathAttestation,
    LlmTechnicalMetric,
    StructuredOutputEvaluation,
)

POLICY_VERSION = "LlmRealPathBenchmarkPolicy-1.0"


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


def candidate(checkpoint_id, origin):
    return CheckpointCandidate(
        checkpoint_id=checkpoint_id,
        origin=origin,
        serving_profile_id=f"SERVE-M012-{checkpoint_id.replace('/', '-').upper()}",
    )


def real_path():
    return LlmRealPathAttestation(
        path_id="LLM-PATH-M012-REAL",
        segments=("docker-local", "llm-gateway", "reseau-prive", "vllm-spark"),
        gateway_trace_id="GWTRACE-M012-LLM-REAL",
        network_policy_id="NETPOL-M002-SPARK-PRIVATE",
        vllm_route_id="VLLM-SPARK-GEMMA4",
    )


def technical_metrics(**overrides):
    values = {
        "llm_gateway_latency_ms": "42.000000000000",
        "llm_network_latency_ms": "8.000000000000",
        "llm_vllm_queue_time_ms": "12.000000000000",
        "llm_time_to_first_token_ms": "310.000000000000",
        "llm_tokens_per_second": "47.500000000000",
        "llm_error_rate": "0.000000000000",
        "llm_retry_before_first_token_total": "1.000000000000",
        "llm_structured_output_stability_rate": "1.000000000000",
        "llm_spark_restart_recovery_rate": "1.000000000000",
    }
    values.update(overrides)
    return tuple(
        LlmTechnicalMetric(
            name=name,
            value=value,
            numerator=1,
            denominator=1,
            public_labels=("checkpoint", "m012"),
        )
        for name, value in values.items()
    )


def evaluation(task_name, **overrides):
    payload = {
        "evaluation_id": f"EVAL-M012-{task_name}",
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
        "retry_idempotency_key": f"IDEMP-M012-{task_name}",
    }
    payload.update(overrides)
    return StructuredOutputEvaluation(**payload)


def evaluations(**task_overrides):
    return tuple(
        evaluation(task_name, **task_overrides.get(task_name, {}))
        for task_name in REQUIRED_LLM_TASKS
    )


def measurement(checkpoint_id, origin, *, task_overrides=None, metric_overrides=None, fallback_checkpoint_id=None):
    return CheckpointMeasurement(
        candidate=candidate(checkpoint_id, origin),
        path_attestation=real_path(),
        structured_outputs=evaluations(**(task_overrides or {})),
        technical_metrics=technical_metrics(**(metric_overrides or {})),
        fallback_checkpoint_id=fallback_checkpoint_id,
    )


# Given les checkpoints obligatoires officiels et communautaire de Gemma.
assert_equal(
    REQUIRED_LLM_CHECKPOINTS,
    (
        "nvidia/Gemma-4-31B-IT-NVFP4",
        "YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ",
        "google/gemma-4-31B-it-qat-w4a16-ct",
    ),
    "Les checkpoints normatifs doivent être verrouillés.",
)

suite = LlmBenchmarkSuite(policy_version=POLICY_VERSION)

# When les checkpoints sont évalués par docker-local -> llm-gateway -> réseau privé -> vLLM sur Spark.
run = suite.measure(
    run_id="LLMRUN-M012-REAL-PATH",
    measurements=(
        measurement("nvidia/Gemma-4-31B-IT-NVFP4", OFFICIAL_CHECKPOINT_ORIGIN),
        measurement("google/gemma-4-31B-it-qat-w4a16-ct", OFFICIAL_CHECKPOINT_ORIGIN),
        measurement(
            "YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ",
            COMMUNITY_CHECKPOINT_ORIGIN,
            task_overrides={"contradiction": {"contradiction_detected": False}},
        ),
    ),
)

# Then les tâches LLM et métriques techniques sont publiées séparément sans payload sensible.
assert_equal(run.checkpoint_count, 3, "Tous les checkpoints obligatoires doivent être mesurés.")
assert_equal(set(run.task_names), set(REQUIRED_LLM_TASKS), "Toutes les tâches LLM obligatoires doivent être couvertes.")
assert_equal(set(run.technical_metric_names), set(REQUIRED_LLM_TECHNICAL_METRICS), "Toutes les métriques techniques doivent être couvertes.")
assert_equal(
    run.measurements_by_checkpoint["nvidia/Gemma-4-31B-IT-NVFP4"].path_attestation.segments,
    ("docker-local", "llm-gateway", "reseau-prive", "vllm-spark"),
    "Le chemin réel doit être attesté.",
)
assert_equal(
    run.measurements_by_checkpoint["YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ"].task_success_rates["contradiction"].value,
    "0.000000000000",
    "Une contradiction non détectée doit rester un échec scientifique.",
)
assert not run.measurements_by_checkpoint["YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ"].eligible_for_promotion

promotion = suite.evaluate_promotion(
    run=run,
    checkpoint_id="YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ",
)
assert_equal(promotion.status, PROMOTION_REJECTED, "Une promotion communautaire insuffisante doit être refusée.")
assert "contradiction" in " ".join(promotion.reasons)

accepted_run = suite.measure(
    run_id="LLMRUN-M012-REAL-PATH-ACCEPTED",
    measurements=(
        measurement("nvidia/Gemma-4-31B-IT-NVFP4", OFFICIAL_CHECKPOINT_ORIGIN),
        measurement("google/gemma-4-31B-it-qat-w4a16-ct", OFFICIAL_CHECKPOINT_ORIGIN),
        measurement("YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ", COMMUNITY_CHECKPOINT_ORIGIN),
    ),
)
accepted_promotion = suite.evaluate_promotion(
    run=accepted_run,
    checkpoint_id="YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ",
)
assert_equal(accepted_promotion.status, PROMOTION_ACCEPTED, "Une promotion égale aux références et techniquement exploitable doit être acceptée.")

assert_raises(
    "checkpoint obligatoire absent",
    lambda: suite.measure(
        run_id="LLMRUN-M012-MISSING-CHECKPOINT",
        measurements=(
            measurement("nvidia/Gemma-4-31B-IT-NVFP4", OFFICIAL_CHECKPOINT_ORIGIN),
            measurement("YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ", COMMUNITY_CHECKPOINT_ORIGIN),
        ),
    ),
)
assert_raises(
    "tache LLM obligatoire absente",
    lambda: CheckpointMeasurement(
        candidate=candidate("nvidia/Gemma-4-31B-IT-NVFP4", OFFICIAL_CHECKPOINT_ORIGIN),
        path_attestation=real_path(),
        structured_outputs=tuple(e for e in evaluations() if e.task_name != "citations"),
        technical_metrics=technical_metrics(),
    ),
)
assert_raises(
    "metrique technique LLM absente",
    lambda: CheckpointMeasurement(
        candidate=candidate("nvidia/Gemma-4-31B-IT-NVFP4", OFFICIAL_CHECKPOINT_ORIGIN),
        path_attestation=real_path(),
        structured_outputs=evaluations(),
        technical_metrics=tuple(metric for metric in technical_metrics() if metric.name != "llm_time_to_first_token_ms"),
    ),
)
assert_raises(
    "chemin direct Spark interdit",
    lambda: LlmRealPathAttestation(
        path_id="LLM-PATH-M012-DIRECT",
        segments=("docker-local", "vllm-spark"),
        gateway_trace_id="GWTRACE-M012-DIRECT",
        network_policy_id="NETPOL-M002-SPARK-PRIVATE",
        vllm_route_id="VLLM-SPARK-GEMMA4",
    ),
)
assert_raises(
    "fallback checkpoint interdit",
    lambda: measurement(
        "nvidia/Gemma-4-31B-IT-NVFP4",
        OFFICIAL_CHECKPOINT_ORIGIN,
        fallback_checkpoint_id="google/gemma-4-31B-it-qat-w4a16-ct",
    ),
)
assert_raises(
    "payload sensible interdit",
    lambda: LlmTechnicalMetric(
        name="llm_gateway_latency_ms",
        value="42.000000000000",
        numerator=1,
        denominator=1,
        public_labels=("prompt complet: acheter maintenant",),
    ),
)
assert not evaluation("json_valide", response_json="{json-invalide").passed

print("Test d'acceptation T-009 benchmark LLM chemin réel M-012: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m012_llm_real_path_benchmark_acceptance_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Test d'acceptation T-009 benchmark LLM chemin réel M-012 invalide. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
