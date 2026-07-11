$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
. (Join-Path $repoRoot "scripts/require_python.ps1")
$pythonExecutable = Get-RequiredPythonExecutable
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$pythonCode = @'
from __future__ import annotations

import sys

repo_root = sys.argv[1]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from app.evaluation.domain.llm_real_path_benchmark import REQUIRED_LLM_TASKS  # noqa: E402
from app.platform.llm_gateway import LLMGatewayContractError  # noqa: E402
from app.platform.configuration import load_application_configuration  # noqa: E402
from app.platform.local_runtime import (  # noqa: E402
    _build_live_benchmark_task_inference_body,
    _build_product_chat_inference_body,
)


application_configuration = load_application_configuration(
    config_path=f"{repo_root}/config/application.example.yaml",
    environment_snapshot={},
)


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message} Valeur obtenue: {actual!r}")


def assert_raises(error_code: str, action) -> None:
    try:
        action()
    except LLMGatewayContractError as exc:
        if exc.code != error_code:
            raise AssertionError(f"Code erreur inattendu: {exc.code}") from exc
        return
    raise AssertionError(f"Erreur attendue absente: {error_code}")


chat_body = {
    "model": application_configuration.models.llm.served_model_name,
    "conversation_id": "CONV-M013-UNIT-0001",
    "trace_id": "TRACE-M013-UNIT-CHAT-0001",
    "request_id": "REQ-M013-UNIT-CHAT-0001",
    "idempotency_key": "IDEMP-M013-UNIT-CHAT-0001",
    "messages": [{"role": "user", "content": "Question de contrôle."}],
    "sampling_parameters": {"max_tokens": 96, "temperature": 0},
}

inference_body = _build_product_chat_inference_body(
    chat_body,
    application_configuration=application_configuration,
)
assert_equal(inference_body["schema_name"], "m13_reality_product_chat", "Schéma chat produit invalide.")
assert_equal(inference_body["schema_version"], "1.0", "Version schéma chat produit invalide.")
assert_equal(inference_body["trace_id"], "TRACE-M013-UNIT-CHAT-0001", "Trace chat non propagée.")
assert_equal(inference_body["request_id"], "REQ-M013-UNIT-CHAT-0001", "Request id chat non propagé.")
assert_equal(inference_body["idempotency_key"], "IDEMP-M013-UNIT-CHAT-0001", "Idempotence chat non propagée.")
assert_equal(inference_body["prompt_id"], "PROMPT-M013-REALITY-PRODUCT-CHAT", "Prompt chat invalide.")
assert_equal(inference_body["output_schema"]["required"], ["answer"], "Champs requis chat invalides.")
assert_equal(inference_body["messages"][0]["role"], "system", "Instruction système chat absente.")
assert_equal(inference_body["messages"][1]["role"], "user", "Message utilisateur chat absent.")

assert_raises(
    "LOCAL_RUNTIME_MODEL_MISMATCH",
    lambda: _build_product_chat_inference_body(
        {**chat_body, "model": "autre-modele"},
        application_configuration=application_configuration,
    ),
)

benchmark_body = {
    "model": application_configuration.models.llm.served_model_name,
    "run_id": "LLMRUN-M013-UNIT-0001",
    "trace_id": "TRACE-M013-UNIT-BENCHMARK-0001",
    "request_id": "REQ-M013-UNIT-BENCHMARK-0001",
    "idempotency_key": "IDEMP-M013-UNIT-BENCHMARK-0001",
    "sampling_parameters": {"max_tokens": 96, "temperature": 0},
}

for index, task_name in enumerate(REQUIRED_LLM_TASKS, start=1):
    task_body = _build_live_benchmark_task_inference_body(
        benchmark_body,
        task_name=task_name,
        task_index=index,
        application_configuration=application_configuration,
    )
    assert_equal(task_body["schema_name"], "m13_reality_llm_benchmark_task", "Schéma tâche invalide.")
    assert_equal(task_body["schema_version"], "1.0", "Version schéma tâche invalide.")
    assert_equal(
        task_body["trace_id"],
        f"TRACE-M013-UNIT-BENCHMARK-0001-{task_name}",
        "Trace tâche non dérivée explicitement.",
    )
    assert_equal(
        task_body["request_id"],
        f"REQ-M013-UNIT-BENCHMARK-0001-{index:02d}",
        "Request id tâche non dérivé explicitement.",
    )
    assert_equal(
        task_body["idempotency_key"],
        f"IDEMP-M013-UNIT-BENCHMARK-0001-{task_name}",
        "Idempotence tâche non dérivée explicitement.",
    )
    assert_equal(task_body["prompt_id"], f"PROMPT-M013-REALITY-LLM-TASK-{task_name}", "Prompt tâche invalide.")
    assert_equal(
        task_body["output_schema"]["required"],
        ["task_name", "evaluation_marker", "answer"],
        "Champs requis tâche invalides.",
    )

assert_raises(
    "LOCAL_RUNTIME_LLM_TASK_UNKNOWN",
    lambda: _build_live_benchmark_task_inference_body(
        benchmark_body,
        task_name="tache_inconnue",
        task_index=99,
        application_configuration=application_configuration,
    ),
)

print("Tests unitaires M13-reality produit: OK")
'@

$pythonScriptPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ost_m013_reality_product_unit_" + [System.Guid]::NewGuid().ToString("N") + ".py")
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
        throw "Tests unitaires M13-reality produit invalides. Sortie: $($output -join "`n")"
    }
    Write-Host ($output -join "`n")
}
finally {
    Remove-Item -LiteralPath $pythonScriptPath -Force
}
